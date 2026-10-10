"""The four Education leaf indicators on the isolated database, with
the UIS and World Bank sources served from the committed fixtures by a mock
transport. No network.

    sspi.ingest(["UIS_ENRPRI", "UIS_ENRSEC", "WB_PUPTCH", "UIS_YRSEDU"])
    sspi.run("ENRPRI"), sspi.run("ENRSEC"), sspi.run("PUPTCH"), sspi.run("YRSEDU")
    sspi.query(indicators=[...], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_education.py). Stored scores are compared
with the legacy golden files exactly. No Education category score exists.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import UISClient, WorldBankClient
from sspi.ingestion.uis import BASE_URL as UIS_URL
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_education import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU"]
RELEASE = json.loads((FIXTURES / "uis" / "versions_default.json").read_text())["version"]
LEGACY = {code: json.loads((GOLDEN / f"{code.lower()}_cases.json").read_text()) for code in INDICATORS}
EXPECTED = {"ENRPRI": (179, 258), "ENRSEC": (120, 255), "PUPTCH": (358, 231), "YRSEDU": (336, 37)}


def legacy_scores(code):
    """(score, stored by the impute route) by identity."""
    return {(r["country_code"], r["year"]): (r["score"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in LEGACY[code][key]}


class Servers:
    """One mock transport serving the UIS and World Bank fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0] + (f"?indicator={request.url.params['indicator']}" if "indicator" in request.url.params else ""))
        if url == UIS_URL + "versions/default":
            return httpx.Response(200, content=(FIXTURES / "uis" / "versions_default.json").read_bytes())
        if url.startswith(UIS_URL + "data/indicators?") and request.url.params.get("version") == RELEASE:
            path = FIXTURES / "uis" / f"{request.url.params['indicator']}_sample.json"
            return httpx.Response(200, content=path.read_bytes()) if path.exists() else httpx.Response(404)
        if url.startswith(WB_URL + "SE.PRM.ENRL.TC.ZS?"):
            return httpx.Response(200, content=(FIXTURES / "wb" / "SE.PRM.ENRL.TC.ZS_sample.json").read_bytes())
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"UIS": UISClient(http=http), "WB": WorldBankClient(http=http)}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, inputs FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_education_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == ["UIS_ENRPRI", "UIS_ENRSEC", "WB_PUPTCH", "UIS_YRSEDU"] and tuple(DATASETS) == required_datasets()
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(DATASETS, client=servers.clients())
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        education = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = {code: sspi.query(indicators=[code], include_inputs=True, include_provenance=True) for code in INDICATORS}
        malaysia = sspi.query(datasets=["UIS_ENRSEC"], countries=["MYS"], years=(2023, 2023), include_provenance=True)

    # one release lookup, one request per UIS indicator, one World Bank request
    assert ingestion.source_fetches == ("NERT.1.CP", "NERT.2.CP", "SE.PRM.ENRL.TC.ZS", "YEARS.FC.COMP.1T3")
    assert servers.requests == [
        UIS_URL + "versions/default",
        UIS_URL + "data/indicators?indicator=NERT.1.CP",
        UIS_URL + "data/indicators?indicator=NERT.2.CP",
        WB_URL + "SE.PRM.ENRL.TC.ZS",
        UIS_URL + "data/indicators?indicator=YEARS.FC.COMP.1T3",
    ]
    assert ingestion.counts == {"UIS_ENRPRI": 179, "UIS_ENRSEC": 120, "WB_PUPTCH": 358, "UIS_YRSEDU": 336}

    for code, run in runs.items():
        assert (len(run.observed_scores), len(run.imputed_scores), run.written) == (*EXPECTED[code], sum(EXPECTED[code]))
        frame = everything[code]
        assert {(r.country_code, r.year): (r.score, r.imputed) for r in frame.itertuples()} == legacy_scores(code) and len(frame) == sum(EXPECTED[code])

    # the researcher-facing frame: four leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in education.dtypes.items()} == INDICATOR_DTYPES and sorted(set(education["indicator_code"])) == INDICATORS
    assert len(education) == 4 * 3 * 14 and {c: set(education[education.indicator_code == c]["unit"]) for c in INDICATORS} == {"ENRPRI": {"%"}, "ENRSEC": {"Percent"}, "PUPTCH": {"Ratio"}, "YRSEDU": {"Years"}}
    imputed = {(r.indicator_code, r.country_code, r.year) for r in education.itertuples() if r.imputed}
    expected = {(code, c, y) for code in INDICATORS for (c, y), (_, was_imputed) in legacy_scores(code).items() if was_imputed and c in ("MYS", "AUT", "USA") and 2010 <= y <= 2023}
    assert imputed == expected
    assert {(i, c, y) for i, c, y in imputed if i in ("ENRPRI", "ENRSEC")} == {(i, "USA", y) for i in ("ENRPRI", "ENRSEC") for y in (2010, 2011, 2012, 2023)}  # UIS: MYS and AUT complete to 2024, USA has a 2010-2012 gap and ends in 2022

    # what is stored with a score: China and Nigeria in ENRSEC
    enrsec = {(r.country_code, r.year): r for r in everything["ENRSEC"].itertuples()}
    china = enrsec[("CHN", 2015)]
    (mean,) = china.inputs
    assert china.imputed and mean["imputation_method"] == "ImputeReferenceClassAverage" and mean["value"] == LEGACY["ENRSEC"]["reference_class"]["mean"]
    assert {r.year for r in everything["ENRSEC"].itertuples() if r.country_code == "NGA"} == set(range(2000, 2024))
    yrsedu = {(r.country_code, r.year): r for r in everything["YRSEDU"].itertuples()}
    assert not any(r.imputed for r in education.itertuples() if r.indicator_code == "YRSEDU")  # all three countries report every year
    assert [(yrsedu[("MYS", y)].inputs[0]["value"], yrsedu[("MYS", y)].imputed) for y in (2002, 2003)] == [(6.0, True), (6.0, False)]  # UIS says 0 in 2002 (YRSEDU-1)
    (row,) = malaysia.itertuples()
    assert row.unit == "Percent" and row.provenance["source_version"] == RELEASE and row.provenance["source_indicator"] == "NERT.2.CP"


def test_missing_datasets_behave_as_legacy_and_reruns_converge(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        assert sspi.run("ENRPRI").written == sspi.run("PUPTCH").written == sspi.run("YRSEDU").written == 0  # never ingested: nothing to score
        with pytest.raises(ImputationError, match="reference data for UIS_ENRSEC/CHN is empty"):
            sspi.run("ENRSEC")  # the legacy impute route raised here too: no mean to give China and Nigeria
        assert counts(db) == (0, 0)
        sspi.ingest(DATASETS, client=servers.clients())
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        sspi.ingest(DATASETS, client=servers.clients())  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot
