"""UNODC: source client and pure normalizer for the data portal's Excel
workbooks.

The legacy SSPI read the UNODC Crime Trends Survey workbook "Prisons and
prisoners" from::

    https://dataunodc.un.org/sites/dataunodc.un.org/files/data_cts_prisons_and_prisoners.xlsx

That address now redirects to the home page of the new data portal
(data.unodc.org), which serves the same file, same name and same layout, at
an address that names the upload::

    https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_prisons_and_prisoners.xlsx

Canonical metadata names the workbook edition in ``query_code``;
:data:`WORKBOOKS` maps each known edition to its URL and the SHA-256 of its
bytes. Nothing infers or prefers another edition: a workbook whose bytes
differ from the pin is refused, even at the same address. A caller may pass
its own ``workbooks`` table to read another edition explicitly. Use and
redistribution terms are open: docs/data-governance-review.md, GOV-3.

The first sheet starts with two title rows (``UNODC`` and a contact
address, then the release date) above the header ``Iso3_code``,
``Country``, ``Region``, ``Subregion``, ``Indicator``, ``Dimension``,
``Category``, ``Sex``, ``Age``, ``Year``, ``Unit of measurement``,
``VALUE``, ``Source``; it is long, one row per value. The series is chosen
by metadata: ``organization_series_code`` is the ``Indicator`` and
``dimensions`` are exact-match filters on other columns.

:func:`normalize_unodc_dataset` reproduces the legacy collector and cleaner
(``collect_unodc_pripop`` and ``clean_unodc_pripop`` in
``api/core/datasets/unodc/unodc_pripop.py``) exactly:

* the collector read the first sheet with ``pandas.read_excel`` and stored
  it as CSV text; the cleaner parsed that text back with
  ``pandas.read_csv(..., skiprows=2)``, which drops the two title lines and
  reads the header. The same round trip runs here, so every value has
  exactly the representation the legacy cleaner saw;
* rows are kept when every filter matches exactly;
* :data:`REGIONAL_MEANS` reproduces the legacy cleaner's one special case:
  a United Kingdom row per year, the UNWEIGHTED arithmetic mean
  (``groupby("Year").mean()``) of whichever of the three jurisdictions
  (``GBR_NI``, ``GBR_E_W``, ``GBR_S``) report that year, after the same
  filters (PRISON-1). No other area is combined: Iraq's two reporting
  units (``IRQ_C``, ``IRQ_KRI``) are not (PRISON-4);
* a row with an empty code, year or value is dropped (an empty value is
  counted as missing); a code that is not three characters long is
  skipped and reported (the UK jurisdictions, ``IRQ_C``, ``IRQ_KRI``); the
  country is ``Iso3_code`` as published, with no ISO check; a reported
  zero is kept;
* the unit is the ``Unit of measurement`` cell, which must be the dataset's
  canonical unit.

The legacy clean collection then refused the whole dataset for a code that
is not three capital letters, a year that is not an integer, a value that
is not a number and two values for one country-year; a sheet whose
``VALUE`` column holds any text made the cleaner itself fail. Each is an
error here.

Nothing here touches a database.
"""

from __future__ import annotations

import hashlib
import io
import math
import numbers
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "UNODC"
LEGACY_URL = "https://dataunodc.un.org/sites/dataunodc.un.org/files/data_cts_prisons_and_prisoners.xlsx"
TITLE_ROWS = 2  # the legacy cleaner's read_csv(skiprows=2)
COUNTRY_COLUMN = "Iso3_code"
NAME_COLUMN = "Country"
INDICATOR_COLUMN = "Indicator"
YEAR_COLUMN = "Year"
UNIT_COLUMN = "Unit of measurement"
VALUE_COLUMN = "VALUE"
SOURCE_COLUMN = "Source"
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")

# Dataset -> {combined area: the source areas whose values the legacy cleaner averaged, unweighted, per year}.
REGIONAL_MEANS: dict[str, dict[str, tuple[str, ...]]] = {
    "UNODC_PRIPOP": {"GBR": ("GBR_NI", "GBR_E_W", "GBR_S")},
}


