"""International Energy Agency statistics endpoint: source client and pure
normalizer.

One request returns one IEA "indicator" for every area, product and year::

    https://api.iea.org/stats/indicator/<INDICATOR>

This is the interface the legacy collector used (``collect_iea_data``). It
answered without authentication when this adapter was written (2026-10-05),
but the IEA does not document it as a stable public API: treat it as a
fragile external interface. Replacing it with another IEA product needs its
own characterization and parity review. IEA data is the IEA's; nothing here
grants a right to redistribute it.

Canonical metadata names the indicator in ``query_code`` (``TESbySource``,
total energy supply by source) and, in ``dimensions``, the row fields the
legacy cleaner filtered on (for example ``{"product": "COAL"}``). The
adapter knows no indicator and no product by name.

The response is a JSON array of flat objects: ``country`` (ISO3 for
countries, a longer name for aggregates), ``year`` (text), ``value``,
``units``, ``product`` and labels.

:func:`normalize_iea_dataset` reproduces the legacy cleaner path
(``clean_iea_data_altnrg`` then ``filter_iea_data``):

* a row is kept when every field named in the dataset's ``dimensions`` has
  exactly the given value;
* geography is the row's ``country``. A code with no ISO 3166-1 alpha-3
  entry is skipped and reported; that drops every aggregate and any country
  the source names in full (``GUYANA``). No country-group restriction;
* a ``null`` value and any other falsy value are missing observations and
  are counted. The legacy truthiness test (``if not value``) also dropped a
  numeric zero; that is preserved;
* year is ``int(year)``; every year in the response is kept;
* the value is otherwise unchanged, as a float; the row's ``units`` must be
  the canonical unit of the dataset. A dataset whose legacy cleaner wrote
  its own unit label and rescaled the value declares the published unit
  and the factor in metadata (``source.published_unit``,
  ``source.value_multiplier``; :mod:`sspi.ingestion.units`): the row must
  carry the published unit, the value is multiplied and the canonical
  label written, as the legacy cleaner did (``IEA_TCO2EM``: MtCO2 times
  10**9, labelled "Tonnes C02 per inhabitant");
* the product, flow and their labels are preserved in provenance.

Two rows for one (country, year) are an error. The legacy cleaner had no
such check, and its scoring step raised on the duplicate instead.

Nothing here touches a database.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import pycountry

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.ingestion.units import conversion_provenance, expected_source_unit, stored_value, unit_expectation
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "IEA"
BASE_URL = "https://api.iea.org/stats/indicator/"
PROVENANCE_FIELDS = ("flow", "flowLabel", "product", "productLabel", "seriesLabel")


def indicator_key(dataset: Any) -> str:
    """The IEA indicator a dataset is requested as (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no IEA indicator (query_code) in canonical metadata")
    if not source.dimensions:
        raise NormalizationError(f"{dataset.code}: no row selection (dimensions) in canonical metadata; an IEA indicator holds several series")
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class IEAClient:
    """Synchronous client for the IEA statistics endpoint.

    ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, base_url: str = BASE_URL, timeout: float = 120.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.base_url = base_url

    def fetch_indicator(self, indicator: str) -> list[dict[str, Any]]:
        """Every row the endpoint holds for one indicator, in source order."""
        url = f"{self.base_url}{indicator}"
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"IEA request for indicator {indicator!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"IEA request for indicator {indicator!r} returned HTTP {response.status_code} ({url})")
        try:
            payload = response.json()
        except ValueError:
            raise SourceResponseError(f"IEA response for indicator {indicator!r} is not JSON") from None
        return read_rows(payload, indicator)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> IEAClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_rows(payload: Any, indicator: str) -> list[dict[str, Any]]:
    """The rows of one response: a non-empty JSON array of objects."""
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise SourceResponseError(f"IEA response for indicator {indicator!r} is not a JSON array of objects")
    if not payload:
        raise SourceResponseError(f"IEA returned no rows for indicator {indicator!r}; check the query code")
    return payload


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_iea_dataset(dataset: DatasetMetadata, rows: Sequence[Mapping[str, Any]]) -> NormalizationResult:
    """Convert the rows of the dataset's IEA indicator into canonical observations."""
    indicator = indicator_key(dataset)
    filters = dict(dataset.source.dimensions or {})
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise NormalizationError(f"{dataset.code}: row {index} is {type(row).__name__}, expected a mapping")
    selected = [row for row in rows if all(row.get(name) == wanted for name, wanted in filters.items())]
    if not selected:
        raise NormalizationError(f"{dataset.code}: dimensions {filters} matched no rows of IEA indicator {indicator}")

    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for row in selected:
        code = row.get("country")
        if not isinstance(code, str) or pycountry.countries.get(alpha_3=code) is None:
            skipped.setdefault((str(code), str(row.get("short", ""))))
            continue
        value = row.get("value")
        if not value:  # legacy `if not value`: null, and a numeric zero as well
            missing += 1
            continue
        where = f"{dataset.code} {code} {row.get('year')!r}"
        try:
            year = int(row["year"])
        except (KeyError, TypeError, ValueError):
            raise NormalizationError(f"{where}: year is not a year") from None
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise NormalizationError(f"{where}: value {value!r} is not numeric")
        try:
            number = float(value)
        except ValueError:
            raise NormalizationError(f"{where}: value {value!r} is not numeric") from None
        if not math.isfinite(number):
            raise NormalizationError(f"{where}: value {value!r} is not finite")
        if row.get("units") != expected_source_unit(dataset):
            raise NormalizationError(f"{where}: source unit {row.get('units')!r} disagrees with {unit_expectation(dataset)}")
        if (code, year) in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in IEA indicator {indicator}; canonical dimensions {filters} do not select one series")
        seen.add((code, year))
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_indicator": indicator,
            "source_area_name": row.get("short"),
            "source_dimensions": filters,
            **{name: row[name] for name in PROVENANCE_FIELDS if name in row},
            **conversion_provenance(dataset, row.get("units"), number),
        }
        observations.append(Observation(dataset.code, code, year, stored_value(dataset, number), dataset.unit, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)
