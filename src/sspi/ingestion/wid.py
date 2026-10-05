"""World Inequality Database (WID): source client and pure normalizer.

WID publishes one bulk archive, ``wid_all_data.zip``, holding two
semicolon-delimited files per country (keyed by ISO 3166-1 alpha-2):
``WID_data_<XX>.csv`` (``country;variable;percentile;year;value;age;pop``)
and ``WID_metadata_<XX>.csv`` (one row per variable, with its ``unit``).
Canonical metadata names the archive in ``query_code``, the WID variable in
``organization_series_code`` (for example ``sptincj992``: share, pre-tax
national income, equal-split adults, age 20+) and the percentile group in
``dimensions.percentile`` (``p0p50``, ``p90p100``). One archive serves every
WID dataset; the runner fetches it once per ingest call.

:func:`normalize_wid_dataset` reproduces the legacy cleaner
(``filter_wid_csv`` as every ``wid_*.py`` cleaner called it):

* countries: the members of the ``SSPI67`` group only, each read from its
  own country file; a member whose data or metadata file is absent is an
  error, as the legacy cleaner asserted;
* rows: ``variable`` and ``percentile`` equal to the dataset's, ``year`` in
  2000-2024 inclusive (every legacy WID cleaner used ``range(2000, 2025)``);
* unit: ``"<unit>; percentile <percentile>; <variable>"`` with ``<unit>``
  from the first metadata row for the variable (``No unit available`` when
  there is none), and it must equal the canonical unit;
* value: the legacy cleaner parsed the column as ``float32`` and serialized
  it with pandas ``to_json`` (ten decimals), so the published ``0.1921`` was
  stored as ``0.1921000034``. :func:`legacy_float32_value` reproduces that
  number exactly. This is a source-representation quirk kept for parity
  (PROVENANCE.yaml), not a methodology; the published text is kept in
  provenance as ``source_value``.

No geography remapping, no imputation, no flag filtering. Nothing here
touches a database.
"""

from __future__ import annotations

import csv
import io
import math
import struct
import tempfile
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, NamedTuple

import httpx
import pycountry

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "WID"
# Bulk archive (canonical query_code) -> download URL.
ARCHIVES: dict[str, str] = {
    "wid_all_data": "https://wid.world/bulk_download/wid_all_data.zip",
}
LEGACY_COUNTRY_GROUP = "SSPI67"  # every legacy WID cleaner looped over this group
LEGACY_YEARS: tuple[int, int] = (2000, 2024)  # every legacy WID cleaner kept range(2000, 2025)
DATA_COLUMNS = ("variable", "percentile", "year", "value")
NO_UNIT = "No unit available"
_JSON_DECIMALS = 10  # pandas to_json default double_precision
_JSON_MAX_MAGNITUDE = 1e15  # beyond this pandas switches notation; not reproduced, refused


class SeriesSelection(NamedTuple):
    archive: str
    variable: str
    percentile: str


