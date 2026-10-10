"""UNESCO Institute for Statistics (UIS) Data API: source client and pure
normalizer.

One request path serves any UIS indicator for every national area and
year::

    https://api.uis.unesco.org/api/public/data/indicators?indicator=<CODE>&version=<RELEASE>

the request the legacy collector (``collect_uis_data``) made, plus the
release. Canonical metadata names the indicator requested in
``query_code`` and the series kept in ``organization_series_code`` (the
same code: ``NERT.1.CP`` for ``UIS_ENRPRI``, ``NERT.2.CP`` for
``UIS_ENRSEC``). The response is one JSON object,
``{"hints": [...], "records": [...], "indicatorMetadata": [...]}``; each
record carries ``indicatorId``, ``geoUnit`` (an ISO3 code for a national
area), ``year``, ``value``, ``magnitude`` and ``qualifier``. Asked for an
indicator only, the API returns national areas only. It returns at most
100,000 records per request and does not page.

Releases. The API serves a versioned database. The legacy request named no
version, so it read whatever release was the default at the time. By
default :class:`UISClient` does the same, but first asks the API which
release is the default (``/versions/default``) and then requests the data
of that release explicitly, so the release recorded in provenance is
certainly the one the data came from. A specific release can be selected
with ``UISClient(version=...)`` (the API's own ``version`` parameter; the
list is at ``/versions``). Successive releases revise past values, so the
same methodology can give different scores after a new release.

:func:`normalize_uis_dataset` reproduces the legacy cleaner
(``clean_uis_data``):

* geography: ``geoUnit``; a code with no ISO 3166-1 alpha-3 entry is
  skipped and reported (the source names no area, so the reported name is
  empty). No country-group restriction;
* year is ``int(year)``; every year the API returns is kept;
* a ``null`` value, the string ``"NaN"`` and any other falsy value are
  missing observations and are counted. The legacy truthiness test also
  dropped a numeric zero; that is preserved;
* the value is otherwise unchanged; the unit is the canonical unit of the
  dataset (the legacy cleaner wrote it as a literal, ``Percent``);
* a value that is not a finite number is an error (legacy stored the string
  ``"NaN"`` instead); two records for one (area, year) are an error (legacy
  had no check, and its scoring step raised on the duplicate instead);
* ``qualifier``, ``magnitude`` and the release are kept in provenance and
  never used to filter.

Nothing here touches a database.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
import pycountry

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "UIS"
BASE_URL = "https://api.uis.unesco.org/api/public/"


def indicator_key(dataset: Any) -> str:
    """The UIS indicator a dataset is requested as (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no UIS indicator (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no UIS series code (organization_series_code) in canonical metadata")
    return source.query_code


@dataclass(frozen=True, slots=True)
class UISIndicatorData:
    """One indicator's records as served by one UIS release."""

    indicator: str
    version: str | None  # the release the records were read from
    records: tuple[Mapping[str, Any], ...] = field(default=())


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class UISClient:
    """Synchronous client for the UIS Data API.

    ``version`` selects a published release; ``None`` (the default) reads the
    release the API currently publishes as its default, resolved once per
    client. ``http`` may be injected (tests: an ``httpx.Client`` with a
    ``MockTransport``); otherwise one is created and owned by this object.
    """

    def __init__(self, *, http: httpx.Client | None = None, base_url: str = BASE_URL, version: str | None = None, timeout: float = 120.0) -> None:
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.base_url = base_url
        self.version = version
        self._default_version: str | None = None

    def release(self) -> str:
        """The release requests are made against: the one given, or the API's current default."""
        if self.version is not None:
            return self.version
        if self._default_version is None:
            payload = self._get("versions/default", {}, "the default release")
            version = payload.get("version") if isinstance(payload, dict) else None
            if not isinstance(version, str) or not version:
                raise SourceResponseError(f"UIS default-release response has no version: {payload!r}")
            self._default_version = version
        return self._default_version

    def fetch_indicator(self, indicator: str) -> UISIndicatorData:
        """Every record one release holds for one indicator, all national areas and years, in API order."""
        version = self.release()
        payload = self._get("data/indicators", {"indicator": indicator, "version": version}, f"indicator {indicator!r}")
        return read_response(payload, indicator, version)

    def _get(self, path: str, params: dict[str, str], what: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self.http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"UIS request for {what} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"UIS request for {what} returned HTTP {response.status_code} ({url})")
        try:
            return response.json()
        except ValueError:
            raise SourceResponseError(f"UIS response for {what} is not JSON") from None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> UISClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_response(payload: Any, indicator: str, version: str | None) -> UISIndicatorData:
    """The records of one data response, ``{"hints", "records", ...}``.

    The API reports an unknown indicator as an empty ``records`` list with a
    hint; that is an error, not an empty dataset.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise SourceResponseError(f"UIS response for indicator {indicator!r} has no records list")
    records = payload["records"]
    if not records and payload.get("hints"):
        messages = [h.get("message", h) if isinstance(h, dict) else h for h in payload["hints"]]
        raise SourceResponseError(f"UIS API returned no records for indicator {indicator!r}: {messages}")
    if any(not isinstance(record, dict) for record in records):
        raise SourceResponseError(f"UIS response for indicator {indicator!r} holds records that are not objects")
    return UISIndicatorData(indicator, version, tuple(records))


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def normalize_uis_dataset(dataset: DatasetMetadata, data: UISIndicatorData) -> NormalizationResult:
    """Convert one release's records for the dataset's indicator into canonical observations."""
    indicator_key(dataset)
    if not dataset.unit:
        raise NormalizationError(f"{dataset.code}: no canonical unit in metadata")
    series = dataset.source.organization_series_code
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for position, record in enumerate(data.records):
        where = f"{dataset.code} record {position}"
        if record.get("indicatorId") != series:
            raise NormalizationError(f"{where}: record belongs to indicator {record.get('indicatorId')!r}, not {series!r}")
        code = record.get("geoUnit")
        if not isinstance(code, str) or pycountry.countries.get(alpha_3=code) is None:
            skipped.setdefault((str(code), ""))
            continue
        try:
            year = int(record.get("year"))  # legacy parsed the year before looking at the value
        except (TypeError, ValueError):
            raise NormalizationError(f"{where}: year {record.get('year')!r} is not a year") from None
        value = record.get("value")
        if value is None or value == "NaN" or not value:
            missing += 1
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise NormalizationError(f"{where}: value {value!r} is not numeric") from None
        if not math.isfinite(number):
            raise NormalizationError(f"{where}: value {value!r} is not finite")
        key = (code, year)
        if key in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in UIS records for {series}")
        seen.add(key)
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_indicator": series,
            "source_version": data.version,
            "qualifier": record.get("qualifier"),
            "magnitude": record.get("magnitude"),
        }
        observations.append(Observation(dataset.code, code, year, number, dataset.unit, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(sorted(skipped)), missing)
