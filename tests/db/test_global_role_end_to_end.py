"""The two registered Global Role leaf indicators on the isolated database,
with every source served offline by mock transports: the SIPRI arms-transfers
API from the committed synthetic answer and the UN SDG API from the committed
verbatim 9.5.1 and 9.5.2 samples. No network.

    sspi.ingest(["SIPRI_ARMEXP", "UNSDG_RDPGDP", "UNSDG_NRSRCH"])
    sspi.run("RDFUND"), sspi.run("ARMEXP")
    sspi.query(indicators=["ARMEXP", "RDFUND"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example. Stored scores are compared
with the legacy golden files exactly; re-ingesting and re-running converge.
ARMEXP runs observed-only (approved execution treatment, ARMEXP-2), also when
a hard-coded reference-class country has data. MILEXP and FORAID raise the
explicit unsupported errors. No Global Role category score exists.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion.sipri import QUERIES, SIPRIClient
from sspi.ingestion.unsdg import UNSDGClient
from tests.unit.test_researcher_guide_global_role import (
    documented_datasets,
    required_datasets,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
ARMS = FIXTURES / "sipri" / "armstransfers_synthetic.json"
PAYLOADS = {name: json.loads((FIXTURES / "unsdg" / f"{name.replace('.', '_')}_sample.json").read_text())["data"] for name in ("9.5.1", "9.5.2")}
DATASETS = list(documented_datasets())
INDICATORS = ["ARMEXP", "RDFUND"]
# ARMEXP: the legacy compute route on the legacy cleaner's rows with the approved ARMEXP-4 name table (observed only).
CASES = {"ARMEXP": json.loads((GOLDEN / "sipri_armexp_corrected_synthetic_cases.json").read_text()), "RDFUND": json.loads((GOLDEN / "rdfund_cases.json").read_text())}


def build_answer(variant=None):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sipri_build_synthetic", FIXTURES / "sipri" / "build_synthetic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build("armstransfers", variant)


class Servers:
    """A mock SIPRI API and UN SDG API answering from the committed fixtures."""

    def __init__(self, arms=None):
        self.requests, self.arms = [], arms or ARMS.read_bytes()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == QUERIES["armstransfers"].url:
            self.requests.append(("SIPRI", json.loads(request.content)))
            return httpx.Response(200, content=self.arms)
        indicator = request.url.params["indicator"]
        self.requests.append(("UNSDG", indicator))
        rows = PAYLOADS[indicator]
        return httpx.Response(200, json={"size": 500, "totalElements": len(rows), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": rows})

    def ingest(self, sspi, datasets):
        with httpx.Client(transport=httpx.MockTransport(self)) as http:
            return sspi.ingest(datasets, client={"SIPRI": SIPRIClient(http=http), "UNSDG": UNSDGClient(http=http, sleep=lambda s: None)})


def legacy_scores(*codes):
    """Observed and imputed scores from the golden files; ARMEXP's observed only (observed-only execution)."""
    return {(code, r["country_code"], r["year"]): r["score"] for code in codes for r in CASES[code]["observed_scores"] + (CASES[code]["imputed_scores"] if code != "ARMEXP" else [])}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, unit, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_global_role_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)
    assert DATASETS == list(required_datasets()) == ["SIPRI_ARMEXP", "UNSDG_RDPGDP", "UNSDG_NRSRCH"]
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = servers.ingest(sspi, DATASETS)
        assert sspi.query(indicators=INDICATORS).empty
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in ("RDFUND", "ARMEXP")}
        assert servers.requests == fetched  # run() never ingests
        results = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        korea = sspi.query(datasets=["SIPRI_ARMEXP"], countries=["PRK"], years=(2024, 2024), include_provenance=True)
        for blocked in ("MILEXP", "FORAID"):
            with pytest.raises(UnknownCodeError, match=blocked):
                sspi.run(blocked)
        for blocked in ("SIPRI_MILEXP", "OECD_TOTDON", "OECD_TONREC", "WB_GDPMKT"):
            with pytest.raises(NotIngestibleError, match=blocked):
                sspi.ingest([blocked])

    assert ingestion.source_fetches == ("armstransfers", "9.5.1", "9.5.2")
    assert servers.requests[0] == ("SIPRI", QUERIES["armstransfers"].payload)  # the legacy collector's request
    assert ingestion.counts == {"SIPRI_ARMEXP": 134, "UNSDG_RDPGDP": 140, "UNSDG_NRSRCH": 93}
    assert (len(runs["ARMEXP"].observed_scores), len(runs["ARMEXP"].imputed_scores), runs["ARMEXP"].written) == (134, 0, 134)
    assert (len(runs["RDFUND"].observed_scores), len(runs["RDFUND"].imputed_scores), runs["RDFUND"].written) == (90, 127, 217)
    assert {(r.indicator_code, r.country_code, r.year): r.score for r in everything.itertuples()} == legacy_scores(*INDICATORS)

    assert {c: str(t) for c, t in results.dtypes.items()} == INDICATOR_DTYPES and sorted(set(results["indicator_code"])) == INDICATORS
    assert {c: set(results[results.indicator_code == c]["unit"]) for c in INDICATORS} == {"ARMEXP": {"Expenditure"}, "RDFUND": {"Index"}}
    assert not results[results.indicator_code == "ARMEXP"]["imputed"].any() and not {("MYS", 2010), ("MYS", 2023)} & {(r.country_code, r.year) for r in results.itertuples() if r.indicator_code == "ARMEXP"}  # not filled, not zero
    rd = {(r.country_code, r.year): (r.score, r.imputed) for r in results.itertuples() if r.indicator_code == "RDFUND"}
    assert rd[("AUT", 2023)][1] is False and rd[("USA", 2023)][1] is True and rd[("MYS", 2023)][1] is True
    (row,) = korea.itertuples()
    assert row.value == 211.0 and row.provenance["source_country_name"] == "North Korea" and row.provenance["source_query"] == "armstransfers"


def test_armexp_runs_observed_only_when_a_listed_country_exports_and_reruns_converge(db):
    with SSPI(database=db) as sspi:
        Servers(build_answer("probe_are_exports")).ingest(sspi, ["SIPRI_ARMEXP"])
        run = sspi.run("ARMEXP")  # the legacy impute route refused this data; the observed-only execution scores it (ARMEXP-2)
        assert (len(run.observed_scores), run.imputed_scores, run.written) == (137, (), 137)
        assert sorted(sspi.query(indicators=["ARMEXP"], countries=["ARE"])["year"]) == [2001, 2005, 2015]
    servers = Servers()
    with SSPI(database=db) as sspi:
        servers.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        first = counts(db)
        servers.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and counts(db) == first == (134 + 140 + 93, 134 + 217)
