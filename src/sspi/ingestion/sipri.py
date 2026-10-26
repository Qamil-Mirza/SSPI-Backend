"""SIPRI: source client and pure normalizers for the SIPRI Arms Transfers
Database export used by ARMEXP and the SIPRI Military Expenditure Database
workbook prepared for MILEXP.

The legacy collector (``collect_sipri_armexp`` in
``api/core/datasets/sipri/sipri_armexp.py``) POSTs a JSON filter to::

    https://atbackend.sipri.org/api/p/trades/import-export-csv-str/

asking for delivered transfers, years 1990-2025, ordered by seller, and
stores the JSON answer, ``{"result": "<csv text>"}``. The text starts with
notes (the values are millions of SIPRI trend-indicator values, TIV; a
``0`` means under 0.5 million; an empty field means no delivery found; and
the date the file was generated), then the table ``Exports by,1990,...,2025,``
followed by period totals and percentages, one row per supplier and a
``Total world export`` row. The API serves the current state of the
database: it has no editions, so a response is not checksum-pinned (each
says when it was generated). :data:`QUERIES` holds the request exactly as
the legacy collector sent it; canonical metadata names it in
``query_code``. Terms of use: docs/data-governance-review.md, GOV-7.

The TIV is a volume measure: SIPRI says its figures "do not represent sales
prices for arms transfers" and should not be compared with GDP or military
expenditure (ARMEXP-1).

:func:`normalize_sipri_dataset` reproduces the registered cleaner
(``clean_sipri_armexp``) exactly, with the same pandas steps:

* the table is read from the first line starting with ``Exports by,``; rows
  whose name contains ``Total world export`` or ``Sum total years`` are
  dropped; only the columns named by a year 1990-2025 are kept;
* the year columns are melted; a cell ``"0 "`` is read as ``0``, an empty or
  non-numeric cell is dropped and counted as missing; a published zero is
  kept;
* names in the cleaner's skip list (former states, non-state suppliers,
  "unknown supplier(s)") are skipped; a name containing ``north korea`` is
  PRK and one containing ``south korea`` is KOR; every other name goes
  through the legacy matcher (:func:`sspi.ingestion.geo.legacy_country_code`)
  and a result that is not three characters long is skipped. Both kinds of
  skip are reported as skipped areas (today: the African Union and Libya's
  House of Representatives are not matched);
* one APPROVED source-representation correction (ARMEXP-4, 2026-10-26)
  differs from the cleaner: :data:`APPROVED_ARMS_NAME_CORRECTIONS` gives the
  two SIPRI spellings the legacy matcher cannot place, ``Brunei`` and
  ``Bosnia-Herzegovina``, their ISO 3166-1 identities (BRN, BIH); the
  cleaner dropped their rows. The table applies to SIPRI_ARMEXP only;
* the unit is the cleaner's literal ``Millions SIPRI TIV``.

The legacy clean collection refused the whole dataset for a code that is not
three capital letters and for two values for one country-year; each is an
error here. Where the legacy cleaner found no ``Exports by,`` line it
stored nothing (after deleting the stored rows); here that is an error, so
a changed response never empties the dataset.

**Military expenditure (``SIPRI_MILEXP``; not ingestible: MILEXP-5).** The
legacy collector POSTed to the military-expenditure API
(``https://backend.sipri.org/api/p/excel-export/preview``, ``yearList:
[1990, 2024]``, ``verify=False``). That API still serves the 2025 edition,
including Belarus's 1992-2013 shares of GDP that SIPRI withdrew on 27 April
2026. The project owner approved (MILEXP-4, 2026-10-26) SIPRI's revised
workbook as the single source instead: :data:`MILEX_WORKBOOKS` pins it by
file name, edition, revision date, official URL and SHA-256. It is
downloaded from SIPRI, or read from an explicitly configured local copy of
the same bytes (``SIPRIClient(local_workbook_directory=...)``); any other
bytes are refused. No API value is used or mixed in.

:func:`normalize_milex_workbook` reads the workbook's "Share of GDP" sheet:

* the schema is checked: exactly one such sheet, its title, exactly one
  header row ``Country, Notes, <year>, <year>, ...`` of consecutive whole
  years covering :data:`MILEX_WINDOW`, unique country names, every row as
  long as the header; anything else is an error;
* only the columns of :data:`MILEX_WINDOW`, 1990-2024, the legacy
  collector's window, are read (the scoring horizon is not extended to 2025);
  each value takes the year of its own header label (MILEXP-1);
* a cell is a number, or one of SIPRI's markers :data:`MILEX_MARKERS`
  (``...`` unavailable, ``xxx`` not independent), which is missing and
  counted; a blank or any other text in a country row is an error. A
  published numeric zero is an observed zero: SIPRI publishes 0 only for
  Costa Rica, Panama and Iceland, each with a footnote stating that the
  country has no military expenditure;
* SIPRI publishes shares of GDP as fractions; every value is multiplied by
  100 (MILEXP-2), with no other rounding. A fraction of 1 or more (100% of
  GDP or more) must be listed in :data:`MILEX_VERIFIED_LARGE_SHARES` (Kuwait
  1991, 117.35%), and is then kept, not clamped; any other is an error;
* country names: :data:`APPROVED_MILEX_NAME_CORRECTIONS` first (MILEXP-1:
  five names the legacy matcher cannot place or places wrongly, and the
  former German Democratic Republic kept out), then the legacy cleaner's
  Korea rules and matcher. A name without a code must be one of
  :data:`MILEX_EXCLUDED_NAMES` (former states and the European Union,
  reported as skipped areas); a code must be ISO 3166-1 alpha-3 or the
  legacy matcher's Kosovo code ``XKX``; region rows must hold no number.
  Two values for one country-year are an error.

Each observation records the workbook's identity (file name, edition,
revision date, URL, SHA-256), the sheet, the source name, notes, year label
and cell value, and each correction applied. SIPRI marks estimates in blue
and highly uncertain figures in red; that colouring is not read.

Nothing here touches a database.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import numbers
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from sspi.errors import (
    DuplicateObservationError,
    NormalizationError,
    SourceRequestError,
    SourceResponseError,
)
from sspi.ingestion.geo import legacy_country_code
from sspi.ingestion.results import NormalizationResult
from sspi.ingestion.workbooks import PinnedWorkbook, PinnedWorkbookClient, WorkbookFile
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

ORGANIZATION_CODE = "SIPRI"
HEADER_PREFIX = "Exports by,"
NAME_COLUMN = "Exports by"
TOTAL_ROWS = "Total world export|Sum total years"  # the cleaner's str.contains pattern
YEARS = (1990, 2025)  # the cleaner keeps the columns named by these years and those between
LEGACY_UNIT = "Millions SIPRI TIV"
SKIPPED_NAMES = (  # the cleaner's skip_countries, compared with the stripped, lower-cased name
    "soviet union",
    "yugoslavia",
    "czechoslovakia",
    "east germany (gdr)",
    "unknown supplier(s)",
    "european union**",
    "fmln (el salvador)*",
    "mujahedin (afghanistan)*",
    "hor (libya)*",
)
_STORABLE_COUNTRY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class SIPRIQuery:
    """One SIPRI API request as the legacy collector sent it."""

    description: str
    url: str
    headers: Mapping[str, str]
    payload: Mapping[str, Any] = field(hash=False)
    sha256: str | None = None  # expected answer checksum where the API answers byte-stably; None for a live database (armstransfers)


@dataclass(frozen=True, slots=True)
class SIPRIResponse:
    """A downloaded answer: the query key, the query and the response bytes."""

    key: str
    query: SIPRIQuery
    content: bytes


# Query key (canonical query_code) -> the request.
QUERIES: dict[str, SIPRIQuery] = {
    "armstransfers": SIPRIQuery(
        description="SIPRI Arms Transfers Database, exports by supplier, delivered transfers, 1990-2025 (the legacy collector's request)",
        url="https://atbackend.sipri.org/api/p/trades/import-export-csv-str/",
        headers={"Content-Type": "application/json", "Origin": "https://armstransfers.sipri.org", "Referer": "https://armstransfers.sipri.org"},
        payload={
            "filters": [
                {"field": "Year range 1", "oldField": "", "condition": "contains", "value1": 1990, "value2": 2025, "listData": []},
                {"field": "orderbyseller", "oldField": "", "condition": "", "value1": "", "value2": "", "listData": []},
                {"field": "DeliveryType", "oldField": "", "condition": "", "value1": "delivered", "value2": "", "listData": []},
                {"field": "Status", "oldField": "", "condition": "", "value1": "0", "value2": "", "listData": []},
            ],
            "logic": "AND",
        },
    ),
}

# APPROVED source-representation correction for SIPRI_ARMEXP only (ARMEXP-4, project owner, 2026-10-26): SIPRI spelling ->
# ISO 3166-1 alpha-3, for the two supplier names the legacy matcher cannot place (the cleaner dropped their rows).
APPROVED_ARMS_NAME_CORRECTIONS: dict[str, str] = {
    "Brunei": "BRN",  # Brunei Darussalam
    "Bosnia-Herzegovina": "BIH",  # Bosnia and Herzegovina
}
ARMS_CORRECTION = "ARMEXP-4 (approved 2026-10-26): SIPRI_ARMEXP name table"

# APPROVED source-representation correction for SIPRI_MILEXP only (MILEXP-1, project owner, 2026-10-26): source spelling
# -> ISO 3166-1 alpha-3, or None to keep out a former state the legacy matcher sends to another country's code.
APPROVED_MILEX_NAME_CORRECTIONS: dict[str, str | None] = {
    "Brunei": "BRN",  # Brunei Darussalam (legacy matcher: no match, row dropped)
    "Congo, Republic": "COG",  # Congo (no match)
    "Cote d'Ivoire": "CIV",  # Côte d'Ivoire (no match)
    "Gambia, The": "GMB",  # Gambia (no match)
    "Korea, North": "PRK",  # Korea, Democratic People's Republic of (legacy matcher: KOR, the code of "Korea, South")
    "German Democratic Republic": None,  # former state, "xxx" after 1990 (legacy matcher: COD)
}
# The approved single source for SIPRI_MILEXP (MILEXP-4, project owner, 2026-10-26): canonical query_code -> the edition.
MILEX_WORKBOOKS: dict[str, PinnedWorkbook] = {
    # "This file was revised on 27 April 2026 at 19:00 CET to update Belarus's military expenditure as a percentage of gross
    # domestic product for the years 1992-2013. This revised version replaces all previous versions." (landing page,
    # read 2026-10-26.) 922,552 bytes, Last-Modified Mon, 27 Apr 2026 15:20:25 GMT.
    "SIPRI-Milex-data-1949-2025_v1.2": PinnedWorkbook(
        filename="SIPRI-Milex-data-1949-2025_v1.2.xlsx",
        edition="SIPRI Military Expenditure Database, 1949-2025 (© SIPRI 2026), version 1.2",
        revised="2026-04-27",
        url="https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx",
        landing_page="https://www.sipri.org/databases/milex",
        sha256="6cc3a30b1064f9f02e60236667eef82e08cad42910ce630909d004ad2c398a9d",
        retrieved="2026-10-26",
    ),
}
MILEX_SHEET = "Share of GDP"
MILEX_TITLE = "Military expenditure by country as percentage of gross domestic product"
MILEX_WINDOW = (1990, 2024)  # the legacy collector's yearList: the comparison window, not extended to the workbook's 2025
MILEX_MARKERS = {"...": "data unavailable", "xxx": "country did not exist or was not independent", ". .": "data unavailable"}  # the sheet's legend
MILEX_REGION_ROWS = (  # the sheet's region and subregion rows (the legacy cleaner's list, with the two it lacked)
    "Africa", "North Africa", "sub-Saharan Africa", "Americas", "North America", "Central America and the Caribbean", "South America",
    "Asia & Oceania", "Central Asia", "East Asia", "South Asia", "South East Asia", "Oceania", "Europe", "Central Europe", "Eastern Europe",
    "Western Europe", "Middle East",
)
MILEX_EXCLUDED_NAMES = {  # names with no present-day identity: reported as skipped areas, never stored under another code
    "Czechoslovakia": "former state",
    "German Democratic Republic": "former state (kept out by MILEXP-1, never DEU)",
    "USSR": "former state",
    "Yemen, North": "former state",
    "Yugoslavia": "former state",
    "European Union": "not a country",
}
NON_ISO_CODES = {"XKX": "Kosovo, the legacy matcher's code (user-assigned, not ISO 3166-1)"}
MILEX_UNIT = "Percent of GDP"
MILEX_NAME_CORRECTION = "MILEXP-1 (approved 2026-10-26): SIPRI_MILEXP name table"
MILEX_SCALING = "MILEXP-2 (approved 2026-10-26): fraction multiplied by 100"
# MILEXP-2: published fractions of 1 or more (100% of GDP or more), each verified: (source name, year) -> the cell's value.
MILEX_VERIFIED_LARGE_SHARES: dict[tuple[str, int], float] = {
    ("Kuwait", 1991): 1.173498232086904,  # 117% of GDP in the year of the Gulf War; identical in the API's 2025 edition
}


def query_key(dataset: Any) -> str:
    """The request a dataset is read from (its canonical ``query_code``)."""
    if not isinstance(dataset, DatasetMetadata):
        code = getattr(dataset, "code", dataset)
        raise NormalizationError(f"{code}: no complete dataset definition to normalize against")
    source = dataset.source
    if source.organization_code != ORGANIZATION_CODE:
        raise NormalizationError(f"{dataset.code}: source organization is {source.organization_code!r}, not {ORGANIZATION_CODE!r}")
    if not source.query_code:
        raise NormalizationError(f"{dataset.code}: no SIPRI query (query_code) in canonical metadata")
    return source.query_code


# --------------------------------------------------------------------------- #
# Source client
# --------------------------------------------------------------------------- #


class SIPRIClient:
    """Synchronous client for SIPRI sources: the database API (arms transfers) and pinned workbooks (military expenditure).

    ``queries`` maps query keys to :class:`SIPRIQuery` and defaults to
    :data:`QUERIES`; ``workbooks`` maps workbook keys to
    :class:`~sspi.ingestion.workbooks.PinnedWorkbook` and defaults to
    :data:`MILEX_WORKBOOKS`. ``local_workbook_directory``, when given, holds a
    local copy of each pinned workbook, read instead of the download (its
    bytes must still match the pin). ``http`` may be injected (tests: an
    ``httpx.Client`` with a ``MockTransport``); otherwise one is created and
    owned by this object.
    """

    def __init__(
        self,
        *,
        queries: Mapping[str, SIPRIQuery] | None = None,
        workbooks: Mapping[str, PinnedWorkbook] | None = None,
        local_workbook_directory: str | Path | None = None,
        http: httpx.Client | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.queries = dict(QUERIES if queries is None else queries)
        self._owns_http = http is None
        self.http = http if http is not None else httpx.Client(timeout=timeout, follow_redirects=True)
        self.workbooks = PinnedWorkbookClient(MILEX_WORKBOOKS if workbooks is None else workbooks, local_directory=local_workbook_directory, http=self.http)

    def fetch(self, key: str) -> SIPRIResponse | WorkbookFile:
        """A pinned workbook where ``key`` names one, otherwise an API query."""
        return self.workbooks.fetch_workbook(key) if key in self.workbooks.workbooks else self.fetch_query(key)

    def fetch_query(self, key: str) -> SIPRIResponse:
        """POST one configured request; the answer must be JSON with a ``result`` text."""
        try:
            query = self.queries[key]
        except KeyError:
            raise SourceRequestError(f"no SIPRI query is configured for {key!r}; known: {sorted(self.queries)}") from None
        try:
            response = self.http.post(query.url, headers=dict(query.headers), json=json.loads(json.dumps(query.payload)))
        except httpx.HTTPError as exc:
            raise SourceRequestError(f"SIPRI request {key!r} failed: {exc}") from exc
        if response.status_code != 200:
            raise SourceRequestError(f"SIPRI request {key!r} returned HTTP {response.status_code} ({query.url})")
        if query.sha256 is not None:
            digest = hashlib.sha256(response.content).hexdigest()
            if digest != query.sha256:
                raise SourceResponseError(f"SIPRI answer {key!r} has SHA-256 {digest}, not the configured {query.sha256}: the published data changed; no other edition is substituted")
        return SIPRIResponse(key, query, response.content)

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> SIPRIClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Normalizer
# --------------------------------------------------------------------------- #


def result_text(response: SIPRIResponse) -> str:
    """The CSV text the legacy cleaner read (``Raw["result"]``)."""
    try:
        document = json.loads(response.content)
    except ValueError as exc:
        raise SourceResponseError(f"SIPRI response {response.key!r} is not JSON: {exc}") from None
    if not isinstance(document, dict) or not isinstance(document.get("result"), str):
        raise SourceResponseError(f"SIPRI response {response.key!r} has no 'result' text (keys: {sorted(document) if isinstance(document, dict) else type(document).__name__})")
    return document["result"]


def legacy_table(text: str) -> Any:
    """The melted table as the legacy cleaner built it, with each value's cell text kept beside it."""
    import pandas as pd  # imported here so the ingestion package stays importable without pandas loaded

    lines = text.strip().split("\n")
    header = next((i for i, line in enumerate(lines) if line.startswith(HEADER_PREFIX)), None)
    if header is None:
        raise SourceResponseError(f"SIPRI response has no line starting {HEADER_PREFIX!r}; the legacy cleaner stored nothing for such a response")
    df = pd.read_csv(io.StringIO("\n".join(lines[header:])))
    df = df[~df[NAME_COLUMN].str.contains(TOTAL_ROWS, na=False)]
    year_columns = [c for c in df.columns if c.isdigit() and YEARS[0] <= int(c) <= YEARS[1]]
    melted = df.melt(id_vars=[NAME_COLUMN], value_vars=year_columns, var_name="Year", value_name="Value")
    melted = melted.rename(columns={NAME_COLUMN: "Country"})
    melted["Cell"] = melted["Value"]
    melted["Value"] = melted["Value"].replace("", None)
    melted["Value"] = melted["Value"].replace("0 ", "0")
    present = melted.dropna(subset=["Value"])
    present = present.assign(Value=pd.to_numeric(present["Value"], errors="coerce"))
    kept = present.dropna(subset=["Value"])
    kept = kept.assign(Year=kept["Year"].astype(int))
    return melted, kept


