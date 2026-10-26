"""Fragile States Index: source client and pure normalizer for the Fund for
Peace's annual Excel workbooks.

The Fund for Peace publishes one workbook per FSI edition and links them
from https://fragilestatesindex.org/excel/. On 2026-10-25 that page linked
the editions 2006 to 2023 (each twice; the legacy collector kept the first
link per year). Each workbook's first sheet has one row per country:
``Country``, ``Year``, ``Rank``, ``Total`` and the twelve indicators, among
them ``C1: Security Apparatus`` (0 best, 10 worst). The column order and the
``Year`` cells differ between editions (a date on 1 January in most, an
integer in 2021 and 2023); in every edition ``Year`` is the edition year of
the file name.

Canonical metadata names the edition set in ``query_code`` and the column in
``organization_series_code``; :data:`EDITION_SETS` maps the set to each
edition's URL and the SHA-256 of its bytes. A workbook whose bytes differ
from the pin is refused; no edition is added, dropped or substituted. A
caller may pass its own ``edition_sets`` table to read others explicitly.

The pinned legacy acquisition never stored an FSI value (SECAPP-1, resolved): its
collector parsed the page's address instead of the page, the raw document
it would store is not the shape its cleaner reads, the source description
it would store is not the one the cleaner queries, and the cleaner's rows
have no ``DatasetCode``. The project owner approved this adapter on
2026-10-25 as the repair of that acquisition. What it reproduces exactly
is the executable cleaner (``clean_fsi_data`` in ``api/datasource/fsi.py``)
applied to each workbook as the working collector of March 2025 stored it
(``read_excel`` records, round-tripped through MongoDB):

* the columns ``Country``, ``Year`` and ``C1: Security Apparatus``; the
  value as read, nothing rounded or rescaled; the overall FSI total is never
  read;
* the year: a date cell gives its calendar year (the cleaner split the
  stored ISO date), an integer cell is kept;
* the unit is the cleaner's literal ``Index``, the dataset's canonical unit.

What the repair adds, and why (documented as SECAPP-1; none changes a value
or a year):

* the dataset code on every observation (the cleaner left it out, so the
  clean collection refused every row);
* country names: the legacy matcher (:func:`sspi.ingestion.geo.legacy_country_code`)
  fails on every edition. Each name is first stripped of surrounding
  whitespace (the 2006 workbook pads most names; "Serbia  " has two spaces
  in 2006-2009), then :data:`APPROVED_NAME_CORRECTIONS` gives the five
  spellings it cannot place their ISO 3166-1 codes. "North Korea" is in that
  table because the legacy matcher sends it to KOR, the code of "South
  Korea", so every edition would hold two KOR rows. Every other name goes
  through the legacy matcher unchanged. A name it cannot code, two rows
  with one code in an edition, a value that is not a finite number, a year
  that is not an integer or differs from the edition's year, and a missing
  column are errors;
* each edition is checked against its pinned file and edition year.

Nothing here touches a database.
"""

from __future__ import annotations

import hashlib
import io
import math
import numbers
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from sspi.errors import DuplicateObservationError, NormalizationError, SourceRequestError, SourceResponseError
from sspi.ingestion.geo import legacy_country_code
from sspi.ingestion.results import NormalizationResult
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "FSI"
EXCEL_PAGE = "https://fragilestatesindex.org/excel/"
COUNTRY_COLUMN = "Country"
YEAR_COLUMN = "Year"
LEGACY_UNIT = "Index"
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")

# The approved repair of the legacy name matching (SECAPP-1): exact spellings, after surrounding whitespace is
# stripped, and the ISO 3166-1 alpha-3 identity each names (pycountry name in the comment). The first four are the
# identities the project owner approved for the same names in the GCI transcription (CYBSEC-1); "North Korea" is
# corrected because the legacy matcher assigns it KOR, colliding with "South Korea". The whitespace stripping and the
# North Korea mapping were confirmed by the project owner on 2026-10-26.
APPROVED_NAME_CORRECTIONS: dict[str, str] = {
    "Cote d'Ivoire": "CIV",  # Côte d'Ivoire
    "Macedonia": "MKD",  # North Macedonia (the name until 2019)
    "Micronesia": "FSM",  # Micronesia, Federated States of
    "Palestine": "PSE",  # Palestine, State of
    "North Korea": "PRK",  # Korea, Democratic People's Republic of (legacy matcher: KOR)
}
CORRECTION_DECISION = "SECAPP-1: approved FSI name repair (project owner, 2026-10-25, confirmed 2026-10-26)"


@dataclass(frozen=True, slots=True)
class SourceWorkbook:
    """One FSI edition's workbook at one address."""

    edition: int
    url: str
    sha256: str | None  # expected content checksum; None accepts any content (an explicitly unpinned location)
    retrieved: str | None = None  # date the pinned bytes were verified at the URL


@dataclass(frozen=True, slots=True)
class FSIWorkbook:
    """A downloaded edition: the edition it was configured as, its checksum and bytes."""

    source: SourceWorkbook
    sha256: str
    content: bytes


