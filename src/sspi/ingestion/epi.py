"""Yale Environmental Performance Index (EPI): source client and pure normalizer.

The EPI publishes one zip per edition holding one wide CSV per indicator:
``code,iso,country,<TLA>.ind.<year>,...``. Canonical metadata names the
edition archive in ``query_code`` and the indicator's three-letter series
code in ``organization_series_code``; :data:`ARCHIVES` maps each known
archive to its download URL, so a new edition is one more row here plus a
documented metadata edit, not a new parser.

The legacy collector downloaded ``epi2024indicators.zip`` and derived each
file's series code from its file name (the part before the first ``_``);
the legacy cleaner (``parse_epi_csv``) dropped the ``code`` and ``country``
columns, melted the year columns, took the year as the four digits in the
column name, dropped NaN and negative values (the EPI's missing-value codes
are negative) and labelled everything ``Index``. :func:`normalize_epi_dataset`
does exactly that: ISO3 comes from the ``iso`` column as published, no
geography remapping, no imputation, values otherwise unchanged. Missing
values are the tokens pandas treated as NaN (``NA`` in the published files).

Nothing here touches a database.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from collections.abc import Mapping
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "EPI"
UNIT = "Index"  # legacy literal for every EPI indicator score
# Edition archive (canonical query_code) -> download URL.
ARCHIVES: dict[str, str] = {
    # Legacy collector URL. It now serves an HTML page; kept for the record and for the committed historical fixture.
    "epi2024indicators": "https://epi.yale.edu/downloads/epi2024indicators.zip",
    # Current official distribution (2026 edition, NA missing-value variant).
    "epi2026_indicators_na_2026-08-31": "https://epi.yale.edu/sites/default/files/2026-09/epi2026_indicators_na_2026-08-31.zip",
}
ID_COLUMNS = ("code", "iso", "country")
# pandas.read_csv default NA tokens: what the legacy cleaner saw as NaN and dropped.
MISSING_TOKENS = frozenset({"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"})
_YEAR = re.compile(r"\d{4}")


def archive_key(dataset: Any) -> str:
    """The edition archive a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no edition archive (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no EPI series code (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class EPIClient:
    """Synchronous client for the EPI edition archives.

    ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, timeout: float = 120.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_archive(self, archive: str) -> dict[str, str]:
        """The CSV members of an edition archive, by file name (directories and macOS metadata dropped)."""
        try:
            url = ARCHIVES[archive]
        except KeyError:
            raise SourceRequestError(f"no EPI archive URL is registered for {archive!r}; known: {sorted(ARCHIVES)}") from None
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"EPI request for archive {archive!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"EPI request for archive {archive!r} returned HTTP {response.status_code} ({url})")
        return read_archive(response.content, archive)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> EPIClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_archive(content: bytes, archive: str) -> dict[str, str]:
    """``{file name: csv text}`` for every CSV in a zip, whatever directory it sits in."""
    try:
        zipped = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise SourceResponseError(f"EPI archive {archive!r} is not a zip file (the legacy 2024 URL now serves an HTML page)") from None
    files: dict[str, str] = {}
    with zipped:
        for name in zipped.namelist():
            if name.endswith("/") or "__MACOSX" in name or not name.lower().endswith(".csv"):
                continue
            basename = name.rsplit("/", 1)[-1]
            if basename in files:
                raise SourceResponseError(f"EPI archive {archive!r} holds two files named {basename!r}")
            files[basename] = zipped.read(name).decode("utf-8-sig")
    if not files:
        raise SourceResponseError(f"EPI archive {archive!r} holds no CSV files")
    return files


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def series_of(file_name: str) -> str:
    """Legacy rule: the series code is the file name up to the first ``_`` (``SNM_ind_na.csv`` -> ``SNM``)."""
    return file_name.rsplit("/", 1)[-1].split(".")[0].split("_")[0]


def normalize_epi_dataset(dataset: DatasetMetadata, archive: Mapping[str, str]) -> NormalizationResult:
    """Convert the dataset's indicator CSV from an edition archive into canonical observations."""
    edition = archive_key(dataset)
    series = dataset.source.organization_series_code
    matches = [name for name in archive if series_of(name) == series]
    if len(matches) != 1:
        raise NormalizationError(f"{dataset.code}: expected one file for series {series!r} in archive {edition!r}, found {matches}; files: {sorted(archive)}")
    file_name = matches[0]
    return normalize_epi_csv(dataset, archive[file_name], edition=edition, file_name=file_name)


def normalize_epi_csv(dataset: DatasetMetadata, text: str, *, edition: str = "", file_name: str = "") -> NormalizationResult:
    """The legacy ``parse_epi_csv`` on one wide indicator CSV."""
    if dataset.unit != UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit is {dataset.unit!r}; every EPI indicator score is {UNIT!r}")
    reader = csv.DictReader(io.StringIO(text))
    columns = list(reader.fieldnames or ())
    where = f"{dataset.code} file {file_name or '<csv>'}"
    missing_columns = [c for c in ID_COLUMNS if c not in columns]
    if missing_columns:
        raise NormalizationError(f"{where}: header lacks columns {missing_columns}; found {columns}")
    year_columns: dict[str, int] = {}
    for column in columns:
        if column in ID_COLUMNS:
            continue
        match = _YEAR.search(column)
        if match is None:
            raise NormalizationError(f"{where}: column {column!r} carries no four-digit year")
        year_columns[column] = int(match.group(0))
    if not year_columns:
        raise NormalizationError(f"{where}: no year columns")

    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    missing = 0
    negative = 0
    for index, row in enumerate(reader, start=2):
        iso = (row.get("iso") or "").strip()
        if not iso:
            raise NormalizationError(f"{where} line {index}: empty iso")
        for column, year in year_columns.items():
            raw = row.get(column)
            if raw is None or raw.strip() in MISSING_TOKENS:
                missing += 1
                continue
            value = _parse_value(raw, f"{where} line {index} column {column}")
            if value < 0:
                negative += 1  # EPI missing-value codes are negative; legacy dropped them after the NaN drop
                continue
            key = (iso, year)
            if key in seen:
                raise DuplicateObservationError(f"{dataset.code}: duplicate ({iso}, {year}) in {file_name or '<csv>'}")
            seen.add(key)
            provenance = {
                "source_organization": ORGANIZATION_CODE,
                "source_edition": edition or None,
                "source_file": file_name or None,
                "source_series": dataset.source.organization_series_code,
                "source_column": column,
                "source_code": row.get("code"),
                "source_country_name": row.get("country"),
            }
            observations.append(Observation(dataset.code, iso, year, value, UNIT, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), missing + negative)


def _parse_value(raw: str, where: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        raise NormalizationError(f"{where}: value {raw!r} is not numeric") from None
    if not math.isfinite(value):
        raise NormalizationError(f"{where}: value {raw!r} is not finite")
    return value
