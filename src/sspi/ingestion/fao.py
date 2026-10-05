"""FAOSTAT bulk download: source client and pure normalizer.

The legacy collector queried the FAOSTAT JSON API per (domain, element,
item) with ``area_cs=ISO3``. That API now requires an authenticated session,
so this adapter reads the official bulk-download artifact for a domain
instead: one public zip per domain holding the whole domain as a normalized
CSV, one row per (area, item, element, year). One download serves every
dataset drawn from the domain; the runner fetches each domain once.

Canonical metadata identifies a dataset's series the way the legacy
collector did, as ``query_code = "Domain=RL;Element=5110;Item=6717"``;
:func:`source_filters` parses it. The normalizer keeps the rows with that
element and item and applies the legacy cleaner's semantics
(``format_fao_data_series``):

* geography: the bulk file carries UN M49 codes, not ISO3; areas are mapped
  with the same M49 -> ISO3 rule as every other source and anything without
  an ISO 3166-1 entry (regional aggregates, FAO's broader "China" grouping
  M49 159, historical "Belgium-Luxembourg" 058) is skipped and reported, as
  the legacy filter dropped the API's non-ISO3 area codes. "China, mainland"
  (M49 156) is CHN. No names are matched;
* an empty value is a missing observation and is counted; every other value
  is parsed as a number, zero included (the legacy API returned values as
  strings, which its truthiness test kept);
* values and the source unit are preserved; the unit must equal the
  canonical unit;
* flags (official / estimated / imputed by FAO) are preserved in provenance
  and never used to filter, as in legacy.

Nothing here touches a database.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.geo import m49_to_iso3
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "UNFAO"
BULK_BASE_URL = "https://bulks-faostat.fao.org/production/"
# FAOSTAT domain code -> bulk artifact (normalized layout) under BULK_BASE_URL.
DOMAIN_ARTIFACTS: dict[str, str] = {
    "RL": "Inputs_LandUse_E_All_Data_(Normalized).zip",
}
REQUIRED_COLUMNS = ("Area Code", "Area Code (M49)", "Area", "Item Code", "Item", "Element Code", "Element", "Year", "Unit", "Value", "Flag")

_QUERY = re.compile(r"^Domain=(?P<domain>[A-Z0-9_]+);Element=(?P<element>\d+);Item=(?P<item>\d+)$")


class SourceFilters(NamedTuple):
    domain: str
    element_code: str
    item_code: str


def source_filters(dataset: Any) -> SourceFilters:
    """The (domain, element, item) selection encoded in a dataset's ``query_code``."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    match = _QUERY.match(source.query_code or "")
    if match is None:
        raise NormalizationError(f"{dataset.code}: query_code {source.query_code!r} is not of the form 'Domain=RL;Element=5110;Item=6717'")
    return SourceFilters(match["domain"], match["element"], match["item"])


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class FAOBulkClient:
    """Synchronous client for the FAOSTAT bulk-download artifacts.

    ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, timeout: float = 300.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_domain(self, domain: str) -> list[dict[str, str]]:
        """Every row of the domain's normalized bulk CSV, as dicts keyed by the file's header."""
        try:
            artifact = DOMAIN_ARTIFACTS[domain]
        except KeyError:
            raise SourceRequestError(f"no FAOSTAT bulk artifact is registered for domain {domain!r}; known: {sorted(DOMAIN_ARTIFACTS)}") from None
        url = BULK_BASE_URL + artifact
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"FAOSTAT bulk request for domain {domain!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"FAOSTAT bulk request for domain {domain!r} returned HTTP {response.status_code} ({url})")
        return read_bulk_archive(response.content, domain)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> FAOBulkClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_bulk_archive(content: bytes, domain: str) -> list[dict[str, str]]:
    """Parse the ``*_All_Data_(Normalized).csv`` member of a bulk zip."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise SourceResponseError(f"FAOSTAT bulk artifact for domain {domain!r} is not a zip file") from None
    with archive:
        members = [name for name in archive.namelist() if name.endswith("_All_Data_(Normalized).csv")]
        if len(members) != 1:
            raise SourceResponseError(f"FAOSTAT bulk artifact for domain {domain!r}: expected one '*_All_Data_(Normalized).csv' member, found {members}")
        text = archive.read(members[0]).decode("utf-8-sig")
    return read_bulk_csv(text, domain)


