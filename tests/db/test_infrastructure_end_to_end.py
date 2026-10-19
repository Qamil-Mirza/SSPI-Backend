"""The three executable Infrastructure leaf indicators on the isolated
database, with the World Bank API and the WEF workbook served from the
committed fixtures by a mock transport. No network.

    sspi.ingest(["WB_AVELEC", "WEF_QUELEC", "WB_SANSRV", "WB_DRKWAT"])
    sspi.run("AQELEC"), sspi.run("SANSRV"), sspi.run("DRKWAT")
    sspi.query(indicators=["AQELEC", "SANSRV", "DRKWAT"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_infrastructure.py). Stored scores are
compared with the legacy golden files exactly. INTRNT and TRNETW cannot be
run, and no Infrastructure category score exists.

The WEF fixture is the synthetic workbook (GOV-2), so its checksum differs
from the original's, which the default configuration pins. The workflow
therefore injects a WEF client configured explicitly for the fixture (same
key, edition and address, the fixture's checksum); a separate test shows the
default configuration refusing it and storing nothing.
"""

import hashlib

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import NotIngestibleError, SourceResponseError, UnknownCodeError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import WEFWorkbookClient, WorldBankClient
from sspi.ingestion.wef import WORKBOOKS, SourceWorkbook
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_infrastructure import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures" / "wb"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["AQELEC", "SANSRV", "DRKWAT"]
SERIES = {"WB_AVELEC": "EG.ELC.ACCS.ZS", "WB_SANSRV": "SH.STA.BASS.ZS", "WB_DRKWAT": "SH.H2O.SMDW.ZS"}
WEF_KEY = "WEF-GCIHH_2023-07-17"
WEF_CONTENT = (Path(__file__).parents[1] / "fixtures" / "wef" / "WEF-GCIHH_synthetic.xlsx").read_bytes()
WEF_FIXTURE_WORKBOOKS = {WEF_KEY: SourceWorkbook(WORKBOOKS[WEF_KEY].edition, WORKBOOKS[WEF_KEY].url, hashlib.sha256(WEF_CONTENT).hexdigest())}
AQELEC = json.loads((GOLDEN / "aqelec_synthetic_cases.json").read_text())
SANSRV = json.loads((GOLDEN / "sansrv_cases.json").read_text())
DRKWAT = json.loads((GOLDEN / "drkwat_cases.json").read_text())


