"""UN SDG Global Database: source client and pure normalizer.

Three separate responsibilities, none of which touches a database:

* ``UNSDGClient`` talks HTTP to the UN SDG PivotData endpoint and returns the
  raw pivot rows for one SDG indicator, across all pages.
* ``normalize_unsdg_dataset`` turns those rows into canonical ``Observation``
  records for one dataset from the metadata catalog. Pure: no I/O, no global
  state, input rows are not mutated.
* Persistence is the caller's job: ``Repository.replace_dataset(...)`` inside
  ``Database.transaction()``.

Source model (as observed on the live API and used by the legacy cleaner):
one pivot row per (series, geo area); ``years`` is a JSON string holding one
entry per year with ``value`` as a string (``""`` when missing) plus
attribute keys such as ``Nature`` and ``Observation Status`` on filled entries.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, NamedTuple

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.geo import m49_to_iso3
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "UNSDG"
PIVOT_DATA_URL = "https://unstats.un.org/SDGAPI/v1/sdg/Indicator/PivotData"

_YEAR = re.compile(r"^\[(\d{4})\]$")
_ROW_KEYS_NOT_DIMENSIONS = frozenset(
    {"goal", "target", "indicator", "series", "seriesDescription", "seriesCount", "geoAreaCode", "geoAreaName", "units", "years"}
)


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class UNSDGClient:
    """Synchronous client for the UN SDG PivotData endpoint.

    ``http`` may be injected (for tests, an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created with ``timeout`` and owned
    by this object. ``pause_between_pages`` mirrors the legacy collector's
    one-second politeness delay; ``sleep`` is injectable so tests do not wait.
    """

    def __init__(
        self,
        *,
        http: httpx.Client | None = None,
        timeout: float = 60.0,
        page_size: int = 500,
        pause_between_pages: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout)
        self._page_size = page_size
        self._pause = pause_between_pages
        self._sleep = sleep

    def fetch_indicator(self, indicator_code: str) -> list[dict[str, Any]]:
        """All pivot rows for one SDG indicator (for example ``"14.5.1"``)."""
        first = self._get_page(indicator_code, 1)
        total_elements, total_pages = first["totalElements"], first["totalPages"]
        if total_elements == 0:
            raise SourceResponseError(f"UNSDG returned no data for indicator {indicator_code!r}; check the query code")
        rows: list[dict[str, Any]] = list(first["data"])
        for page in range(2, total_pages + 1):
            if self._pause:
                self._sleep(self._pause)
            rows.extend(self._get_page(indicator_code, page)["data"])
        if len(rows) != total_elements:
            raise SourceResponseError(
                f"UNSDG indicator {indicator_code!r}: expected {total_elements} rows across {total_pages} page(s), received {len(rows)}"
            )
        return rows

    def _get_page(self, indicator_code: str, page: int) -> dict[str, Any]:
        params = {"indicator": indicator_code, "pageSize": self._page_size, "page": page}
        try:
            response = self.http.get(PIVOT_DATA_URL, params=params)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"UNSDG request failed for indicator {indicator_code!r} page {page}: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(
                f"UNSDG request for indicator {indicator_code!r} page {page} returned HTTP {response.status_code} ({response.url})"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceResponseError(f"UNSDG indicator {indicator_code!r} page {page}: response is not valid JSON") from exc
        return _validated_page(payload, indicator_code, page)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> UNSDGClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _validated_page(payload: Any, indicator_code: str, page: int) -> dict[str, Any]:
    where = f"UNSDG indicator {indicator_code!r} page {page}"
    if not isinstance(payload, dict):
        raise SourceResponseError(f"{where}: response body is not a JSON object")
    for key in ("totalElements", "totalPages", "pageNumber"):
        if not isinstance(payload.get(key), int) or isinstance(payload.get(key), bool):
            raise SourceResponseError(f"{where}: missing or non-integer {key!r}")
    if not isinstance(payload.get("data"), list):
        raise SourceResponseError(f"{where}: 'data' is not a list")
    if payload["pageNumber"] != page:
        raise SourceResponseError(f"{where}: server answered with page {payload['pageNumber']}")
    return payload


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


class NormalizationResult(NamedTuple):
    observations: list[Observation]
    skipped_areas: tuple[tuple[str, str], ...]  # (geo_area_code, geo_area_name) with no ISO3 mapping
    missing_values: int  # empty-value year entries dropped, mapped areas only


def normalize_unsdg_dataset(
    dataset: DatasetMetadata,
    rows: Sequence[Mapping[str, Any]],
    *,
    dimension_filters: Mapping[str, Any] | None = None,
) -> NormalizationResult:
    """Convert UN SDG pivot rows into canonical observations for ``dataset``.

    Keeps rows whose ``series`` equals ``dataset.source.organization_series_code``,
    applies the exact-match dimension filters declared in
    ``dataset.source.dimensions`` plus any passed in ``dimension_filters``
    (column == value) before looking for duplicates, maps M49 areas to ISO3,
    parses years and values, checks units against the canonical unit, and
    refuses any collision on (country_code, year). Applied dimensions are
    recorded in each observation's provenance as ``source_dimensions``.

    Empty and ``NaN`` values are missing observations and are counted, as the
    legacy extractor treated them. Other values that do not parse as finite
    numbers are errors. Flags such as ``Nature``
    and ``Observation Status`` are preserved in provenance and never used to
    filter: that reproduces the legacy behaviour and defers the methodology
    question.
    """
    series, indicator = _source_identifiers(dataset)
    filters = dict(dataset.source.dimensions or {})
    filters.update(dimension_filters or {})
    selected = _select_series(dataset, rows, series, indicator, filters)

    observations: list[Observation] = []
    seen: dict[tuple[str, int], Mapping[str, Any]] = {}
    duplicates: list[str] = []
    skipped: list[tuple[str, str]] = []
    missing = 0

    for row in selected:
        geo_code = str(row.get("geoAreaCode"))
        geo_name = str(row.get("geoAreaName"))
        country_code = m49_to_iso3(geo_code)
        if country_code is None:
            skipped.append((geo_code, geo_name))
            continue
        where = f"{dataset.code} series {series} area {geo_code} ({geo_name})"
        row_unit = row.get("units")
        if row_unit != dataset.unit:
            raise NormalizationError(f"{where}: source unit {row_unit!r} disagrees with canonical unit {dataset.unit!r}")
        for entry in _year_entries(row, where):
            year = _parse_year(entry.get("year"), where)
            raw_value = entry.get("value")
            if raw_value is None or raw_value == "" or _is_nan_literal(raw_value):
                missing += 1  # the legacy extractor dropped empty and NaN values alike
                continue
            value = _parse_value(raw_value, f"{where} year {year}")
            entry_unit = entry.get("Units")
            if entry_unit not in (None, "", dataset.unit):
                raise NormalizationError(f"{where} year {year}: entry unit {entry_unit!r} disagrees with canonical unit {dataset.unit!r}")
            multiplier = entry.get("UnitMultiplier")
            if multiplier not in (None, ""):
                raise NormalizationError(f"{where} year {year}: unit multiplier {multiplier!r} is not supported (no conversion rule)")
            key = (country_code, year)
            if key in seen:
                duplicates.append(f"{key} from areas {seen[key].get('geoAreaCode')} and {geo_code}; differing columns: {_differing_columns(seen[key], row)}")
                continue
            seen[key] = row
            observations.append(
                Observation(
                    dataset_code=dataset.code,
                    country_code=country_code,
                    year=year,
                    value=value,
                    unit=dataset.unit,
                    provenance=_provenance(indicator, series, geo_code, geo_name, entry, filters),
                )
            )

    if duplicates:
        raise DuplicateObservationError(
            f"{dataset.code}: {len(duplicates)} collision(s) on (country_code, year); pin the distinguishing dimension "
            f"with dimension_filters or give each slice its own dataset code:\n  - " + "\n  - ".join(duplicates)
        )
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(skipped), missing)


def _source_identifiers(dataset: Any) -> tuple[str, str]:
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no source series code (organization_series_code) in canonical metadata")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no source indicator (query_code) in canonical metadata")
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    return source.organization_series_code, source.query_code


def _select_series(
    dataset: DatasetMetadata, rows: Sequence[Mapping[str, Any]], series: str, indicator: str, filters: dict[str, Any]
) -> list[Mapping[str, Any]]:
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise NormalizationError(f"{dataset.code}: row {index} is {type(row).__name__}, expected a mapping")
    selected = [row for row in rows if row.get("series") == series]
    if not selected:
        present = sorted({str(row.get("series")) for row in rows})
        raise NormalizationError(f"{dataset.code}: no rows for series {series!r} (indicator {indicator}); series present: {present}")
    for column, wanted in filters.items():
        selected = [row for row in selected if row.get(column) == wanted]
        if not selected:
            raise NormalizationError(f"{dataset.code}: dimension filter {column}={wanted!r} matched no rows of series {series!r}")
    return selected


def _year_entries(row: Mapping[str, Any], where: str) -> list[Mapping[str, Any]]:
    years = row.get("years")
    if isinstance(years, str):
        try:
            years = json.loads(years)
        except ValueError:
            raise NormalizationError(f"{where}: 'years' is not valid JSON") from None
    if not isinstance(years, list) or not all(isinstance(e, Mapping) for e in years):
        raise NormalizationError(f"{where}: 'years' must be a list of entries")
    return years


def _parse_year(raw: Any, where: str) -> int:
    match = _YEAR.match(raw) if isinstance(raw, str) else None
    if match is None:
        raise NormalizationError(f"{where}: year {raw!r} is not a single '[YYYY]' year (ranges are not supported)")
    return int(match.group(1))


def _is_nan_literal(raw: Any) -> bool:
    """The source writes ``"NaN"`` for some missing values (seen on 6.4.1)."""
    try:
        return math.isnan(float(raw)) if isinstance(raw, (str, float)) and not isinstance(raw, bool) else False
    except ValueError:
        return False


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


def _provenance(indicator: str, series: str, geo_code: str, geo_name: str, entry: Mapping[str, Any], dimensions: Mapping[str, Any]) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "source_organization": ORGANIZATION_CODE,
        "source_indicator": indicator,
        "source_series": series,
        "source_geo_area_code": geo_code,
        "source_geo_area_name": geo_name,
        "nature": entry.get("Nature"),
        "observation_status": entry.get("Observation Status"),
    }
    if dimensions:
        provenance["source_dimensions"] = dict(dimensions)
    footnotes = entry.get("footnotes")
    if footnotes:
        provenance["footnotes"] = footnotes
    return provenance


def _differing_columns(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[str]:
    keys = (set(a) | set(b)) - _ROW_KEYS_NOT_DIMENSIONS
    return sorted(k for k in keys if a.get(k) != b.get(k))