@dataclass(frozen=True, slots=True)
class FSIEditions:
    """Every workbook of one edition set, in edition order."""

    key: str
    workbooks: tuple[FSIWorkbook, ...]


def _edition(year: int, path: str, sha256: str) -> SourceWorkbook:
    return SourceWorkbook(year, f"https://fragilestatesindex.org/wp-content/uploads/{path}", sha256, "2026-10-25")


# Edition set (canonical query_code) -> the workbooks, as linked from EXCEL_PAGE on 2026-10-25 (first link per year).
EDITION_SETS: dict[str, tuple[SourceWorkbook, ...]] = {
    "fsi-excel_2006-2023": (
        _edition(2006, "data/fsi-2006.xlsx", "dcc3fa8914bef3159e7263a9b6efdb447fd293485abd0c2c6ad44ff3ba3ed7eb"),
        _edition(2007, "data/fsi-2007.xlsx", "5142f1a238ec86cfd24b6842e3f293c577fb9fd8a934a8a0c0e1975ca91d88eb"),
        _edition(2008, "data/fsi-2008.xlsx", "225be13499da8cf60dc6d4e56005bc2425c4226935b11fa93cd88b2f2e719f39"),
        _edition(2009, "data/fsi-2009.xlsx", "d5c271f586142f68fc42ad909f876235f2bd1b65a369c34ae5d4316fe94ef7c3"),
        _edition(2010, "data/fsi-2010.xlsx", "8c9e48ac85746d85f1828664c7e5c5265e5c18bbdc577764c82b151812884cfc"),
        _edition(2011, "data/fsi-2011.xlsx", "a711eeef877a5fd24d3c35590cfe4468b464c33974e7286d200f6c0cf33982d1"),
        _edition(2012, "data/fsi-2012.xlsx", "3191091115e210a4f447196aa8aed32f173092a80e1acf1e457f59e746da40a2"),
        _edition(2013, "data/fsi-2013.xlsx", "70009d126708093b35a5b2c3963ada9442a219216a46851409691b4296effaee"),
        _edition(2014, "data/fsi-2014.xlsx", "4c8e1a1a9dd226fcdfb8245271e301fd5f38c9e3b5e9b8a1c7f40a9558aa3f91"),
        _edition(2015, "data/fsi-2015.xlsx", "bef7914dc6d16e2f22ae177c2a5e7828a5536352dd68f2a9aa90d7b15bfd755c"),
        _edition(2016, "data/fsi-2016.xlsx", "dab6ce81db1c3166eb091d41d668edc2d3fb87075c70f6d6a2f8b27d68499461"),
        _edition(2017, "data/fsi-2017.xlsx", "0993d395e9189d3a7ee182e7a46b969d2e1efcb757e41f24957facdbdae26fee"),
        _edition(2018, "2018/04/fsi-2018.xlsx", "6e64b2da442f93bb9b81a8843f00a384aa63598ee9cde10c4d422bf308d43a40"),
        _edition(2019, "2019/04/fsi-2019.xlsx", "7a342d07da49ed87053c360030411857b05eb84df0c490f0dec08eb986d22d80"),
        _edition(2020, "2020/05/fsi-2020.xlsx", "69efc929b7972f8e772ddab288bfe92ffd3c6d725e1d82644a5c684379a42877"),
        _edition(2021, "2021/05/fsi-2021.xlsx", "b21a891071f48ee00746b25c6b5c2ebbe08323b46a9daf3b8935243f0e2325d4"),
        _edition(2022, "2022/07/fsi-2022-download.xlsx", "fdbecfb98bb15478905e4fa2e1be1b552e95c914b57f0ff983134fca3413fe0a"),
        _edition(2023, "2023/06/FSI-2023-DOWNLOAD.xlsx", "76adfd95695ad8da1eb6233dc14e06ba2c1f55080f604b5310f2acd52ffc1d2d"),
    ),
}