class Server:
    """A mock World Bank API and WEF workbook host answering from the committed fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0])
        if url == WORKBOOKS[WEF_KEY].url:
            return httpx.Response(200, content=WEF_CONTENT)
        for series in SERIES.values():
            if url.startswith(WB_URL + series + "?"):
                return httpx.Response(200, content=(FIXTURES / f"{series}_sample.json").read_bytes())
        return httpx.Response(404)

    def ingest(self, sspi, datasets, workbooks=WEF_FIXTURE_WORKBOOKS):
        http = httpx.Client(transport=httpx.MockTransport(self))
        try:
            return sspi.ingest(datasets, client={"WB": WorldBankClient(http=http), "WEF": WEFWorkbookClient(workbooks=workbooks, http=http)})
        finally:
            http.close()


def legacy_scores():
    """(indicator, country, year) -> (score, stored by the impute route)."""
    sansrv = {("SANSRV", r["country_code"], r["year"]): (r["score"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in SANSRV[key]}
    aqelec = {("AQELEC", r["country_code"], r["year"]): (r["score"], False) for r in AQELEC["observed_scores"]}
    return {**aqelec, **sansrv, **{("DRKWAT", r["country_code"], r["year"]): (r["score"], False) for r in DRKWAT["scores"]}}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, unit, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_infrastructure_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["WB_AVELEC", "WEF_QUELEC", "WB_SANSRV", "WB_DRKWAT"]
    server = Server()
    with SSPI(database=db) as sspi:
        ingestion = server.ingest(sspi, DATASETS)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(server.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert server.requests == fetched  # run() never ingests
        infrastructure = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)

    assert ingestion.source_fetches == ("EG.ELC.ACCS.ZS", WEF_KEY, "SH.STA.BASS.ZS", "SH.H2O.SMDW.ZS")
    assert server.requests == [WB_URL + "EG.ELC.ACCS.ZS", WORKBOOKS[WEF_KEY].url, WB_URL + "SH.STA.BASS.ZS", WB_URL + "SH.H2O.SMDW.ZS"]
    assert ingestion.counts == {"WB_AVELEC": 209, "WEF_QUELEC": 46, "WB_SANSRV": 355, "WB_DRKWAT": 274}

    assert (len(runs["AQELEC"].observed_scores), len(runs["AQELEC"].imputed_scores), len(runs["AQELEC"].unscored), runs["AQELEC"].written) == (30, 0, 195, 30)

    assert (len(runs["SANSRV"].observed_scores), len(runs["SANSRV"].imputed_scores), runs["SANSRV"].written) == (355, 42, 397)
    assert (len(runs["DRKWAT"].observed_scores), len(runs["DRKWAT"].imputed_scores), runs["DRKWAT"].written) == (274, 0, 274)
    assert {(r.indicator_code, r.country_code, r.year): (r.score, r.imputed) for r in everything.itertuples()} == legacy_scores()

    # the researcher-facing frame: three leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in infrastructure.dtypes.items()} == INDICATOR_DTYPES and sorted(set(infrastructure["indicator_code"])) == sorted(INDICATORS)
    aqelec_years = {c: sorted(infrastructure[(infrastructure.indicator_code == "AQELEC") & (infrastructure.country_code == c)]["year"]) for c in ("MYS", "AUT", "USA")}
    assert aqelec_years == {"MYS": list(range(2010, 2018)), "AUT": [2015, 2016, 2017], "USA": list(range(2010, 2018))}  # nothing after 2017
    assert len(infrastructure) == 2 * 3 * 14 + 19 and not infrastructure["imputed"].any()  # SANSRV and DRKWAT every year
    assert {c: set(infrastructure[infrastructure.indicator_code == c]["unit"]) for c in INDICATORS} == {"AQELEC": {"Index"}, "SANSRV": {"Percent"}, "DRKWAT": {"%"}}
    mys = {(r.indicator_code, r.year): r.score for r in infrastructure.itertuples() if r.country_code == "MYS"}
    assert mys[("SANSRV", 2023)] == (96.0191440152349 - 50) / 50 and mys[("DRKWAT", 2023)] == 0.9462046640002271
    assert mys[("AQELEC", 2010)] == 0.8411213990843621 and ("AQELEC", 2018) not in mys

    # what is stored: Argentina's 2016 sanitation value carried to 2023; no DRKWAT before the United States' series starts
    scored = {(r.indicator_code, r.country_code, r.year): r for r in everything.itertuples()}
    (carried,) = scored[("SANSRV", "ARG", 2023)].inputs
    assert scored[("SANSRV", "ARG", 2023)].imputed and (carried["imputation_method"], carried["value"]) == ("Forward Extrapolation", 94.8209557204549)
    (row,) = [r for r in stored(db, "SANSRV") if (r.country_code, r.year) == ("ARG", 2023)]
    (snapshot,) = row.inputs["observations"]
    assert row.imputed and (snapshot["provenance"]["anchor_year"], snapshot["provenance"]["imputation_distance"]) == (2016, 7)
    assert not any(("DRKWAT", "USA", year) in scored for year in range(2000, 2005)) and ("DRKWAT", "USA", 2005) in scored
    assert sorted((i["dataset_code"], i["value"]) for i in scored[("AQELEC", "USA", 2017)].inputs) == [("WB_AVELEC", 100.0), ("WEF_QUELEC", 7.0)]
    (row,) = [r for r in stored(db, "AQELEC") if (r.country_code, r.year) == ("USA", 2017)]
    wef = next(o for o in row.inputs["observations"] if o["dataset_code"] == "WEF_QUELEC")
    assert (wef["provenance"]["source_file"], wef["provenance"]["source_sha256"]) == (WEF_KEY, hashlib.sha256(WEF_CONTENT).hexdigest())


def test_the_default_configuration_refuses_any_workbook_but_the_pinned_edition(db):
    server = Server()
    with SSPI(database=db) as sspi:
        with pytest.raises(SourceResponseError, match="no other edition is substituted"):
            server.ingest(sspi, ["WEF_QUELEC"], workbooks=None)  # WORKBOOKS: the original's checksum, not the fixture's
    assert counts(db) == (0, 0) and server.requests == [WORKBOOKS[WEF_KEY].url]


def test_the_blocked_leaves_cannot_be_ingested_or_run(db):
    with SSPI(database=db) as sspi:
        for dataset in ("UNSDG_AVINTR", "CABLE_QUINTR", "CIA_ROADNT"):
            with pytest.raises(NotIngestibleError):
                sspi.ingest([dataset])
        for dataset in ("WB_RAILNT",):
            with pytest.raises(NotIngestibleError, match="no complete definition"):
                sspi.ingest([dataset])
        for dataset in ("WB_INTRNT", "UNSDG_INTRNT"):  # what the legacy INTRNT route read; not in the canonical catalog
            with pytest.raises(UnknownCodeError):
                sspi.ingest([dataset])
        for indicator in ("INTRNT", "TRNETW"):
            with pytest.raises(UnknownCodeError):
                sspi.run(indicator)
    assert counts(db) == (0, 0)


def test_missing_inputs_behave_as_legacy_and_reruns_converge(db):
    server = Server()
    with SSPI(database=db) as sspi:
        assert sspi.run("SANSRV").written == 0 == sspi.run("DRKWAT").written == sspi.run("AQELEC").written  # never ingested: nothing to score, no error
        server.ingest(sspi, ["WEF_QUELEC"])
        quality_only = sspi.run("AQELEC")
        assert quality_only.written == 0 and len(quality_only.unscored) == 46  # one input alone scores nothing, as in legacy
        server.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        first = counts(db)
        server.ingest(sspi, DATASETS)  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and counts(db) == first == (209 + 46 + 355 + 274, 30 + 397 + 274)