def legacy_code(name: str) -> str | None:
    """The cleaner's identity for a supplier name, or ``None`` where it skipped the row."""
    lowered = name.strip().lower()
    if lowered in SKIPPED_NAMES:
        return None
    if "north korea" in lowered:
        return "PRK"
    if "south korea" in lowered:
        return "KOR"
    code = legacy_country_code(name)
    return code if code and len(code) == 3 else None


def arms_code(name: str) -> tuple[str | None, bool]:
    """(identity, corrected): the cleaner's identity, or the approved SIPRI_ARMEXP name table where the cleaner skipped the row."""
    code = legacy_code(name)
    if code is None and name in APPROVED_ARMS_NAME_CORRECTIONS:
        return APPROVED_ARMS_NAME_CORRECTIONS[name], True
    return code, False


def normalize_sipri_dataset(dataset: DatasetMetadata, fetched: SIPRIResponse | WorkbookFile) -> NormalizationResult:
    """Canonical observations for one dataset from a SIPRI answer or pinned workbook."""
    if isinstance(fetched, WorkbookFile):
        return normalize_milex_workbook(dataset, fetched)
    return normalize_arms_dataset(dataset, fetched)


def milex_code(name: str) -> tuple[str | None, bool]:
    """(identity, corrected): the approved name table first, then the legacy cleaner's Korea rules and matcher."""
    if name in APPROVED_MILEX_NAME_CORRECTIONS:
        return APPROVED_MILEX_NAME_CORRECTIONS[name], True
    lowered = name.lower()
    if "north korea" in lowered:
        return "PRK", False
    if "south korea" in lowered:
        return "KOR", False
    code = legacy_country_code(name)
    return (code if code and len(code) == 3 else None), False


