"""World Bank Indicators API: source client and pure normalizer.

One request path serves any World Bank indicator for every economy and
year::

    https://api.worldbank.org/v2/country/all/indicator/<CODE>?format=json

Canonical metadata names the indicator requested in ``query_code`` and the
series kept in ``organization_series_code`` (the same code for a plain
indicator such as ``SI.POV.GINI``). The response is paged JSON,
``[page metadata, [rows]]``; each row carries the indicator, the economy
(``country.id`` is the API's two-character id, ``countryiso3code`` the ISO3
code, empty for some aggregates), ``date`` and ``value``.

:func:`normalize_worldbank_dataset` reproduces the legacy cleaner
(``clean_wb_data``):

* geography: ``countryiso3code``, or ``country.id`` when that is empty; a
  code with no ISO 3166-1 alpha-3 entry is skipped and reported. That drops
  every aggregate (World, income groups, regions) and Kosovo (``XKX``,
  not an ISO code). No country-group restriction: every recognized economy
  is kept, as in legacy;
* a ``null`` value, the string ``"NaN"`` and any other falsy value are
  missing observations and are counted. The legacy truthiness test also
  dropped a numeric zero; that is preserved and applies to every World Bank
  dataset, since they all shared the cleaner;
* year is ``int(date)``; every year the API returns is kept;
* the value is otherwise unchanged, and the unit is the canonical unit of
  the dataset (the API's own ``unit`` field is empty for most indicators and
  is kept in provenance);
* ``obs_status`` and ``decimal`` are preserved in provenance and never used
  to filter.

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
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "WB"
BASE_URL = "https://api.worldbank.org/v2/country/all/indicator/"
PER_PAGE = 10000


def indicator_key(dataset: Any) -> str:
    """The World Bank indicator a dataset is requested as (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no World Bank indicator (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no World Bank series code (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class WorldBankClient:
    """Synchronous client for the World Bank Indicators API.

    ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, base_url: str = BASE_URL, per_page: int = PER_PAGE, timeout: float = 120.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.base_url = base_url
        self.per_page = per_page

    def fetch_indicator(self, indicator: str) -> list[dict[str, Any]]:
        """Every row the API holds for one indicator, all economies and years, in API order."""
        rows: list[dict[str, Any]] = []
        page, pages = 1, 1
        while page <= pages:
            metadata, page_rows = self._page(indicator, page)
            try:
                pages = int(metadata["pages"])
            except (KeyError, TypeError, ValueError):
                raise SourceResponseError(f"World Bank response for {indicator!r} page {page} has no usable page count: {metadata!r}") from None
            rows.extend(page_rows)
            page += 1
        return rows

    def _page(self, indicator: str, page: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        url = f"{self.base_url}{indicator}"
        try:
            response = self.http.get(url, params={"format": "json", "per_page": self.per_page, "page": page})
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"World Bank request for indicator {indicator!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"World Bank request for indicator {indicator!r} returned HTTP {response.status_code} ({url})")
        try:
            payload = response.json()
        except ValueError:
            raise SourceResponseError(f"World Bank response for indicator {indicator!r} is not JSON") from None
        return read_page(payload, indicator)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> WorldBankClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_page(payload: Any, indicator: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(page metadata, rows) from one API response body, ``[metadata, rows]``.

    The API reports an unknown indicator as a one-element list holding a
    ``message``; a known indicator with no data has ``null`` rows.
    """
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise SourceResponseError(f"World Bank response for indicator {indicator!r} is not a [metadata, rows] list")
    if "message" in payload[0]:
        raise SourceResponseError(f"World Bank API rejected indicator {indicator!r}: {payload[0]['message']}")
    rows = payload[1] if len(payload) > 1 else None
    if rows is None:
        return payload[0], []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise SourceResponseError(f"World Bank response for indicator {indicator!r} holds rows that are not objects")
    return payload[0], rows


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_worldbank_dataset(dataset: DatasetMetadata, rows: Sequence[Mapping[str, Any]]) -> NormalizationResult:
    """Convert API rows for the dataset's indicator into canonical observations."""
    indicator_key(dataset)
    series = dataset.source.organization_series_code
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for position, row in enumerate(rows):
        where = f"{dataset.code} row {position}"
        indicator = row.get("indicator") or {}
        if indicator.get("id") != series:
            raise NormalizationError(f"{where}: row belongs to indicator {indicator.get('id')!r}, not {series!r}")
        economy = row.get("country") or {}
        code = row.get("countryiso3code") or economy.get("id")
        if not code:
            continue  # legacy: no ISO3 code and no country id, row ignored
        if pycountry.countries.get(alpha_3=code) is None:
            skipped.setdefault((str(code), str(economy.get("value", ""))))
            continue
        value = row.get("value")
        if value is None or value == "NaN" or not value:
            missing += 1
            continue
        try:
            year = int(str(row.get("date")))
        except ValueError:
            raise NormalizationError(f"{where}: date {row.get('date')!r} is not a year") from None
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise NormalizationError(f"{where}: value {value!r} is not numeric") from None
        if not math.isfinite(number):
            raise NormalizationError(f"{where}: value {value!r} is not finite")
        key = (code, year)
        if key in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in World Bank rows for {series}")
        seen.add(key)
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_indicator": series,
            "description": indicator.get("value"),
            "source_country_id": economy.get("id"),
            "source_country_name": economy.get("value"),
            "source_unit": row.get("unit"),
            "obs_status": row.get("obs_status"),
            "decimal": row.get("decimal"),
        }
        observations.append(Observation(dataset.code, code, year, number, dataset.unit, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)
