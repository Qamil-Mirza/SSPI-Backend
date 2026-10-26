"""The two executable Rights leaf indicators on the isolated database, with
the V-Dem archive served offline from the committed synthetic archive by a
mock transport, on a fixed run date. No network.

    sspi.ingest(["VDEM_RULELW", "VDEM_EDEMOC"])
    sspi.run("RULELW"), sspi.run("EDEMOC")
    sspi.query(indicators=["RULELW", "EDEMOC"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline in tests/unit/test_researcher_guide_rights.py). Stored
scores are compared with the legacy golden files exactly; re-ingesting and
re-running converge. PUBSRV, UNCONV and GENDEQ raise the explicit
unsupported errors. No Rights category score exists.
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import NotIngestibleError, SourceResponseError, UnknownCodeError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion.vdem import ARCHIVES, SourceArchive, VDemArchiveClient
from tests.unit.test_researcher_guide_rights import (
    documented_datasets,
    required_datasets,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
ARCHIVE = FIXTURES / "vdem" / "V-Dem-CY-FullOthers_csv_v13_synthetic.zip"
KEY = "V-Dem-CY-FullOthers_csv_v13"
RUN_DATE = date(2026, 10, 26)  # the date the golden files fixed the legacy clock to
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["RULELW", "EDEMOC"]
CASES = {code: json.loads((GOLDEN / f"{code.lower()}_synthetic_cases.json").read_text()) for code in INDICATORS}


class Server:
    """A mock v-dem.net answering the pinned address with the committed synthetic archive."""

    def __init__(self, content=None):
        self.requests, self.content = [], content or ARCHIVE.read_bytes()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        return httpx.Response(200, content=self.content) if str(request.url) == ARCHIVES[KEY].url else httpx.Response(404)

    def ingest(self, sspi, datasets, *, pinned_to=None):
        archives = {KEY: SourceArchive("synthetic test archive", ARCHIVES[KEY].url, pinned_to or hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(), None)}
        with httpx.Client(transport=httpx.MockTransport(self)) as http:
            return sspi.ingest(datasets, client=VDemArchiveClient(archives=archives, http=http, today=lambda: RUN_DATE))


def legacy_scores(*codes):
    """(indicator, country, year) -> score, observed and imputed, from the golden files."""
    return {(code, r["country_code"], r["year"]): r["score"] for code in codes for r in CASES[code]["observed_scores"] + CASES[code]["imputed_scores"]}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, unit, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_rights_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["VDEM_RULELW", "VDEM_EDEMOC"]
    server = Server()
    with SSPI(database=db) as sspi:
        ingestion = server.ingest(sspi, DATASETS)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(server.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert server.requests == fetched  # run() never ingests
        results = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        kosovo = sspi.query(datasets=["VDEM_RULELW"], countries=["XKX"], years=(2010, 2010), include_provenance=True)
        for blocked in ("PUBSRV", "UNCONV", "GENDEQ"):
            with pytest.raises(UnknownCodeError, match=blocked):
                sspi.run(blocked)
        for blocked in ("WGI_PUBSRV", "UNSDG_UNCONV", "IPU_WMPLMT", "WBL_WMMOBL"):
            with pytest.raises(NotIngestibleError, match=blocked):
                sspi.ingest([blocked])

    # one download serves both datasets
    assert ingestion.source_fetches == (KEY,) and server.requests == [ARCHIVES[KEY].url]
    assert ingestion.counts == {"VDEM_RULELW": 113, "VDEM_EDEMOC": 115}
    assert (len(runs["RULELW"].observed_scores), len(runs["RULELW"].imputed_scores), runs["RULELW"].written) == (113, 95, 208)
    assert (len(runs["EDEMOC"].observed_scores), len(runs["EDEMOC"].imputed_scores), runs["EDEMOC"].written) == (115, 95, 210)
    assert {(r.indicator_code, r.country_code, r.year): r.score for r in everything.itertuples()} == legacy_scores(*INDICATORS)

    # the researcher-facing frame: two leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in results.dtypes.items()} == INDICATOR_DTYPES and sorted(set(results["indicator_code"])) == sorted(INDICATORS)
    assert set(results["unit"]) == {"Index"}
    imputed = {(r.indicator_code, r.country_code, r.year) for r in results.itertuples() if r.imputed}
    assert imputed == {(c, "MYS", 2023) for c in INDICATORS} | {(c, "AUT", y) for c in INDICATORS for y in range(2016, 2024)}  # carried forward, flagged (RULELW-1, EDEMOC-1)
    assert ("RULELW", "USA", 2023) not in imputed and len(results) == 2 * (14 + 14 + 14)
    scores = {(r.indicator_code, r.country_code, r.year): r.score for r in results.itertuples()}
    assert scores[("RULELW", "AUT", 2023)] == scores[("RULELW", "AUT", 2015)] and scores[("EDEMOC", "MYS", 2023)] == scores[("EDEMOC", "MYS", 2022)]

    # what is stored: V-Dem's own code, the column and the run's year window
    (row,) = kosovo.itertuples()
    assert row.provenance["source_column"] == "v2x_rule" and row.provenance["source_country_name"] == "Kosovo" and row.provenance["source_years"] == [1991, 2025]


def test_reruns_converge_and_a_changed_archive_is_refused(db):
    server = Server()
    with SSPI(database=db) as sspi:
        assert sspi.run("RULELW").written == 0 == sspi.run("EDEMOC").written  # never ingested: nothing to score, no error
        server.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        first = counts(db)
        server.ingest(sspi, DATASETS)  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
            sspi.run(code)  # a second run replaces, never duplicates (legacy's second impute run did, RULELW-1)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and counts(db) == first == (113 + 115, 208 + 210)
        with pytest.raises(SourceResponseError, match="no other edition is substituted"):
            server.ingest(sspi, DATASETS, pinned_to=ARCHIVES[KEY].sha256)  # the synthetic bytes are not the pinned v13 archive
        assert counts(db) == first  # the failed refresh changed nothing
