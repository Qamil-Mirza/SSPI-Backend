"""ILOSTAT SDMX API: source client and pure normalizer.

One request serves one dataflow, optionally narrowed by an SDMX key::

    https://sdmx.ilo.org/rest/data/<DATAFLOW>[/<KEY>]?format=jsondata

Canonical metadata names the request in ``query_code``, in the legacy form
``Indicator=<DATAFLOW>;Parameters=<KEY>`` (the key may be empty), the
dataflow again in ``organization_series_code``, and in ``dimensions`` the
series dimensions the legacy cleaner filtered on (for example
``{"SEX": "SEX_T", "AGE": "AGE_YTHADULT_Y15-64"}``).

The legacy collectors also sent a time window that no metadata file records;
it is kept in :data:`REQUEST_PERIODS`, by query code. A query with no entry
is requested without a window.

The response is SDMX-JSON: series keyed by dimension-value indexes
(``"0:0:0"``), each holding observations keyed by the index of the time
period, each observation an array whose first element is the value and whose
other elements index the observation attributes.

:func:`normalize_ilo_dataset` reproduces the legacy cleaner path
(``parse_sdmx_json_to_tabular`` then ``filter_ilo``):

* a series is kept when every dimension named in the dataset's
  ``dimensions`` has exactly the given value;
* geography is ``REF_AREA`` as the source codes it. A code containing a
  digit is an ILO regional or income aggregate (``X01``): skipped and
  reported. Every other code is kept unchanged, as in legacy, with no ISO
  check and no country-group restriction, so the few ILO codes that are not
  ISO 3166-1 (``KOS`` Kosovo, ``ANT`` Netherlands Antilles) are stored as
  they are;
* a ``null`` observation value is a missing observation and is counted. A
  numeric zero is kept (the legacy test was ``is not None``);
* year is ``int(TIME_PERIOD)``; every year in the response is kept;
* the value is otherwise unchanged and the unit is the canonical unit of the
  dataset, which is the label the legacy cleaner assigned, not the source's
  own ``UNIT_MEASURE``;
* series dimensions, series attributes and the non-empty observation
  attributes (source, notes, observation status) are preserved in provenance
  under their SDMX ids and never used to filter.

Where the legacy code silently dropped a row (a period that is not a year, a
value that is not a number) this module raises instead; neither occurs in an
annual dataflow.

Nothing here touches a database.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "ILO"
BASE_URL = "https://sdmx.ilo.org/rest/data/"
AREA_DIMENSION = "REF_AREA"
TIME_DIMENSION = "TIME_PERIOD"

# The time window each legacy collector sent, by canonical query code.
REQUEST_PERIODS: dict[str, tuple[tuple[str, str], ...]] = {
    "Indicator=DF_ILR_CBCT_NOC_RT;Parameters=": (("startPeriod", "1990-01-01"), ("endPeriod", "2024-12-31")),
    "Indicator=DF_EMP_DWAP_SEX_AGE_RT;Parameters=.A..SEX_T.AGE_YTHADULT_Y15-64": (("startPeriod", "2000"),),
}


def parse_query(query_code: str) -> tuple[str, str]:
    """(dataflow, SDMX key) from a canonical ``Indicator=<DATAFLOW>;Parameters=<KEY>`` query code."""
    head, separator, key = query_code.partition(";Parameters=")
    if not separator or not head.startswith("Indicator=") or not head[len("Indicator=") :]:
        raise NormalizationError(f"ILO query code {query_code!r} is not of the form 'Indicator=<DATAFLOW>;Parameters=<KEY>'")
    return head[len("Indicator=") :], key


def query_key(dataset: Any) -> str:
    """The ILO request a dataset is fetched with (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no ILO request (query_code) in canonical metadata")
    dataflow, _ = parse_query(source.query_code)
    if source.organization_series_code != dataflow:
        raise NormalizationError(
            f"{dataset.code}: canonical metadata names dataflow {source.organization_series_code!r} as the series but requests {dataflow!r}"
        )
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class ILOClient:
    """Synchronous client for the ILOSTAT SDMX REST API.

    ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, base_url: str = BASE_URL, timeout: float = 300.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.base_url = base_url

    def fetch_query(self, query_code: str) -> dict[str, Any]:
        """The SDMX-JSON message for one canonical query code, with its legacy time window."""
        dataflow, key = parse_query(query_code)
        url = f"{self.base_url}{dataflow}" + (f"/{key}" if key else "")
        params = {"format": "jsondata", **dict(REQUEST_PERIODS.get(query_code, ()))}
        try:
            response = self.http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"ILO request for {query_code!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"ILO request for {query_code!r} returned HTTP {response.status_code} ({url})")
        try:
            payload = response.json()
        except ValueError:
            raise SourceResponseError(f"ILO response for {query_code!r} is not JSON") from None
        read_message(payload, query_code)
        return payload

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> ILOClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_message(payload: Any, what: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(structure, data sets) of one SDMX-JSON data message."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("dataSets"), list) or not isinstance(data.get("structures"), list) or not data["structures"]:
        raise SourceResponseError(f"ILO response for {what} is not an SDMX-JSON data message (no data.dataSets / data.structures)")
    return data["structures"][0], data["dataSets"]


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def _attribute_ids(definitions: list[dict[str, Any]], indexes: list[Any], where: str) -> dict[str, str]:
    """Attribute id -> its value, for the attributes that have one: the
    value's code where the attribute is coded (``OBS_STATUS``), its text
    where it is free text (``SOURCE``, the notes)."""
    found: dict[str, str] = {}
    for definition, index in zip(definitions, indexes):
        if index is None:
            continue
        try:
            value = definition["values"][index]
            found[definition["id"]] = value["id"] if "id" in value else value["value"]
        except (IndexError, KeyError, TypeError):
            raise NormalizationError(f"{where}: attribute {definition.get('id')!r} has no value at index {index!r}") from None
    return found


def normalize_ilo_dataset(dataset: DatasetMetadata, payload: Mapping[str, Any]) -> NormalizationResult:
    """Convert one SDMX-JSON message for the dataset's request into canonical observations."""
    query_code = query_key(dataset)
    dataflow = dataset.source.organization_series_code
    structure, data_sets = read_message(payload, dataset.code)
    try:
        series_dimensions = sorted(structure["dimensions"]["series"], key=lambda d: d["keyPosition"])
        dimension_ids = [d["id"] for d in series_dimensions]
        periods = next(d for d in structure["dimensions"]["observation"] if d["id"] == TIME_DIMENSION)["values"]
        attributes = structure.get("attributes") or {}
        series_attributes, observation_attributes = attributes.get("series") or [], attributes.get("observation") or []
    except (KeyError, TypeError, StopIteration):
        raise NormalizationError(f"{dataset.code}: SDMX structure has no usable series dimensions or {TIME_DIMENSION} dimension") from None
    if AREA_DIMENSION not in dimension_ids:
        raise NormalizationError(f"{dataset.code}: dataflow {dataflow} has no {AREA_DIMENSION} dimension")
    filters = dict(dataset.source.dimensions or {})
    unknown = sorted(set(filters) - set(dimension_ids))
    if unknown:
        raise NormalizationError(f"{dataset.code}: canonical dimensions {unknown} are not series dimensions of dataflow {dataflow} ({dimension_ids})")

    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for data_set in data_sets:
        for series_key, series in (data_set.get("series") or {}).items():
            where = f"{dataset.code} series {series_key}"
            try:
                values = [dimension["values"][int(index)] for dimension, index in zip(series_dimensions, series_key.split(":"), strict=True)]
            except (IndexError, KeyError, TypeError, ValueError):
                raise NormalizationError(f"{where}: series key does not match the dataflow's dimensions {dimension_ids}") from None
            key = {dimension_id: value["id"] for dimension_id, value in zip(dimension_ids, values)}
            if any(key[name] != wanted for name, wanted in filters.items()):
                continue
            code = key[AREA_DIMENSION]
            if any(character.isdigit() for character in code):
                skipped.setdefault((code, str(values[dimension_ids.index(AREA_DIMENSION)].get("name", ""))))
                continue
            series_provenance = {name: value for name, value in key.items() if name != AREA_DIMENSION}
            series_provenance.update(_attribute_ids(series_attributes, series.get("attributes") or [], where))
            for period_index, cells in (series.get("observations") or {}).items():
                if not cells or cells[0] is None:
                    missing += 1
                    continue
                try:
                    period = periods[int(period_index)]["id"]
                    year = int(period)
                except (IndexError, KeyError, TypeError, ValueError):
                    raise NormalizationError(f"{where}: observation {period_index!r} has no {TIME_DIMENSION} that is a year") from None
                try:
                    number = float(cells[0])
                except (TypeError, ValueError):
                    raise NormalizationError(f"{where} {period}: value {cells[0]!r} is not numeric") from None
                if not math.isfinite(number):
                    raise NormalizationError(f"{where} {period}: value {cells[0]!r} is not finite")
                if (code, year) in seen:
                    raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in ILO dataflow {dataflow}; canonical dimensions {filters or None} do not select one series")
                seen.add((code, year))
                provenance = {
                    "source_organization": ORGANIZATION_CODE,
                    "source_dataflow": dataflow,
                    "source_query": query_code,
                    "source_area_name": values[dimension_ids.index(AREA_DIMENSION)].get("name"),
                    **series_provenance,
                    **_attribute_ids(observation_attributes, list(cells[1:]), f"{where} {period}"),
                }
                observations.append(Observation(dataset.code, code, year, number, dataset.unit, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)