def read_bulk_csv(text: str, domain: str = "") -> list[dict[str, str]]:
    """Rows of a normalized bulk CSV; the header must carry every column the normalizer reads."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or ())]
    if missing:
        raise SourceResponseError(f"FAOSTAT bulk CSV {domain!r}: header lacks columns {missing}; found {reader.fieldnames}")
    return list(reader)


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_fao_dataset(dataset: DatasetMetadata, rows: Sequence[Mapping[str, Any]]) -> NormalizationResult:
    """Convert normalized bulk rows into canonical observations for ``dataset``.

    Keeps the rows whose element and item codes are the ones in the
    dataset's ``query_code``, maps M49 areas to ISO3 (skipping and reporting
    the rest), checks the unit against the canonical one, counts empty values
    as missing and refuses any collision on (country_code, year).
    """
    filters = source_filters(dataset)
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    selected = _select(dataset, rows, filters)

    observations: list[Observation] = []
    seen: dict[tuple[str, int], Mapping[str, Any]] = {}
    duplicates: list[str] = []
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for row in selected:
        m49 = str(row.get("Area Code (M49)", "")).lstrip("'")
        country_code = m49_to_iso3(m49)
        if country_code is None:
            skipped.setdefault((str(row.get("Area Code")), str(row.get("Area"))))
            continue
        where = f"{dataset.code} area {row.get('Area Code')} ({row.get('Area')})"
        unit = row.get("Unit")
        if unit != dataset.unit:
            raise NormalizationError(f"{where}: source unit {unit!r} disagrees with canonical unit {dataset.unit!r}")
        year = _parse_year(row.get("Year"), where)
        raw_value = row.get("Value")
        if raw_value is None or raw_value == "":
            missing += 1
            continue
        value = _parse_value(raw_value, f"{where} year {year}")
        key = (country_code, year)
        if key in seen:
            duplicates.append(f"{key} from areas {seen[key].get('Area Code')} and {row.get('Area Code')}")
            continue
        seen[key] = row
        observations.append(Observation(dataset.code, country_code, year, value, dataset.unit, _provenance(filters, row, m49)))

    if duplicates:
        raise DuplicateObservationError(f"{dataset.code}: {len(duplicates)} collision(s) on (country_code, year):\n  - " + "\n  - ".join(duplicates))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(skipped), missing)


def _select(dataset: DatasetMetadata, rows: Sequence[Mapping[str, Any]], filters: SourceFilters) -> list[Mapping[str, Any]]:
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise NormalizationError(f"{dataset.code}: row {index} is {type(row).__name__}, expected a mapping")
    selected = [row for row in rows if str(row.get("Element Code")) == filters.element_code and str(row.get("Item Code")) == filters.item_code]
    if not selected:
        present = sorted({(str(row.get("Element Code")), str(row.get("Item Code"))) for row in rows})
        raise NormalizationError(
            f"{dataset.code}: no rows for element {filters.element_code} and item {filters.item_code} in domain {filters.domain}; (element, item) pairs present: {present}"
        )
    return selected


def _parse_year(raw: Any, where: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, str)) or not re.fullmatch(r"\d{4}", str(raw)):
        raise NormalizationError(f"{where}: year {raw!r} is not a four-digit year")
    return int(raw)


def _parse_value(raw: Any, where: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise NormalizationError(f"{where}: value {raw!r} is not numeric")
    try:
        value = float(raw)
    except ValueError:
        raise NormalizationError(f"{where}: value {raw!r} is not numeric") from None
    if not math.isfinite(value):
        raise NormalizationError(f"{where}: value {raw!r} is not finite")
    return value


def _provenance(filters: SourceFilters, row: Mapping[str, Any], m49: str) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "source_organization": ORGANIZATION_CODE,
        "source_domain": filters.domain,
        "source_element_code": filters.element_code,
        "source_element": row.get("Element"),
        "source_item_code": filters.item_code,
        "source_item": row.get("Item"),
        "source_area_code": str(row.get("Area Code")),
        "source_m49_code": m49,
        "source_area_name": row.get("Area"),
        "flag": row.get("Flag") or None,
    }
    if row.get("Note"):
        provenance["note"] = row["Note"]
    return provenance
