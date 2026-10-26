"""V-Dem: source client and pure normalizer for the Varieties of Democracy
country-year CSV archive.

The legacy SSPI read every V-Dem dataset from one archive::

    https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip

"Country-Year: V-Dem Full+Others", version 13 (data release of March 2023;
the CSV inside is dated 2023-02-22). The address still serves that file.
The archive holds one CSV, ``V-Dem-CY-Full+Others-v13.csv`` (4,602 columns,
one row per country and year, 1789 to 2022), and four PDFs (codebook,
cautionary notes, citation, what is new).

Canonical metadata names the archive in ``query_code`` and the CSV column in
``organization_series_code``; :data:`ARCHIVES` maps the archive to its URL,
the SHA-256 of its bytes and the CSV inside it. Nothing infers or prefers
another edition: an archive whose bytes differ from the pin is refused, even
at the same address. V-Dem re-estimates every past year in each release
(version 16, March 2026, changes most 2000-2022 values); a caller may pass
its own ``archives`` table to read another edition explicitly. Terms of use:
docs/data-governance-review.md, GOV-6.

:func:`normalize_vdem_dataset` reproduces the legacy collector and cleaners
(``collect_vdem_data`` in ``api/datasource/vdem.py``, ``clean_vdem_rulelw``
and ``clean_vdem_edemoc`` in ``api/core/datasets/vdem/``) exactly:

* the collector stored every member whose name contains ``.csv`` as UTF-8
  text (split into fragments of at most 16,609,443 characters by the raw
  collection and joined again by the cleaner's fetch, which loses nothing);
  the cleaner parsed that text with ``pandas.read_csv``. The pinned archive
  has one such member; an archive with none, or more than one, or another
  name than the pinned one, is an error here;
* the cleaner kept the columns ``country_text_id``, ``year`` and the
  dataset's column, then the rows with ``year > 1990`` and ``year <`` the
  calendar year in which it ran (:attr:`VDemArchive.evaluation_year`: the
  year the archive was fetched, so a run in 2026 keeps 1991 to 2025). The
  upper bound moves with the clock; on the pinned v13 archive, whose last
  year is 2022, it removes nothing when run in 2023 or later;
* the rows went through ``DataFrame.to_json(orient="records")`` and
  ``json.loads``: the same round trip runs here, so every value has exactly
  the representation the legacy cleaner stored (``to_json`` writes at most
  ten decimals; the v13 values have at most three);
* a row whose value is empty (``None`` after the round trip) is dropped and
  counted as missing; every other row is an observation of the country
  ``country_text_id`` as published. V-Dem's own identifiers are kept as they
  are: ``XKX`` (Kosovo), ``PSE`` (Palestine/West Bank), ``PSG``
  (Palestine/Gaza), ``SML`` (Somaliland), ``ZZB`` (Zanzibar); there is no ISO
  check and no area is dropped;
* the unit is the cleaners' literal ``Index``, the dataset's canonical unit.

The legacy clean collection then refused the whole dataset for a code that
is not three capital letters, a year that is not an integer between 1901
and 2029, a value that is not a finite number and two values for one
country-year. Each is an error here. V-Dem's confidence bounds
(``*_codelow``, ``*_codehigh``) and standard deviations (``*_sd``) are
never read: the value is the point estimate column alone.

Nothing here touches a database.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from sspi.errors import (
    DuplicateObservationError,
    NormalizationError,
    SourceRequestError,
    SourceResponseError,
)
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "VDEM"
LEGACY_URL = "https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip"
COUNTRY_COLUMN = "country_text_id"
NAME_COLUMN = "country_name"
YEAR_COLUMN = "year"
FIRST_YEAR_EXCLUDED = 1990  # the cleaners' year > 1990
LEGACY_UNIT = "Index"
LEGACY_YEAR_BOUNDS = (1900, 2030)  # the legacy clean collection's 1900 < Year < 2030
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class SourceArchive:
    """One edition of the V-Dem country-year CSV archive at one address."""

    edition: str
    url: str
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned location)
    member: str | None  # the CSV inside the archive; None accepts the one CSV member, whatever its name
    retrieved: str | None = None  # date the pinned bytes were verified at the URL


@dataclass(frozen=True, slots=True)
class VDemArchive:
    """A downloaded archive: its canonical key, the edition it was configured as, its checksum and
    bytes, and the calendar year of the run (the legacy cleaners' upper year bound, exclusive)."""

    key: str
    source: SourceArchive
    sha256: str
    content: bytes
    evaluation_year: int


# Archive edition (canonical query_code) -> where and what it is.
ARCHIVES: dict[str, SourceArchive] = {
    # The legacy collector's literal address, which still serves the v13 archive (26,868,858 bytes; the CSV is
    # dated 2023-02-22, the PDFs 2023-02-27/28).
    "V-Dem-CY-FullOthers_csv_v13": SourceArchive(
        edition="V-Dem Country-Year: V-Dem Full+Others, version 13 (March 2023), CSV",
        url=LEGACY_URL,
        sha256="8186847fa025e7fbc41b9f3b46aeccc6a13817c47d7305bc74e2289f062a28d4",
        member="V-Dem-CY-Full+Others-v13.csv",
        retrieved="2026-10-26",
    ),
}


def archive_key(dataset: Any) -> str:
    """The archive a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no V-Dem archive (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no V-Dem column (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class VDemArchiveClient:
    """Synchronous client for V-Dem archives.

    ``archives`` maps archive keys to :class:`SourceArchive` and defaults to
    :data:`ARCHIVES`. ``http`` may be injected (tests: an ``httpx.Client``
    with a ``MockTransport``); otherwise one is created and owned by this
    object. ``today`` gives the date of the run (default ``date.today``);
    its year is the archive's :attr:`VDemArchive.evaluation_year`.
    """

    def __init__(
        self,
        *,
        archives: Mapping[str, SourceArchive] | None = None,
        http: httpx.Client | None = None,
        timeout: float = 600.0,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.archives = dict(ARCHIVES if archives is None else archives)
        self.today = today
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_archive(self, key: str) -> VDemArchive:
        """Download one configured archive and check its bytes against the configured checksum."""
        try:
            source = self.archives[key]
        except KeyError:
            raise SourceRequestError(f"no V-Dem archive is configured for {key!r}; known: {sorted(self.archives)}") from None
        try:
            response = self.http.get(source.url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"V-Dem archive request for {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"V-Dem archive request for {key!r} returned HTTP {response.status_code} ({source.url})")
        digest = hashlib.sha256(response.content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"V-Dem archive {key!r} ({source.url}) has SHA-256 {digest}, not the configured {source.sha256} of edition "
                f"{source.edition!r}: the published file changed; no other edition is substituted"
            )
        return VDemArchive(key, source, digest, response.content, self.today().year)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> VDemArchiveClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def csv_member(archive: VDemArchive) -> str:
    """The one CSV member the legacy collector stored and its cleaner read."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            names = [name for name in z.namelist() if ".csv" in name]  # the collector's test
    except zipfile.BadZipFile as exc:
        raise SourceResponseError(f"V-Dem archive {archive.key!r} is not a readable ZIP file: {exc}") from None
    if len(names) != 1:
        raise SourceResponseError(f"V-Dem archive {archive.key!r} has {len(names)} CSV members ({names}); exactly one is read")
    (name,) = names
    if archive.source.member is not None and name != archive.source.member:
        raise SourceResponseError(f"V-Dem archive {archive.key!r} holds {name!r}, not the configured {archive.source.member!r}")
    return name


def legacy_records(archive: VDemArchive, column: str) -> tuple[list[dict[str, Any]], list[Any]]:
    """The rows the legacy cleaner built its documents from, after its year filter and its
    ``to_json``/``json.loads`` round trip, and each row's ``country_name`` (for provenance)."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    name = csv_member(archive)
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        try:
            text = z.read(name).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceResponseError(f"V-Dem archive {archive.key!r}: {name} is not UTF-8 text ({exc}); the legacy collector failed on it too") from None
    header = pd.read_csv(io.StringIO(text), nrows=0).columns
    absent = [c for c in (COUNTRY_COLUMN, NAME_COLUMN, YEAR_COLUMN, column) if c not in header]
    if absent:
        raise NormalizationError(f"V-Dem archive {archive.key!r}: {name} lacks columns {absent}")
    table = pd.read_csv(io.StringIO(text), usecols=[NAME_COLUMN, COUNTRY_COLUMN, YEAR_COLUMN, column])
    filtered = table[[COUNTRY_COLUMN, YEAR_COLUMN, column]]
    filtered = filtered[(filtered[YEAR_COLUMN] > FIRST_YEAR_EXCLUDED) & (filtered[YEAR_COLUMN] < archive.evaluation_year)]
    return json.loads(str(filtered.to_json(orient="records"))), list(table.loc[filtered.index, NAME_COLUMN])


def normalize_vdem_dataset(dataset: DatasetMetadata, archive: VDemArchive) -> NormalizationResult:
    """Canonical observations for one dataset from a downloaded V-Dem archive."""
    key = archive_key(dataset)
    if archive.key != key:
        raise NormalizationError(f"{dataset.code}: archive {archive.key!r} is not the dataset's {key!r}")
    if dataset.unit != LEGACY_UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit {dataset.unit!r} is not the legacy cleaners' literal {LEGACY_UNIT!r}")
    column = dataset.source.organization_series_code
    member = csv_member(archive)
    records, names = legacy_records(archive, column)
    where = f"{dataset.code} archive {key!r}"
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    missing = 0
    for record, name in zip(records, names, strict=True):
        country, year, value = record[COUNTRY_COLUMN], record[YEAR_COLUMN], record[column]
        if value is None:
            missing += 1  # the cleaners' `if obs[column] is None: continue`
            continue
        if not isinstance(country, str) or not _STORABLE_COUNTRY.match(country):
            raise NormalizationError(f"{where}: country_text_id {country!r} cannot be stored (three capital letters required; the legacy clean collection refused it too)")
        if isinstance(year, bool) or not isinstance(year, int) or not LEGACY_YEAR_BOUNDS[0] < year < LEGACY_YEAR_BOUNDS[1]:
            raise NormalizationError(f"{where}: ({country}) year {year!r} is not an integer between 1901 and 2029 (the legacy clean collection refused it too)")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise NormalizationError(f"{where}: ({country}, {year}) value {value!r} is not a finite number (the legacy clean collection refused it too)")
        if (country, year) in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({country}, {year}) in archive {key!r} column {column!r}")
        seen.add((country, year))
        provenance: dict[str, Any] = {
            "source_organization": ORGANIZATION_CODE,
            "source_file": archive.key,
            "source_edition": archive.source.edition,
            "source_url": archive.source.url,
            "source_sha256": archive.sha256,
            "source_member": member,
            "source_column": column,
            "source_country_name": name if isinstance(name, str) else None,
            "source_value": repr(value),
            "source_years": [FIRST_YEAR_EXCLUDED + 1, archive.evaluation_year - 1],  # the legacy window on the run's calendar year
        }
        observations.append(Observation(dataset.code, country, year, value, LEGACY_UNIT, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), missing)
