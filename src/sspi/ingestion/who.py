"""WHO Global Health Observatory (GHO) OData API: source client and pure
normalizer.

One request path serves any GHO indicator, every area and year::

    https://ghoapi.azureedge.net/api/<INDICATOR CODE>

the request the legacy collector (``collect_who_data`` in
``api/datasource/who.py``) made. Canonical metadata names the GHO indicator
requested in ``query_code`` and the series kept in
``organization_series_code`` (the same code; the legacy collector recorded
both as the indicator code). Optional exact-match filters on the response's
own fields (``Dim1``, ``Dim2``, ``Dim3``, ``DataSourceDim``) are declared in
``source.dimensions``.

The response is an OData v4 JSON object, ``{"@odata.context": ...,
"value": [rows]}``. Each row carries ``IndicatorCode``, ``SpatialDimType``
and ``SpatialDim`` (for a ``COUNTRY`` row an ISO3 code), ``TimeDimType`` and
``TimeDim`` (the year), the disaggregation fields ``Dim1``-``Dim3`` with
their types, ``DataSourceDim``, ``Value`` (a display string, rounded),
``NumericValue`` (the number), ``Low``/``High``, ``Comments`` and ``Date``
(when WHO last changed the row). No unit is served; the unit is in the
indicator's name. If the service pages a response it adds
``@odata.nextLink``, which :class:`WHOClient` follows.

WHO announced that this OData implementation would be deprecated near the
end of 2025 in favour of a new one with different field names. It still
answered on 2026-10-18. The base URL is a client parameter; nothing here
switches to another API by itself.

:func:`normalize_who_dataset` reproduces the legacy cleaner
(``clean_who_data``), in its order:

* geography: only rows whose ``SpatialDimType`` is ``COUNTRY`` are kept;
  ``REGION``, ``WORLDBANKINCOMEGROUP``, ``UNREGION``, ``GLOBAL`` and any
  other area type are skipped and reported. ``SpatialDim`` is the country
  code as served: the legacy cleaner did not check it against ISO 3166, so
  neither does this one; a code that cannot be stored (not three capital
  letters) is an error;
* a row whose ``Value`` is ``"No data"`` is a missing observation and is
  counted;
* the declared dimension filters, field == value, as the legacy
  ``dimension_values`` argument;
* the value is ``NumericValue`` unchanged (never the rounded ``Value``
  string); a reported zero is kept. A row with no ``NumericValue`` and a
  ``Value`` other than ``"No data"`` is an error (legacy ``float(None)``
  raised), as is a non-finite number;
* year is ``int(TimeDim)``; every year is kept; the unit is the canonical
  unit of the dataset (the legacy cleaner wrote a literal per dataset);
* two rows for one (country, year) after the filters are an error (legacy
  stored both and its scoring step raised on the duplicate).

Disaggregation fields, the data source, the confidence bounds, WHO's
comment and change date, the display value, the request URL and the
OData context are kept in provenance and never used to filter.

Nothing here touches a database.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "WHO"
BASE_URL = "https://ghoapi.azureedge.net/api/"
COUNTRY = "COUNTRY"
NO_DATA = "No data"
FILTERABLE_FIELDS = ("Dim1", "Dim2", "Dim3", "DataSourceDim")
MAX_PAGES = 1000  # a guard against a nextLink cycle, far above any GHO indicator
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")
_PROVENANCE_FIELDS = (  # source field -> provenance key, recorded when present
    ("SpatialDimType", "spatial_dim_type"),
    ("ParentLocationCode", "parent_location_code"),
    ("TimeDimType", "time_dim_type"),
    ("Dim1Type", "dim1_type"),
    ("Dim1", "dim1"),
    ("Dim2Type", "dim2_type"),
    ("Dim2", "dim2"),
    ("Dim3Type", "dim3_type"),
    ("Dim3", "dim3"),
    ("DataSourceDimType", "data_source_dim_type"),
    ("DataSourceDim", "data_source_dim"),
    ("Value", "display_value"),
    ("Low", "low"),
    ("High", "high"),
    ("Comments", "comments"),
    ("Date", "source_date"),
)


def indicator_key(dataset: Any) -> str:
    """The GHO indicator a dataset is requested as (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no GHO indicator (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no GHO series code (organization_series_code) in canonical metadata")
    unknown = sorted(set(source.dimensions or {}) - set(FILTERABLE_FIELDS))
    if unknown:
        raise NormalizationError(f"{dataset.code}: dimension filters {unknown} are not GHO row fields; filterable: {list(FILTERABLE_FIELDS)}")
    return source.query_code


@dataclass(frozen=True, slots=True)
class GHOIndicatorData:
    """One indicator's rows as served by the GHO OData API."""

    indicator: str
    url: str  # the request for the first page
    odata_context: str | None
    pages: int
    rows: tuple[Mapping[str, Any], ...] = field(default=())


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class WHOClient:
    """Synchronous client for the GHO OData API.

    ``base_url`` selects the service (default: the documented GHO OData
    API). ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, base_url: str = BASE_URL, timeout: float = 120.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"

    def fetch_indicator(self, indicator: str) -> GHOIndicatorData:
        """Every row the service holds for one indicator, every area and year, in API order, all pages."""
        url = f"{self.base_url}{indicator}"
        payload = self._get(url, f"indicator {indicator!r}")
        rows, context, next_link = read_page(payload, indicator)
        pages = 1
        while next_link is not None:
            pages += 1
            if pages > MAX_PAGES:
                raise SourceResponseError(f"GHO response for indicator {indicator!r} exceeded {MAX_PAGES} pages")
            page_rows, _, next_link = read_page(self._get(next_link, f"indicator {indicator!r} page {pages}"), indicator)
            rows.extend(page_rows)
        return GHOIndicatorData(indicator, url, context, pages, tuple(rows))

    def _get(self, url: str, what: str) -> Any:
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"GHO request for {what} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"GHO request for {what} returned HTTP {response.status_code} ({url}); the service answers 404 for an unknown indicator code")
        try:
            return response.json()
        except ValueError:
            raise SourceResponseError(f"GHO response for {what} is not JSON") from None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> WHOClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_page(payload: Any, indicator: str) -> tuple[list[Mapping[str, Any]], str | None, str | None]:
    """(rows, ``@odata.context``, ``@odata.nextLink``) of one OData page."""
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise SourceResponseError(f"GHO response for indicator {indicator!r} has no 'value' list")
    rows = payload["value"]
    if any(not isinstance(row, dict) for row in rows):
        raise SourceResponseError(f"GHO response for indicator {indicator!r} holds rows that are not objects")
    next_link = payload.get("@odata.nextLink")
    if next_link is not None and not isinstance(next_link, str):
        raise SourceResponseError(f"GHO response for indicator {indicator!r} has a malformed @odata.nextLink: {next_link!r}")
    return list(rows), payload.get("@odata.context"), next_link


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_who_dataset(dataset: DatasetMetadata, data: GHOIndicatorData) -> NormalizationResult:
    """Convert one indicator's GHO rows into canonical observations for ``dataset``."""
    indicator_key(dataset)
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    series = dataset.source.organization_series_code
    filters = dict(dataset.source.dimensions or {})
    observations: list[Observation] = []
    seen: dict[tuple[str, int], Mapping[str, Any]] = {}
    duplicates: list[str] = []
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for position, row in enumerate(data.rows):
        where = f"{dataset.code} row {position}"
        if row.get("IndicatorCode") != series:
            raise NormalizationError(f"{where}: row belongs to indicator {row.get('IndicatorCode')!r}, not {series!r}")
        if row.get("SpatialDimType") != COUNTRY:
            skipped.setdefault((str(row.get("SpatialDim")), str(row.get("SpatialDimType"))))
            continue
        if row.get("Value") == NO_DATA:
            if all(row.get(column) == wanted for column, wanted in filters.items()):
                missing += 1
            continue
        if any(row.get(column) != wanted for column, wanted in filters.items()):
            continue
        country = row.get("SpatialDim")
        if not isinstance(country, str) or not _STORABLE_COUNTRY.match(country):
            raise NormalizationError(f"{where}: country code {country!r} cannot be stored (three capital letters required)")
        value = row.get("NumericValue")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NormalizationError(f"{where} ({country}): NumericValue {value!r} is not a number and Value {row.get('Value')!r} is not {NO_DATA!r} (the legacy cleaner raised here)")
        value = float(value)
        if not math.isfinite(value):
            raise NormalizationError(f"{where} ({country}): NumericValue {value!r} is not finite")
        try:
            year = int(row.get("TimeDim"))
        except (TypeError, ValueError):
            raise NormalizationError(f"{where} ({country}): TimeDim {row.get('TimeDim')!r} is not a year (TimeDimType {row.get('TimeDimType')!r})") from None
        key = (country, year)
        if key in seen:
            differing = [c for c in sorted(set(row) | set(seen[key])) if c not in ("Id", "Value", "NumericValue", "Low", "High", "Comments", "Date") and row.get(c) != seen[key].get(c)]
            duplicates.append(f"{key}; differing fields: {differing}")
            continue
        seen[key] = row
        observations.append(Observation(dataset.code, country, year, value, dataset.unit, _provenance(data, row, filters)))
    if duplicates:
        raise DuplicateObservationError(
            f"{dataset.code}: {len(duplicates)} collision(s) on (country_code, year); pin the distinguishing field "
            f"({', '.join(FILTERABLE_FIELDS)}) in source.dimensions:\n  - " + "\n  - ".join(duplicates)
        )
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(skipped), missing)


def _provenance(data: GHOIndicatorData, row: Mapping[str, Any], filters: Mapping[str, Any]) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "source_organization": ORGANIZATION_CODE,
        "source_indicator": data.indicator,
        "source_url": data.url,
    }
    if data.odata_context is not None:
        provenance["odata_context"] = data.odata_context
    for source_field, key in _PROVENANCE_FIELDS:
        if row.get(source_field) is not None:
            provenance[key] = row[source_field]
    if filters:
        provenance["source_dimensions"] = dict(filters)
    return provenance