def series_selection(dataset: Any) -> SeriesSelection:
    """The (archive, variable, percentile) a dataset selects, from canonical metadata."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no WID archive (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no WID variable (organization_series_code) in canonical metadata")
    dimensions = dict(source.dimensions or {})
    if set(dimensions) != {"percentile"}:
        raise NormalizationError(f"{dataset.code}: WID datasets select exactly one dimension, 'percentile'; canonical metadata has {dimensions}")
    return SeriesSelection(source.query_code, source.organization_series_code, dimensions["percentile"])


def archive_key(dataset: Any) -> str:
    """The bulk archive a dataset is read from (its canonical ``query_code``)."""
    return series_selection(dataset).archive


def country_file_names(alpha_2: str) -> tuple[str, str]:
    """(data file, metadata file) for one country in the bulk archive."""
    return f"WID_data_{alpha_2}.csv", f"WID_metadata_{alpha_2}.csv"


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class WIDArchive(Mapping[str, str]):
    """Read-only ``{member name: text}`` view of a bulk archive on disk.

    Members are decompressed on access and not cached: the archive holds
    several gigabytes of CSV and a normalizer reads only the country files
    it needs.
    """

    def __init__(self, file: Any, archive: str) -> None:
        self._file = file
        self.archive = archive
        try:
            self._zip = zipfile.ZipFile(file)
        except zipfile.BadZipFile:
            raise SourceResponseError(f"WID archive {archive!r} is not a zip file") from None
        self._names = {name.rsplit("/", 1)[-1]: name for name in self._zip.namelist() if not name.endswith("/") and "__MACOSX" not in name}
        if not self._names:
            raise SourceResponseError(f"WID archive {archive!r} holds no files")

    def __getitem__(self, name: str) -> str:
        return self._zip.read(self._names[name]).decode("utf-8")

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def close(self) -> None:
        self._zip.close()
        self._file.close()


class WIDClient:
    """Synchronous client for the WID bulk archive.

    The archive is several hundred megabytes, so it is streamed to a
    temporary file that lives until :meth:`close`. ``http`` may be injected
    (tests: an ``httpx.Client`` with a ``MockTransport``); otherwise one is
    created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, timeout: float = 1800.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=httpx.Timeout(timeout, connect=30.0), follow_redirects=True)
        self._archives: list[WIDArchive] = []

    def fetch_archive(self, archive: str) -> WIDArchive:
        """Download one bulk archive and open it for member-by-member reading."""
        try:
            url = ARCHIVES[archive]
        except KeyError:
            raise SourceRequestError(f"no WID archive URL is registered for {archive!r}; known: {sorted(ARCHIVES)}") from None
        spooled = tempfile.TemporaryFile()
        try:
            with self.http.stream("GET", url) as response:
                if response.status_code != 200:
                    raise SourceRequestError(f"WID request for archive {archive!r} returned HTTP {response.status_code} ({url})")
                for chunk in response.iter_bytes():
                    spooled.write(chunk)
        except httpx.HTTPError as exc:
            spooled.close()
            raise SourceRequestError(f"WID request for archive {archive!r} failed: {exc}") from exc
        except BaseException:
            spooled.close()
            raise
        spooled.seek(0)
        try:
            opened = WIDArchive(spooled, archive)
        except BaseException:
            spooled.close()
            raise
        self._archives.append(opened)
        return opened

    def close(self) -> None:
        for opened in self._archives:
            opened.close()
        self._archives.clear()
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> WIDClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def legacy_float32_value(raw: str, where: str = "value") -> float:
    """The number the legacy cleaner stored for a published WID value.

    Legacy path: pandas parsed the column as ``float32``; ``DataFrame.to_json``
    wrote the widened value with ten decimals (round half to even on the
    scaled fraction); ``json.loads`` read that text back. ``"0.1921"``
    therefore became ``0.1921000034``. Same steps, same arithmetic, here.
    """
    try:
        parsed = float(raw)
    except ValueError:
        raise NormalizationError(f"{where}: value {raw!r} is not numeric") from None
    if not math.isfinite(parsed):
        raise NormalizationError(f"{where}: value {raw!r} is not finite")
    try:
        (single,) = struct.unpack("<f", struct.pack("<f", parsed))
    except OverflowError:
        raise NormalizationError(f"{where}: value {raw!r} does not fit float32") from None
    magnitude = abs(single)
    if magnitude >= _JSON_MAX_MAGNITUDE:
        raise NormalizationError(f"{where}: value {raw!r} is too large for the legacy ten-decimal representation")
    scale = 10**_JSON_DECIMALS
    whole = int(magnitude)
    scaled = (magnitude - whole) * float(scale)
    fraction = int(scaled)
    remainder = scaled - fraction
    if remainder > 0.5 or (remainder == 0.5 and (fraction == 0 or fraction & 1)):
        fraction += 1
        if fraction >= scale:
            fraction -= scale
            whole += 1
    return float(f"{'-' if single < 0 else ''}{whole}.{fraction:0{_JSON_DECIMALS}d}")


