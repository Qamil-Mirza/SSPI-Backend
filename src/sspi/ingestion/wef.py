"""World Economic Forum: source client and pure normalizer for WEF data
workbooks.

The WEF publishes no data API for its historical indexes. The legacy SSPI
read one Excel workbook, the WEF Global Competitiveness Index Historical
Dataset, from the address where the World Bank hosts it::

    https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx

It is WEF data on a World Bank server, not a World Bank Indicators (WDI)
series, so it has its own adapter. Its licence terms are an open
data-governance question (docs/data-governance-review.md, GOV-2).

Canonical metadata names the workbook in ``query_code``; :data:`WORKBOOKS`
maps each known workbook to its edition, its URL and the SHA-256 of its
bytes. Nothing infers or prefers another edition: a workbook whose bytes
differ from the pin is refused, even at the same address and under the same
file name. A caller may pass its own ``workbooks`` table to read another
edition or location explicitly; the default never changes silently.

The workbook's first sheet is long in indicators and wide in years:
``Economy ISO3``, ``Economy Name``, ``Indicator ID``, ``Indicator``,
``Attribute 1`` to ``Attribute 3``, ``Partner`` and one column per year.
The series is selected by metadata: ``organization_series_code`` is the
``Indicator ID`` and ``dimensions`` are exact-match filters on other
columns (``Attribute 1: Value`` keeps the values and drops the ranks).

:func:`normalize_wef_dataset` reproduces the legacy collector and cleaner
(``collect_wef_data``, ``clean_wef_quelec``) exactly:

* the collector read the first sheet with ``pandas.read_excel`` and stored
  it as CSV text (``DataFrame.to_csv``); the cleaner parsed that text back
  with ``pandas.read_csv``. The same round trip runs here, so every value
  has exactly the representation the legacy cleaner saw, whatever the
  workbook holds;
* rows are filtered on ``Indicator ID`` and the declared dimensions, every
  column whose name is all digits is a year, and the year columns are
  melted; a missing cell is a missing value, dropped and counted; nothing
  is rounded, a reported zero is kept;
* the country is ``Economy ISO3`` as published: no ISO check, no country
  filter. The legacy clean collection refused, and so refused the whole
  dataset for, a code that is not three capital letters, two values for one
  country-year and a value that is not a number; each is an error here;
* the unit is the text after the first comma of the ``Indicator`` name
  (``"Quality of electricity supply, 1-7 (best)"`` gives ``1-7 (best)``), as
  the legacy cleaner derived it; it must equal the dataset's canonical unit.

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

ORGANIZATION_CODE = "WEF"
COUNTRY_COLUMN = "Economy ISO3"
NAME_COLUMN = "Economy Name"
INDICATOR_ID_COLUMN = "Indicator ID"
INDICATOR_COLUMN = "Indicator"
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class SourceWorkbook:
    """One edition of one WEF workbook at one address."""

    edition: str
    url: str
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned location)
    retrieved: str | None = None  # date the pinned bytes were verified at the URL


@dataclass(frozen=True, slots=True)
class WEFWorkbook:
    """A downloaded workbook: its canonical key, the edition it was configured as, its checksum and bytes."""

    key: str
    source: SourceWorkbook
    sha256: str
    content: bytes


# Workbook (canonical query_code) -> where and what it is.
WORKBOOKS: dict[str, SourceWorkbook] = {
    # WEF Global Competitiveness Index Historical Dataset (dataset "Last Updated" 2023-07-17; 2007-2017,
    # 152 economies), the workbook the legacy collector (api/datasource/wef.py) downloaded. Served on
    # 2026-10-19 with Last-Modified 2024-02-16 and 3,476,362 bytes.
    "WEF-GCIHH_2023-07-17": SourceWorkbook(
        edition="WEF Global Competitiveness Index Historical Dataset, last updated 2023-07-17 (2007-2017)",
        url="https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx",
        sha256="a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451",
        retrieved="2026-10-19",
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
        raise NormalizationError(f"{dataset.code}: no WEF workbook (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no WEF indicator (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class WEFWorkbookClient:
    """Synchronous client for WEF workbooks.

    ``workbooks`` maps workbook keys to :class:`SourceWorkbook` and defaults
    to :data:`WORKBOOKS`. ``http`` may be injected (tests: an
    ``httpx.Client`` with a ``MockTransport``); otherwise one is created and
    owned by this object.
    """

    def __init__(self, *, workbooks: Mapping[str, SourceWorkbook] | None = None, http: httpx.Client | None = None, timeout: float = 300.0) -> None:
        self.workbooks = dict(WORKBOOKS if workbooks is None else workbooks)
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_workbook(self, key: str) -> WEFWorkbook:
        """Download one configured workbook and check its bytes against the configured checksum."""
        try:
            source = self.workbooks[key]
        except KeyError:
            raise SourceRequestError(f"no WEF workbook is configured for {key!r}; known: {sorted(self.workbooks)}") from None
        try:
            response = self.http.get(source.url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"WEF workbook request for {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"WEF workbook request for {key!r} returned HTTP {response.status_code} ({source.url})")
        digest = hashlib.sha256(response.content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"WEF workbook {key!r} ({source.url}) has SHA-256 {digest}, not the configured {source.sha256} of edition "
                f"{source.edition!r}: the published file changed; no other edition is substituted"
            )
        return WEFWorkbook(key, source, digest, response.content)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> WEFWorkbookClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def legacy_table(content: bytes) -> Any:
    """The workbook's first sheet as the legacy cleaner saw it: ``read_excel``, then the
    collector's ``to_csv`` and the cleaner's ``read_csv``."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    try:
        sheet = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 - any unreadable workbook is the same failure
        raise SourceResponseError(f"WEF workbook is not a readable Excel file: {type(exc).__name__}: {exc}") from None
    return pd.read_csv(io.StringIO(sheet.to_csv(index=False)))


