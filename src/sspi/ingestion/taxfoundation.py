"""Tax Foundation: source client and pure normalizer for its published CSV files.

The Tax Foundation offers no data API. It publishes each data set as a CSV
file per edition, at an edition-specific address, for example the worldwide
corporate tax rates of January 2025::

    https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv

Canonical metadata names the edition file in ``query_code``; :data:`FILES`
maps each known file to its edition label, its URL and the SHA-256 of its
content. Nothing infers or prefers a newer edition: a different edition is
one more row here plus a documented metadata edit. The client refuses a
download whose checksum differs from the configured one, so a file that
changes in place is an error, never a silent substitute. A caller may pass
its own ``files`` table to read another location or edition explicitly.

The file is wide: an unnamed row-number column, ``iso_2``, ``iso_3``,
``continent``, ``country`` and one column per year. :func:`normalize_taxfoundation_dataset`
reproduces the legacy cleaner (``clean_tax_foundation``):

* the row-number, ``iso_2``, ``continent`` and ``country`` columns are
  dropped and every year column is melted against ``iso_3``; the country is
  ``iso_3`` as published, with no ISO check and no country filter
  (territories, ``XKX`` and ``ANT`` are kept);
* a cell holding one of pandas' default missing-value tokens (``NA`` in the
  published file) is missing and dropped; nothing else is. A reported
  ``0`` is a value and is kept;
* the year is the column name as an integer, every year column is kept;
* the value is the published number, unchanged; the unit is the canonical
  unit of the dataset (the legacy literal).

A row whose ``iso_3`` is itself a missing token was dropped by the legacy
``dropna``; it is skipped and reported here. A second row for the same
``iso_3`` would have given legacy two values per country-year; it is an
error. Nothing here touches a database.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "TF"
ROW_NUMBER_COLUMN = ""  # pandas named it "Unnamed: 0"
COUNTRY_COLUMN = "iso_3"
DROPPED_COLUMNS = (ROW_NUMBER_COLUMN, "iso_2", "continent", "country")  # what the legacy cleaner dropped before melting
# pandas.read_csv default NA tokens: what the legacy cleaner saw as NaN and dropped.
MISSING_TOKENS = frozenset({"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"})


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One published edition of one Tax Foundation file."""

    edition: str
    url: str
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned location)


@dataclass(frozen=True, slots=True)
class TaxFoundationFile:
    """A downloaded file: its canonical key, the edition it was configured as, and its text."""

    key: str
    source: SourceFile
    sha256: str
    text: str


# Edition file (canonical query_code) -> where and what it is.
FILES: dict[str, SourceFile] = {
    # Worldwide corporate tax rates, January 2025 edition, 1980-2024: the file the legacy collector
    # (api/datasource/taxfoundation.py) downloaded. Byte-identical to the Internet Archive captures of
    # 2025-01-17 and 2025-05-28 of the same address.
    "rates_final_2025-01": SourceFile(
        edition="2025/01",
        url="https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv",
        sha256="7dd8f506e2942c816e28f01c7c478402fb39d3c263cf6c38b32f04df3fab9f52",
    ),
}


def file_key(dataset: Any) -> str:
    """The edition file a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no Tax Foundation file (query_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class TaxFoundationClient:
    """Synchronous client for Tax Foundation CSV files.

    ``files`` maps file keys to :class:`SourceFile` and defaults to
    :data:`FILES`. ``http`` may be injected (tests: an ``httpx.Client`` with
    a ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, files: Mapping[str, SourceFile] | None = None, http: httpx.Client | None = None, timeout: float = 120.0) -> None:
        self.files = dict(FILES if files is None else files)
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_file(self, key: str) -> TaxFoundationFile:
        """Download one configured file and check its content against the configured checksum."""
        try:
            source = self.files[key]
        except KeyError:
            raise SourceRequestError(f"no Tax Foundation file is configured for {key!r}; known: {sorted(self.files)}") from None
        try:
            response = self.http.get(source.url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"Tax Foundation request for {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"Tax Foundation request for {key!r} returned HTTP {response.status_code} ({source.url})")
        digest = hashlib.sha256(response.content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"Tax Foundation file {key!r} ({source.url}) has SHA-256 {digest}, not the configured {source.sha256} of edition "
                f"{source.edition}: the published file changed; no other edition is substituted"
            )
        try:
            text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            raise SourceResponseError(f"Tax Foundation file {key!r} is not UTF-8 text") from None
        return TaxFoundationFile(key, source, digest, text)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> TaxFoundationClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_taxfoundation_dataset(dataset: DatasetMetadata, file: TaxFoundationFile) -> NormalizationResult:
    """Canonical observations for one dataset from a downloaded Tax Foundation file."""
    key = file_key(dataset)
    if file.key != key:
        raise NormalizationError(f"{dataset.code}: file {file.key!r} is not the dataset's {key!r}")
    reader = csv.reader(io.StringIO(file.text, newline=""))
    header = next(reader, None)
    if header is None:
        raise NormalizationError(f"{dataset.code}: file {key!r} is empty")
    if len(set(header)) != len(header):
        raise NormalizationError(f"{dataset.code}: file {key!r} repeats a column name: {header}")
    missing_columns = [c for c in (*DROPPED_COLUMNS, COUNTRY_COLUMN) if c not in header]
    if missing_columns:
        raise NormalizationError(f"{dataset.code}: file {key!r} lacks columns {missing_columns}; found {header}")
    year_columns: list[tuple[int, int]] = []
    for position, name in enumerate(header):
        if name in DROPPED_COLUMNS or name == COUNTRY_COLUMN:
            continue
        try:
            year_columns.append((position, int(name)))  # legacy: Year.astype(int) on every melted column name
        except ValueError:
            raise NormalizationError(f"{dataset.code}: file {key!r} column {name!r} is not a year") from None
    country_index, name_index = header.index(COUNTRY_COLUMN), header.index("country")
    observations: list[Observation] = []
    skipped: dict[tuple[str, str], None] = {}
    seen: set[str] = set()
    missing = 0
    for line, row in enumerate(reader, start=2):
        if len(row) != len(header):
            raise NormalizationError(f"{dataset.code}: file {key!r} line {line} has {len(row)} fields, header has {len(header)}")
        country = row[country_index]
        if country in MISSING_TOKENS:
            skipped.setdefault((country, row[name_index]))  # legacy dropna removed every cell of the row
            continue
        if country in seen:
            raise DuplicateObservationError(f"{dataset.code}: {country} has more than one row in file {key!r}")
        seen.add(country)
        for position, year in year_columns:
            raw = row[position]
            if raw in MISSING_TOKENS:
                missing += 1
                continue
            observations.append(Observation(dataset.code, country, year, _parse_value(raw, f"{dataset.code} file {key!r} ({country}, {year})"), dataset.unit, _provenance(file, raw, row[name_index])))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)


def _provenance(file: TaxFoundationFile, raw: str, country_name: str) -> dict[str, Any]:
    return {
        "source_organization": ORGANIZATION_CODE,
        "source_file": file.key,
        "source_edition": file.source.edition,
        "source_url": file.source.url,
        "source_sha256": file.sha256,
        "source_country_name": country_name,
        "source_value": raw,
    }


def _parse_value(raw: str, where: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        raise NormalizationError(f"{where}: value {raw!r} is not numeric") from None
    if not math.isfinite(value):
        raise NormalizationError(f"{where}: value {raw!r} is not finite")
    return value