@dataclass(frozen=True, slots=True)
class SourceWorkbook:
    """One edition of one UNODC workbook at one address."""

    edition: str
    url: str
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned location)
    retrieved: str | None = None  # date the pinned bytes were verified at the URL


@dataclass(frozen=True, slots=True)
class UNODCWorkbook:
    """A downloaded workbook: its canonical key, the edition it was configured as, its checksum and bytes."""

    key: str
    source: SourceWorkbook
    sha256: str
    content: bytes


# Workbook edition (canonical query_code) -> where and what it is.
WORKBOOKS: dict[str, SourceWorkbook] = {
    # Crime Trends Survey, "Prisons and prisoners", release dated 30/09/2026 in the workbook (Last-Modified
    # 2026-09-30, 5,943,584 bytes); the file the legacy collector's address served until it was retired.
    "data_cts_prisons_and_prisoners_2026-09-30": SourceWorkbook(
        edition="UNODC Crime Trends Survey, Prisons and prisoners (data_cts_prisons_and_prisoners.xlsx), release of 30/09/2026",
        url="https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_prisons_and_prisoners.xlsx",
        sha256="27f6a3bbc89769a9acef0675335b9ca4dca7ec3776db9499127256d39b7e14e6",
        retrieved="2026-10-25",
    ),
}


def workbook_key(dataset: Any) -> str:
    """The workbook a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no UNODC workbook (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no UNODC indicator (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class UNODCWorkbookClient:
    """Synchronous client for UNODC workbooks.

    ``workbooks`` maps workbook keys to :class:`SourceWorkbook` and defaults
    to :data:`WORKBOOKS`. ``http`` may be injected (tests: an
    ``httpx.Client`` with a ``MockTransport``); otherwise one is created and
    owned by this object.
    """

    def __init__(self, *, workbooks: Mapping[str, SourceWorkbook] | None = None, http: httpx.Client | None = None, timeout: float = 300.0) -> None:
        self.workbooks = dict(WORKBOOKS if workbooks is None else workbooks)
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_workbook(self, key: str) -> UNODCWorkbook:
        """Download one configured workbook and check its bytes against the configured checksum."""
        try:
            source = self.workbooks[key]
        except KeyError:
            raise SourceRequestError(f"no UNODC workbook is configured for {key!r}; known: {sorted(self.workbooks)}") from None
        try:
            response = self.http.get(source.url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"UNODC workbook request for {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"UNODC workbook request for {key!r} returned HTTP {response.status_code} ({source.url})")
        digest = hashlib.sha256(response.content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"UNODC workbook {key!r} ({source.url}) has SHA-256 {digest}, not the configured {source.sha256} of edition "
                f"{source.edition!r}: the published file changed; no other edition is substituted"
            )
        return UNODCWorkbook(key, source, digest, response.content)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> UNODCWorkbookClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def legacy_table(content: bytes) -> Any:
    """The workbook's first sheet as the legacy cleaner saw it: ``read_excel``, then the
    collector's ``to_csv`` and the cleaner's ``read_csv(skiprows=2)``."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    try:
        sheet = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - any unreadable workbook is the same failure
        raise SourceResponseError(f"UNODC workbook is not a readable Excel file: {type(exc).__name__}: {exc}") from None
    return pd.read_csv(io.StringIO(sheet.to_csv(index=False)), skiprows=TITLE_ROWS)


def _is_number(text: Any) -> bool:
    try:
        float(text)
    except (TypeError, ValueError):
        return False
    return True