def milex_identity(name: str, where: str) -> tuple[str | None, bool]:
    """A validated identity for a source name, or ``(None, False)`` for an excluded name; anything else is an error."""
    import pycountry

    code, corrected = milex_code(name)
    if code is None:
        if name not in MILEX_EXCLUDED_NAMES:
            raise NormalizationError(f"{where}: no country identity for {name!r}, and it is not an excluded name {sorted(MILEX_EXCLUDED_NAMES)}")
        return None, False
    if not _STORABLE_COUNTRY.match(code) or (pycountry.countries.get(alpha_3=code) is None and code not in NON_ISO_CODES):
        raise NormalizationError(f"{where}: {name!r} matched {code!r}, which is neither an ISO 3166-1 alpha-3 code nor an accepted code {sorted(NON_ISO_CODES)}")
    return code, corrected


def milex_sheet(workbook: WorkbookFile) -> list[tuple[Any, ...]]:
    """The rows of the one "Share of GDP" sheet, as values."""
    import openpyxl  # imported here so the ingestion package stays importable without it loaded

    try:
        book = openpyxl.load_workbook(io.BytesIO(workbook.content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any unreadable workbook is the same failure
        raise SourceResponseError(f"SIPRI workbook {workbook.key!r} is not a readable Excel file: {type(exc).__name__}: {exc}") from None
    try:
        sheets = [name for name in book.sheetnames if name.strip() == MILEX_SHEET]
        if len(sheets) != 1:
            raise SourceResponseError(f"SIPRI workbook {workbook.key!r} has {len(sheets)} {MILEX_SHEET!r} sheets ({book.sheetnames}); exactly one is read")
        return [tuple(row) for row in book[sheets[0]].iter_rows(values_only=True)]
    finally:
        book.close()


def milex_header(rows: list[tuple[Any, ...]], where: str) -> tuple[int, dict[int, int]]:
    """(header row index, year -> column): exactly one ``Country, Notes, <consecutive whole years>`` row covering the window."""
    if not rows or not isinstance(rows[0][0], str) or not rows[0][0].startswith(MILEX_TITLE):
        raise SourceResponseError(f"{where}: the sheet's title is {rows[0][0] if rows and rows[0] else None!r}, not {MILEX_TITLE!r}...")
    found = [i for i, row in enumerate(rows) if row and row[0] == "Country"]
    if len(found) != 1:
        raise SourceResponseError(f"{where}: {len(found)} header rows start 'Country'; exactly one is read")
    (at,) = found
    header = rows[at]
    labels = list(header[2:])
    if header[1] != "Notes" or not labels or any(isinstance(y, bool) or not isinstance(y, int) for y in labels):
        raise SourceResponseError(f"{where}: the header is not Country, Notes, then whole years: {list(header[:4])} ... {labels[-2:]}")
    if labels != list(range(labels[0], labels[0] + len(labels))):
        raise SourceResponseError(f"{where}: the header years are not consecutive: {labels}")
    if not (labels[0] <= MILEX_WINDOW[0] and MILEX_WINDOW[1] <= labels[-1]):
        raise SourceResponseError(f"{where}: the header years {labels[0]}-{labels[-1]} do not cover the window {MILEX_WINDOW[0]}-{MILEX_WINDOW[1]}")
    return at, {year: 2 + i for i, year in enumerate(labels) if MILEX_WINDOW[0] <= year <= MILEX_WINDOW[1]}


def normalize_milex_workbook(dataset: DatasetMetadata, workbook: WorkbookFile) -> NormalizationResult:
    """SIPRI_MILEXP observations from the pinned workbook (MILEXP-1, MILEXP-2, MILEXP-4)."""
    key = query_key(dataset)
    if workbook.key != key or key not in MILEX_WORKBOOKS:
        raise NormalizationError(f"{dataset.code}: workbook {workbook.key!r} is not the dataset's pinned {key!r}")
    if dataset.unit != MILEX_UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit {dataset.unit!r} is not {MILEX_UNIT!r}")
    source = workbook.source
    where = f"{dataset.code} workbook {source.filename} sheet {MILEX_SHEET!r}"
    rows = milex_sheet(workbook)
    at, columns = milex_header(rows, where)
    width = len(rows[at])
    observations: list[Observation] = []
    seen: dict[tuple[str, int], str] = {}
    names: set[str] = set()
    skipped: dict[tuple[str, str], None] = {}
    missing = 0
    for row in rows[at + 1 :]:
        if all(cell is None for cell in row):
            continue
        name = row[0]
        if not isinstance(name, str) or not name.strip():
            raise SourceResponseError(f"{where}: a row with values has no country name: {list(row[:4])}")
        if len(row) != width:
            raise SourceResponseError(f"{where}: row {name!r} has {len(row)} cells, the header {width}")
        if name in names:
            raise SourceResponseError(f"{where}: country name {name!r} appears twice")
        names.add(name)
        cells = {year: row[column] for year, column in columns.items()}
        if name in MILEX_REGION_ROWS:
            if any(cell is not None and cell not in MILEX_MARKERS for cell in cells.values()):
                raise SourceResponseError(f"{where}: region row {name!r} holds values; a region is never stored")
            continue
        code, corrected = milex_identity(name, where)
        if code is None:
            skipped.setdefault(("", name))
            continue
        for year, cell in cells.items():
            if isinstance(cell, str) and cell in MILEX_MARKERS:
                missing += 1
                continue
            if cell is None or isinstance(cell, bool) or not isinstance(cell, numbers.Real):
                raise SourceResponseError(f"{where}: ({name!r}, {year}) holds {cell!r}, which is neither a number nor one of SIPRI's markers {sorted(MILEX_MARKERS)}")
            published = float(cell)
            if not math.isfinite(published) or published < 0:
                raise SourceResponseError(f"{where}: ({name!r}, {year}) holds {cell!r}, not a share of GDP")
            if published >= 1 and MILEX_VERIFIED_LARGE_SHARES.get((name, year)) != published:
                raise SourceResponseError(f"{where}: ({name!r}, {year}) publishes {cell!r}, a share of GDP of 100% or more that has not been verified (MILEXP-2)")
            if (code, year) in seen:
                raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in {source.filename}: {seen[(code, year)]!r} and {name!r}")
            seen[(code, year)] = name
            provenance: dict[str, Any] = {
                "source_organization": ORGANIZATION_CODE,
                "source_workbook": source.filename,
                "source_edition": source.edition,
                "source_revised": source.revised,
                "source_url": source.url,
                "source_sha256": source.sha256,
                "source_sheet": MILEX_SHEET,
                "source_country_name": name,
                "source_notes": row[1],
                "source_year_column": year,
                "source_value": repr(cell),
                "scaling": MILEX_SCALING,
            }
            if published >= 1:
                provenance["verified_large_share"] = "MILEXP-2: a share of 100% of GDP or more, verified"
            if corrected:
                provenance["country_code_correction"] = MILEX_NAME_CORRECTION
            observations.append(Observation(dataset.code, code, year, published * 100, MILEX_UNIT, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, tuple(skipped), missing)


def normalize_arms_dataset(dataset: DatasetMetadata, response: SIPRIResponse) -> NormalizationResult:
    """Canonical observations for SIPRI_ARMEXP from a SIPRI arms-transfers response."""
    key = query_key(dataset)
    if response.key != key:
        raise NormalizationError(f"{dataset.code}: response {response.key!r} is not the dataset's {key!r}")
    if dataset.unit != LEGACY_UNIT:
        raise NormalizationError(f"{dataset.code}: canonical unit {dataset.unit!r} is not the legacy cleaner's literal {LEGACY_UNIT!r}")
    melted, kept = legacy_table(result_text(response))
    where = f"{dataset.code} SIPRI query {key!r}"
    resolved = {name: arms_code(name) for name in dict.fromkeys(melted["Country"])}
    codes = {name: code for name, (code, _) in resolved.items()}
    skipped = tuple(("", name) for name, code in codes.items() if code is None)
    missing = sum(1 for name, ok in zip(melted["Country"], melted.index.isin(kept.index), strict=True) if not ok and codes[name] is not None)
    observations: list[Observation] = []
    seen: set[tuple[str, int]] = set()
    for _, row in kept.iterrows():
        code = codes[row["Country"]]
        if code is None:
            continue
        if not _STORABLE_COUNTRY.match(code):
            raise NormalizationError(f"{where}: {row['Country']!r} matched {code!r}, which cannot be stored (three capital letters required; the legacy clean collection refused it too)")
        year, value = int(row["Year"]), float(row["Value"])
        if not math.isfinite(value):
            raise NormalizationError(f"{where}: ({code}, {year}) value {row['Cell']!r} is not finite")
        if (code, year) in seen:
            raise DuplicateObservationError(f"{dataset.code}: duplicate ({code}, {year}) in SIPRI query {key!r}: two supplier rows match {code}")
        seen.add((code, year))
        provenance = {
            "source_organization": ORGANIZATION_CODE,
            "source_query": key,
            "source_url": response.query.url,
            "source_description": response.query.description,
            "source_country_name": row["Country"],
            "source_value": str(row["Cell"]),
        }
        if resolved[row["Country"]][1]:
            provenance["country_code_correction"] = ARMS_CORRECTION
        observations.append(Observation(dataset.code, code, year, value, LEGACY_UNIT, provenance))
    observations.sort(key=lambda o: (o.country_code, o.year))
    return NormalizationResult(observations, skipped, missing)
