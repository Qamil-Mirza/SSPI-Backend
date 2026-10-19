"""The two executable Worker Wellbeing leaf indicators on the isolated
database, with the UN SDG API and the ILO SDMX API served from the committed
fixtures by a mock transport. No network.

    sspi.ingest(["UNSDG_BENFTS_UNEMP", "ILO_FATINJ"])
    sspi.run("UNEMPB"), sspi.run("FATINJ")
    sspi.query(indicators=["UNEMPB", "FATINJ"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_worker_wellbeing.py). Stored scores are
compared with the legacy golden files exactly. MATERN and SENIOR cannot be
run, and no Worker Wellbeing category score exists.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import ILOClient, UNSDGClient
from sspi.ingestion.ilo import BASE_URL as ILO_URL
from sspi.ingestion.unsdg import PIVOT_DATA_URL
from tests.unit.test_researcher_guide_worker_wellbeing import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["UNEMPB", "FATINJ"]
UNSDG_ROWS = json.loads((FIXTURES / "unsdg" / "1_3_1_sample.json").read_text(encoding="utf-8"))["data"]
ILO_CONTENT = (FIXTURES / "ilo" / "DF_SDG_F881_SEX_MIG_RT.json").read_bytes()
UNEMPB = json.loads((GOLDEN / "unempb_cases.json").read_text())
FATINJ = json.loads((GOLDEN / "fatinj_cases.json").read_text())


class Servers:
    """One mock transport serving the UN SDG pivot rows and the ILO response."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if url == PIVOT_DATA_URL and request.url.params["indicator"] == "1.3.1":
            self.requests.append("UNSDG 1.3.1")
            return httpx.Response(200, json={"size": 500, "totalElements": len(UNSDG_ROWS), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": UNSDG_ROWS})
        if url == ILO_URL + "DF_SDG_F881_SEX_MIG_RT" and request.url.params["format"] == "jsondata" and set(request.url.params) == {"format"}:
            self.requests.append("ILO DF_SDG_F881_SEX_MIG_RT")
            return httpx.Response(200, content=ILO_CONTENT, headers={"content-type": "application/json"})
        self.requests.append(str(request.url))
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"UNSDG": UNSDGClient(http=http, sleep=lambda s: None), "ILO": ILOClient(http=http)}


def legacy_scores():
    """(indicator, country, year) -> (score, unit, stored by the impute route)."""
    unempb = {("UNEMPB", r["country_code"], r["year"]): (r["score"], r["unit"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in UNEMPB[key]}
    fatinj = {("FATINJ", r["country_code"], r["year"]): (r["score"], r["unit"], False) for r in FATINJ["observed_scores"]}
    return {**unempb, **fatinj}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, unit, imputed, inputs FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_worker_wellbeing_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["UNSDG_BENFTS_UNEMP", "ILO_FATINJ"]
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(DATASETS, client=servers.clients())
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        wellbeing = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        benefits = sspi.query(datasets=["UNSDG_BENFTS_UNEMP"], countries=["USA"], years=(2019, 2019), include_provenance=True)
        injuries = sspi.query(datasets=["ILO_FATINJ"], countries=["MYS"], include_provenance=True)

    # one UN SDG request (one page here), one ILO request with no time window
    assert servers.requests == ["UNSDG 1.3.1", "ILO DF_SDG_F881_SEX_MIG_RT"] and ingestion.source_fetches == ("1.3.1", "Indicator=DF_SDG_F881_SEX_MIG_RT;Parameters=")
    assert ingestion.counts == {"UNSDG_BENFTS_UNEMP": 106, "ILO_FATINJ": 457}

    assert (len(runs["UNEMPB"].observed_scores), len(runs["UNEMPB"].imputed_scores), runs["UNEMPB"].written) == (106, 304, 410)
    assert (len(runs["FATINJ"].observed_scores), len(runs["FATINJ"].imputed_scores), runs["FATINJ"].written) == (457, 0, 457)
    assert {(r.indicator_code, r.country_code, r.year): (r.score, r.unit, r.imputed) for r in everything.itertuples()} == legacy_scores()

    # the researcher-facing frame: two leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in wellbeing.dtypes.items()} == INDICATOR_DTYPES and sorted(set(wellbeing["indicator_code"])) == sorted(INDICATORS)
    unempb = wellbeing[wellbeing.indicator_code == "UNEMPB"]
    fatinj = wellbeing[wellbeing.indicator_code == "FATINJ"]
    assert len(unempb) == 3 * 14  # every year filled for all three
    assert {(r.country_code, r.year) for r in fatinj.itertuples()} == {("MYS", 2022), ("USA", 2023)}  # FATINJ-1: Austria reports 2024 only
    malaysia = {r.year: r for r in unempb.itertuples() if r.country_code == "MYS"}
    assert {r.score for r in malaysia.values()} == {10.4 / 100} and [y for y, r in malaysia.items() if not r.imputed] == [2019]  # UNEMPB-3
    assert malaysia[2019].unit == "Benefits Coverage (%)" and malaysia[2023].unit == "Tax Rate"  # UNEMPB-1
    assert {r.score for r in fatinj.itertuples() if r.country_code == "USA"} == {(3.5 - 25) / (0 - 25)}

    # what is stored: the series and dimension with each observation; Iceland's mean; reported zeros
    (row,) = benefits.itertuples()
    assert row.value == 27.9 and row.unit == "PERCENT" and row.provenance["source_series"] == "SI_COV_UEMP" and row.provenance["source_dimensions"] == {"sex": "BOTHSEX"}
    (row,) = injuries.itertuples()
    assert (row.year, row.value, row.unit) == (2022, 14.58, "Rate per 100,000") and (row.provenance["SEX"], row.provenance["MIG"]) == ("SEX_T", "MIG_STATUS_TOTAL")
    scored = {(r.indicator_code, r.country_code, r.year): r for r in everything.itertuples()}
    (iceland,) = scored[("UNEMPB", "ISL", 2015)].inputs
    assert iceland["imputation_method"] == "ImputeReferenceClassAverage" and iceland["value"] == UNEMPB["reference_class"]["mean"]
    assert scored[("UNEMPB", "IND", 2019)].score == 0.0 and scored[("FATINJ", "ISL", 2011)].score == 1.0


def test_missing_datasets_behave_as_legacy_and_reruns_converge(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        assert sspi.run("FATINJ").written == 0  # never ingested: nothing to score, no error
        with pytest.raises(ImputationError, match="reference data for UNSDG_BENFTS_UNEMP/ISL is empty"):
            sspi.run("UNEMPB")  # the legacy impute route raised here too: no mean for Iceland
        assert counts(db) == (0, 0) and servers.requests == []
        sspi.ingest(DATASETS, client=servers.clients())
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        sspi.ingest(DATASETS, client=servers.clients())  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot
