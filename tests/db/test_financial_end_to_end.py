"""The two executable Financial Sector leaf indicators on the isolated
database, with the World Bank API served from the committed samples by a
mock transport. No network.

    sspi.ingest(["WB_CREDIT", "WB_DPOSIT", "WB_PUBACC"])
    sspi.run("FDEPTH"), sspi.run("PUBACC")
    sspi.query(indicators=["FDEPTH", "PUBACC"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_financial.py). Stored scores are compared
with the legacy golden files exactly. FSTABL cannot be run, and no
Financial Sector category score exists.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import WorldBankClient
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_financial import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures" / "wb"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["FDEPTH", "PUBACC"]
SERIES = {"WB_CREDIT": "FS.AST.PRVT.GD.ZS", "WB_DPOSIT": "GFDD.OI.02", "WB_PUBACC": "FX.OWN.TOTL.ZS"}
FDEPTH = json.loads((GOLDEN / "fdepth_cases.json").read_text())
PUBACC = json.loads((GOLDEN / "pubacc_cases.json").read_text())


class Server:
    """A mock World Bank API answering the three requested indicators from the committed samples."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0])
        for series in SERIES.values():
            if url.startswith(WB_URL + series + "?"):
                return httpx.Response(200, content=(FIXTURES / f"{series}_sample.json").read_bytes())
        return httpx.Response(404)

    def ingest(self, sspi, datasets):
        with WorldBankClient(http=httpx.Client(transport=httpx.MockTransport(self))) as client:
            return sspi.ingest(datasets, client=client)


def legacy_scores():
    """(indicator, country, year) -> score; legacy stored no imputed score for either indicator."""
    return {**{("FDEPTH", r["country_code"], r["year"]): r["score"] for r in FDEPTH["observed_scores"]}, **{("PUBACC", r["country_code"], r["year"]): r["score"] for r in PUBACC["scores"]}}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, unit, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_financial_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["WB_CREDIT", "WB_DPOSIT", "WB_PUBACC"]
    server = Server()
    with SSPI(database=db) as sspi:
        ingestion = server.ingest(sspi, DATASETS)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(server.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert server.requests == fetched  # run() never ingests
        results = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        deposits = sspi.query(datasets=["WB_DPOSIT"], countries=["MYS"], years=(2021, 2021), include_provenance=True)

    # one World Bank request per dataset
    assert ingestion.source_fetches == tuple(SERIES.values())
    assert server.requests == [WB_URL + series for series in SERIES.values()]
    assert ingestion.counts == {"WB_CREDIT": 625, "WB_DPOSIT": 616, "WB_PUBACC": 61}

    assert (len(runs["FDEPTH"].observed_scores), len(runs["FDEPTH"].imputed_scores), len(runs["FDEPTH"].unscored), runs["FDEPTH"].written) == (422, 0, 397, 422)
    assert (len(runs["PUBACC"].observed_scores), len(runs["PUBACC"].imputed_scores), runs["PUBACC"].written) == (61, 0, 61)
    assert {(r.indicator_code, r.country_code, r.year): r.score for r in everything.itertuples()} == legacy_scores()
    assert not everything["imputed"].any()

    # the researcher-facing frame: two leaf indicators, three countries, 2010-2023; no category score, no FSTABL
    assert {c: str(t) for c, t in results.dtypes.items()} == INDICATOR_DTYPES and sorted(set(results["indicator_code"])) == INDICATORS
    years = {(r.indicator_code, r.country_code): sorted(results[(results.indicator_code == r.indicator_code) & (results.country_code == r.country_code)]["year"]) for r in results.itertuples()}
    assert years[("FDEPTH", "MYS")] == years[("FDEPTH", "AUT")] == list(range(2010, 2022))  # the deposit series ends in 2021
    assert years[("FDEPTH", "USA")] == list(range(2010, 2021))  # and in 2020 for the United States
    assert years[("PUBACC", "MYS")] == years[("PUBACC", "AUT")] == years[("PUBACC", "USA")] == [2011, 2014, 2017, 2021]  # Findex survey waves only
    assert len(results) == 12 + 12 + 11 + 3 * 4 and not results["imputed"].any()
    assert {c: set(results[results.indicator_code == c]["unit"]) for c in INDICATORS} == {"FDEPTH": {"Index"}, "PUBACC": {"Percent"}}
    mys = {(r.indicator_code, r.year): r.score for r in results.itertuples() if r.country_code == "MYS"}
    assert mys[("FDEPTH", 2021)] == 127.260894609567 / 200 / 2 + 1.0 / 2 and mys[("PUBACC", 2021)] == 88.3748841160555 / 100

    # what is stored: both inputs with every FDEPTH score; the series and description with each observation
    scored = {(r.indicator_code, r.country_code, r.year): r for r in everything.itertuples()}
    assert sorted((i["dataset_code"], i["value"]) for i in scored[("FDEPTH", "MYS", 2021)].inputs) == [("WB_CREDIT", 127.260894609567), ("WB_DPOSIT", 122.5862)]
    (row,) = deposits.itertuples()
    assert row.value == 122.5862 and row.unit == "Percent"
    assert {k: row.provenance[k] for k in ("source_organization", "source_indicator", "description")} == {"source_organization": "WB", "source_indicator": "GFDD.OI.02", "description": "Bank deposits to GDP (%)"}


def test_fstabl_cannot_be_ingested_or_run(db):
    with SSPI(database=db) as sspi:
        with pytest.raises(NotIngestibleError, match="no complete definition"):
            sspi.ingest(["IMF_FSTABL"])
        with pytest.raises(UnknownCodeError):
            sspi.ingest(["WB_FSTABL"])  # the legacy World Bank collector's dataset is not in the canonical catalog
        with pytest.raises(UnknownCodeError):
            sspi.run("FSTABL")
    assert counts(db) == (0, 0)


def test_missing_inputs_behave_as_legacy_and_reruns_converge(db):
    server = Server()
    with SSPI(database=db) as sspi:
        assert sspi.run("FDEPTH").written == 0 == sspi.run("PUBACC").written  # never ingested: nothing to score, no error
        server.ingest(sspi, ["WB_CREDIT"])
        credit_only = sspi.run("FDEPTH")
        assert credit_only.written == 0 and len(credit_only.unscored) == 625  # one input alone scores nothing, as in legacy
        assert counts(db) == (625, 0)
        server.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        first = counts(db)
        server.ingest(sspi, DATASETS)  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and counts(db) == first == (625 + 616 + 61, 422 + 61)