def metadata_unit(metadata_text: str, variable: str) -> str:
    """Legacy unit lookup: the ``unit`` of the first metadata row for ``variable``."""
    reader = csv.DictReader(io.StringIO(metadata_text, newline=""), delimiter=";")
    for row in reader:
        if row.get("variable") == variable:
            unit = row.get("unit")
            return unit if unit else NO_UNIT if unit is None else unit
    return NO_UNIT


def _default_countries() -> tuple[str, ...]:
    from sspi.metadata import CountryCatalog

    return tuple(CountryCatalog.load().group(LEGACY_COUNTRY_GROUP).members)


def normalize_wid_dataset(
    dataset: DatasetMetadata,
    archive: Mapping[str, str],
    *,
    countries: Sequence[str] | None = None,
    years: tuple[int, int] = LEGACY_YEARS,
) -> NormalizationResult:
    """Canonical observations for one WID dataset from a bulk archive.

    ``archive`` maps member names to text (a :class:`WIDArchive`, or a plain
    dict in tests). ``countries`` are ISO3 codes and default to the
    ``SSPI67`` members, the legacy cleaner's country universe.
    """
    selection = series_selection(dataset)
    expected_unit = dataset.unit.strip()
    observations: list[Observation] = []
    for iso3 in _default_countries() if countries is None else countries:
        country = pycountry.countries.get(alpha_3=iso3)
        if country is None:
            raise NormalizationError(f"{dataset.code}: {iso3!r} is not an ISO 3166-1 alpha-3 code; WID files are keyed by alpha-2")
        data_name, metadata_name = country_file_names(country.alpha_2)
        missing_files = [name for name in (data_name, metadata_name) if name not in archive]
        if missing_files:
            raise NormalizationError(f"{dataset.code}: WID archive {selection.archive!r} has no {missing_files} for {iso3}")
        unit = f"{metadata_unit(archive[metadata_name], selection.variable)}; percentile {selection.percentile}; {selection.variable}"
        if unit != expected_unit:
            raise NormalizationError(f"{dataset.code}: {metadata_name} gives unit {unit!r}, canonical unit is {expected_unit!r}")
        observations.extend(_country_observations(dataset, selection, iso3, data_name, archive[data_name], unit, years))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), 0)


def _country_observations(
    dataset: DatasetMetadata, selection: SeriesSelection, iso3: str, file_name: str, text: str, unit: str, years: tuple[int, int]
) -> list[Observation]:
    lines = io.StringIO(text, newline="")
    header = next(csv.reader([lines.readline()], delimiter=";"), [])
    missing_columns = [c for c in DATA_COLUMNS if c not in header]
    if missing_columns:
        raise NormalizationError(f"{dataset.code} file {file_name}: header lacks columns {missing_columns}; found {header}")
    index = {name: header.index(name) for name in header}
    needle = f";{selection.variable};" if index["variable"] > 0 else f"{selection.variable};"  # cheap pre-filter; the exact test follows
    start, end = years
    observations: list[Observation] = []
    seen: set[int] = set()
    for row in csv.reader((line for line in lines if needle in line), delimiter=";"):
        if len(row) < len(header) or row[index["variable"]] != selection.variable or row[index["percentile"]] != selection.percentile:
            continue
        where = f"{dataset.code} file {file_name} ({selection.variable}, {selection.percentile}, {row[index['year']]})"
        try:
            year = int(row[index["year"]])
        except ValueError:
            raise NormalizationError(f"{where}: year is not an integer") from None
        if not start <= year <= end:
            continue
        raw = row[index["value"]]
        if raw.strip() == "":
            raise NormalizationError(f"{where}: empty value; the legacy cleaner stored a null here and no rule exists for it")
        if year in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({iso3}, {year}) in {file_name}")
        seen.add(year)
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_archive": selection.archive,
            "source_file": file_name,
            "source_variable": selection.variable,
            "source_percentile": selection.percentile,
            "source_age": row[index["age"]] if "age" in index else None,
            "source_population": row[index["pop"]] if "pop" in index else None,
            "source_value": raw,
            "value_representation": "float32, ten decimals (legacy cleaner)",
        }
        observations.append(Observation(dataset.code, iso3, year, legacy_float32_value(raw, where), unit, provenance))
    return observations