def normalize_unodc_dataset(dataset: DatasetMetadata, workbook: UNODCWorkbook) -> NormalizationResult:
    """Canonical observations for one dataset from a downloaded UNODC workbook."""
    import pandas as pd

    key = workbook_key(dataset)
    if workbook.key != key:
        raise NormalizationError(f"{dataset.code}: workbook {workbook.key!r} is not the dataset's {key!r}")
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    table = legacy_table(workbook.content)
    filters = {INDICATOR_COLUMN: dataset.source.organization_series_code, **(dataset.source.dimensions or {})}
    absent = [c for c in (COUNTRY_COLUMN, NAME_COLUMN, YEAR_COLUMN, UNIT_COLUMN, VALUE_COLUMN, SOURCE_COLUMN, *filters) if c not in table.columns]
    if absent:
        raise NormalizationError(f"{dataset.code}: workbook {key!r} lacks columns {absent}; found {list(table.columns)}")
    if not pd.api.types.is_numeric_dtype(table[VALUE_COLUMN]):
        cells = sorted({str(v) for v in table[VALUE_COLUMN].dropna() if not _is_number(v)})
        raise NormalizationError(
            f"{dataset.code}: workbook {key!r} has VALUE cells that are not numbers ({cells[:5]}); the legacy cleaner stored nothing "
            "for such a sheet (its United Kingdom mean raised, and the clean collection refused text values)"
        )
    selected = table
    for column, wanted in filters.items():
        selected = selected[selected[column] == wanted]
    combined = []
    for area, parts in REGIONAL_MEANS.get(dataset.code, {}).items():
        regions = selected[selected[COUNTRY_COLUMN].isin(parts)]
        if len(regions) > 0:
            means = regions.groupby(YEAR_COLUMN).agg({VALUE_COLUMN: "mean"}).reset_index()
            reporting = regions.groupby(YEAR_COLUMN)[COUNTRY_COLUMN].agg(lambda codes: sorted(codes))
            means[COUNTRY_COLUMN] = area
            means[UNIT_COLUMN] = filters.get(UNIT_COLUMN)  # the legacy literal, the unit the rows were filtered on
            means["_regions"] = means[YEAR_COLUMN].map(reporting)
            combined.append(means)
    rows = pd.concat([selected, *combined], ignore_index=True) if combined else selected.reset_index(drop=True)
    where = f"{dataset.code} workbook {key!r}"
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for _, row in rows.iterrows():
        country, year, raw = row[COUNTRY_COLUMN], row[YEAR_COLUMN], row[VALUE_COLUMN]
        if pd.isna(country) or pd.isna(year):
            continue  # legacy dropna on CountryCode and Year: the row is not an observation
        if pd.isna(raw):
            missing += 1
            continue
        name = row.get(NAME_COLUMN)
        if len(str(country)) != 3:
            skipped.setdefault((str(country), name if isinstance(name, str) else ""))
            continue
        if not isinstance(country, str) or not _STORABLE_COUNTRY.match(country):
            raise NormalizationError(f"{where}: Iso3_code {country!r} cannot be stored (three capital letters required; the legacy clean collection refused it too)")
        if isinstance(year, bool) or not isinstance(year, numbers.Integral):
            raise NormalizationError(f"{where}: ({country}) year {year!r} is not an integer (the legacy clean collection refused it too)")
        year = int(year)
        if isinstance(raw, bool) or type(raw).__name__ == "bool_" or not isinstance(raw, numbers.Real):  # numpy scalars register as numbers.Real
            raise NormalizationError(f"{where}: ({country}, {year}) value {raw!r} is not a number (the legacy clean collection refused it too)")
        value = float(raw)
        if not math.isfinite(value):
            raise NormalizationError(f"{where}: ({country}, {year}) value {raw!r} is not finite")
        unit = row[UNIT_COLUMN]
        if unit != dataset.unit:
            raise NormalizationError(f"{where}: ({country}, {year}) unit {unit!r} is not the canonical unit {dataset.unit!r}")
        if (country, year) in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({country}, {year}) in workbook {key!r} for {filters}")
        seen.add((country, year))
        regions = row.get("_regions")
        provenance: dict[str, Any] = {
            "source_organization": ORGANIZATION_CODE,
            "source_file": workbook.key,
            "source_edition": workbook.source.edition,
            "source_url": workbook.source.url,
            "source_sha256": workbook.sha256,
            "source_selection": dict(filters),
            "source_value": repr(raw.item() if hasattr(raw, "item") else raw),
        }
        if isinstance(regions, list):
            provenance.update(unweighted_mean_of=regions, source_country_name=None, source=None)
        else:
            provenance.update(source_country_name=name if isinstance(name, str) else None, source=row[SOURCE_COLUMN] if isinstance(row[SOURCE_COLUMN], str) else None)
        observations.append(Observation(dataset.code, country, year, value, unit, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)