def legacy_unit(indicator_name: str) -> str:
    """The legacy cleaner's unit: the text after the first comma of the indicator name, or empty."""
    return indicator_name.split(",")[1].strip() if "," in indicator_name else ""


def normalize_wef_dataset(dataset: DatasetMetadata, workbook: WEFWorkbook) -> NormalizationResult:
    """Canonical observations for one dataset from a downloaded WEF workbook."""
    import pandas as pd

    key = workbook_key(dataset)
    if workbook.key != key:
        raise NormalizationError(f"{dataset.code}: workbook {workbook.key!r} is not the dataset's {key!r}")
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    table = legacy_table(workbook.content)
    filters = {INDICATOR_ID_COLUMN: dataset.source.organization_series_code, **(dataset.source.dimensions or {})}
    absent = [c for c in (COUNTRY_COLUMN, NAME_COLUMN, INDICATOR_COLUMN, *filters) if c not in table.columns]
    if absent:
        raise NormalizationError(f"{dataset.code}: workbook {key!r} lacks columns {absent}; found {list(table.columns)}")
    selected = table
    for column, wanted in filters.items():
        selected = selected[selected[column] == wanted]
    year_columns = [c for c in table.columns if c.isdigit()]
    if not year_columns:
        raise NormalizationError(f"{dataset.code}: workbook {key!r} has no year columns")
    where = f"{dataset.code} workbook {key!r}"
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    missing = 0
    for _, row in selected.iterrows():
        country, name, indicator = row[COUNTRY_COLUMN], row[NAME_COLUMN], row[INDICATOR_COLUMN]
        if not isinstance(country, str) or not _STORABLE_COUNTRY.match(country):
            raise NormalizationError(f"{where}: Economy ISO3 {country!r} cannot be stored (three capital letters required; the legacy clean collection refused it too)")
        unit = legacy_unit(indicator) if isinstance(indicator, str) else ""
        if unit != dataset.unit:
            raise NormalizationError(f"{where}: unit {unit!r} derived from indicator name {indicator!r} is not the canonical unit {dataset.unit!r}")
        for column in year_columns:
            raw = row[column]
            if pd.isna(raw):
                missing += 1
                continue
            year = int(column)
            if isinstance(raw, bool) or type(raw).__name__ == "bool_" or not isinstance(raw, numbers.Real):  # numpy scalars register as numbers.Real
                raise NormalizationError(f"{where}: ({country}, {year}) value {raw!r} is not a number (the legacy clean collection refused it too)")
            value = float(raw)
            if not math.isfinite(value):
                raise NormalizationError(f"{where}: ({country}, {year}) value {raw!r} is not finite")
            if (country, year) in seen:
                raise DuplicateObservationError(f"{dataset.code}: duplicate ({country}, {year}) in workbook {key!r} for {filters}")
            seen.add((country, year))
            observations.append(Observation(dataset.code, country, year, value, unit, _provenance(workbook, filters, indicator, name, raw)))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), missing)


def _provenance(workbook: WEFWorkbook, filters: dict[str, str], indicator: str, name: Any, raw: Any) -> dict[str, Any]:
    return {
        "source_organization": ORGANIZATION_CODE,
        "source_file": workbook.key,
        "source_edition": workbook.source.edition,
        "source_url": workbook.source.url,
        "source_sha256": workbook.sha256,
        "source_selection": dict(filters),
        "source_indicator_name": indicator,
        "source_country_name": name if isinstance(name, str) else None,
        "source_value": repr(raw.item() if hasattr(raw, "item") else raw),
    }