def edition_set_key(dataset: Any) -> str:
    """The edition set a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no FSI edition set (query_code) in canonical metadata")
    if not source.organization_series_code:
        raise NormalizationError(f"{dataset.code}: no FSI indicator column (organization_series_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class FSIWorkbookClient:
    """Synchronous client for the FSI annual workbooks.

    ``edition_sets`` maps set keys to their :class:`SourceWorkbook` tuple and
    defaults to :data:`EDITION_SETS`. ``http`` may be injected (tests: an
    ``httpx.Client`` with a ``MockTransport``); otherwise one is created and
    owned by this object.
    """

    def __init__(self, *, edition_sets: Mapping[str, Sequence[SourceWorkbook]] | None = None, http: httpx.Client | None = None, timeout: float = 300.0) -> None:
        self.edition_sets = {key: tuple(value) for key, value in (EDITION_SETS if edition_sets is None else edition_sets).items()}
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_editions(self, key: str) -> FSIEditions:
        """Download every workbook of one configured set and check each against its configured checksum."""
        try:
            sources = self.edition_sets[key]
        except KeyError:
            raise SourceRequestError(f"no FSI edition set is configured for {key!r}; known: {sorted(self.edition_sets)}") from None
        return FSIEditions(key, tuple(self._fetch(key, source) for source in sources))

    def _fetch(self, key: str, source: SourceWorkbook) -> FSIWorkbook:
        try:
            response = self.http.get(source.url)
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"FSI {source.edition} workbook request for {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"FSI {source.edition} workbook request for {key!r} returned HTTP {response.status_code} ({source.url})")
        digest = hashlib.sha256(response.content).hexdigest()
        if source.sha256 is not None and digest != source.sha256:
            raise SourceResponseError(
                f"FSI {source.edition} workbook ({source.url}) has SHA-256 {digest}, not the configured {source.sha256}: "
                "the published file changed; no other edition is substituted"
            )
        return FSIWorkbook(source, digest, response.content)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> FSIWorkbookClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def country_code(name: str) -> tuple[str, str | None]:
    """(code, correction) for one FSI country name: the repaired legacy matching described above."""
    stripped = name.strip()
    if stripped in APPROVED_NAME_CORRECTIONS:
        return APPROVED_NAME_CORRECTIONS[stripped], CORRECTION_DECISION
    code = legacy_country_code(stripped)
    return code, (CORRECTION_DECISION + ": surrounding whitespace stripped" if stripped != name else None)


def legacy_year(cell: Any) -> int:
    """The cleaner's year: the calendar year of a date cell (its stored ISO date, split), an integer as it is."""
    if hasattr(cell, "year") and hasattr(cell, "month"):
        return int(cell.year)
    if isinstance(cell, bool) or not isinstance(cell, numbers.Integral):
        raise NormalizationError(f"FSI Year cell {cell!r} is neither a date nor an integer (the legacy clean collection refused it)")
    return int(cell)


def normalize_fsi_dataset(dataset: DatasetMetadata, editions: FSIEditions) -> NormalizationResult:
    """Canonical observations for one dataset from every workbook of its edition set."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    key = edition_set_key(dataset)
    if editions.key != key:
        raise NormalizationError(f"{dataset.code}: edition set {editions.key!r} is not the dataset's {key!r}")
    if dataset.unit != LEGACY_UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit {dataset.unit!r} is not the legacy cleaner's {LEGACY_UNIT!r}")
    column = dataset.source.organization_series_code
    observations: list[Observation] = []
    seen: dict[tuple[str, int], str] = {}
    for workbook in editions.workbooks:
        edition = workbook.source.edition
        where = f"{dataset.code} FSI {edition} ({workbook.source.url})"
        try:
            sheet = pd.read_excel(io.BytesIO(workbook.content))
        except Exception as exc:  # noqa: BLE001 - any unreadable workbook is the same failure
            raise SourceResponseError(f"{where}: not a readable Excel file: {type(exc).__name__}: {exc}") from None
        absent = [c for c in (COUNTRY_COLUMN, YEAR_COLUMN, column) if c not in sheet.columns]
        if absent:
            raise NormalizationError(f"{where}: lacks columns {absent}; found {list(sheet.columns)}")
        unmatched: list[str] = []
        for name, cell, raw in zip(sheet[COUNTRY_COLUMN], sheet[YEAR_COLUMN], sheet[column], strict=True):
            if not isinstance(name, str):
                raise NormalizationError(f"{where}: Country cell {name!r} is not a name")
            code, correction = country_code(name)
            if not _STORABLE_COUNTRY.match(code):
                unmatched.append(name)
                continue
            year = legacy_year(cell)
            if year != edition:
                raise NormalizationError(f"{where}: {name!r} has Year {year}, not the edition year {edition}")
            if isinstance(raw, bool) or not isinstance(raw, numbers.Real) or not math.isfinite(float(raw)):
                raise NormalizationError(f"{where}: {name!r} {column} value {raw!r} is not a finite number (the legacy clean collection refused it too)")
            if (code, year) in seen:
                raise DuplicateObservationError(f"{dataset.code}: {name!r} and {seen[(code, year)]!r} are both {code} in FSI {edition}")
            seen[(code, year)] = name
            provenance: dict[str, Any] = {
                "source_organization": ORGANIZATION_CODE,
                "source_file": key,
                "source_edition": edition,
                "source_url": workbook.source.url,
                "source_sha256": workbook.sha256,
                "source_column": column,
                "source_country_name": name,
                "source_year_cell": str(cell),
                "source_value": repr(raw.item() if hasattr(raw, "item") else raw),
            }
            if correction:
                provenance["country_code_correction"] = correction
            observations.append(Observation(dataset.code, code, year, float(raw), LEGACY_UNIT, provenance))
        if unmatched:
            raise NormalizationError(f"{where}: no ISO3 code for {sorted(unmatched)} under the legacy matcher and the approved FSI corrections (SECAPP-1)")
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, (), 0)
