"""REDLST end to end on the isolated database, with the UN SDG source served
from the committed fixture by a mock transport. No network.

    sspi.ingest("UNSDG_REDLST") -> canonical observations -> sspi.run("REDLST") -> scores -> sspi.query(...)
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.db import Repository
from sspi.errors import IndicatorDefinitionError
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion import UNSDGClient

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {name: json.loads((FIXTURES / f"{name.replace('.', '_')}_sample.json").read_text())["data"] for name in ("14.5.1", "15.1.2", "15.5.1")}
GOLDEN = json.loads((Path(__file__).parents[1] / "golden" / "redlst_cases.json").read_text())


class FixtureServer:
    def __init__(self, payloads=PAYLOADS):
        self.payloads, self.requests = payloads, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        indicator = request.url.params["indicator"]
        self.requests.append(indicator)
        rows = self.payloads[indicator]
        return httpx.Response(200, json={"size": 500, "totalElements": len(rows), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": rows})


def client_for(server) -> UNSDGClient:
    return UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(server)), sleep=lambda s: None)


def stored_scores(db):
    with db.transaction() as session:
        return session.execute(text("SELECT indicator_code, country_code, year, score, unit, imputed, inputs FROM indicator_score ORDER BY 1, 2, 3")).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


def test_ingest_redlst(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        result = sspi.ingest("UNSDG_REDLST", client=client_for(server))
        df = sspi.query(datasets=["UNSDG_REDLST"], countries=["MYS", "AUT"], years=(2018, 2023))
    assert result.datasets == ("UNSDG_REDLST",) and result.counts == {"UNSDG_REDLST": 230} and result.observations_written == 230
    assert result.source_fetches == ("15.5.1",) and server.requests == ["15.5.1"]
    (per,) = result.per_dataset
    assert per.source_query == "15.5.1" and per.skipped_areas == (("1", "World"), ("150", "Europe")) and per.missing_values > 0
    assert dtypes(df) == DATASET_DTYPES and len(df) == 12 and set(df["unit"]) == {"INDEX"}
    values = {(r.country_code, r.year): r.value for r in df.itertuples()}
    assert values[("MYS", 2018)] == 0.83317 and values[("MYS", 2023)] == 0.81645 and values[("AUT", 2020)] == 0.95275
    assert stored_scores(db) == []  # ingestion never computes


def test_redlst_workflow(db):
    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_REDLST", client=client_for(FixtureServer()))
        assert sspi.query(indicators=["REDLST"]).empty
        before = sspi.query(datasets=["UNSDG_REDLST"])

        run = sspi.run("REDLST")

        df = sspi.query(indicators=["REDLST"], countries=["MYS", "AUT"], years=(2018, 2023))
        everything = sspi.query(indicators=["REDLST"], include_inputs=True)
        after = sspi.query(datasets=["UNSDG_REDLST"])

    assert run.written == 230 == len(run.observed_scores) and run.imputed_scores == () and run.unscored == ()
    assert dtypes(df) == INDICATOR_DTYPES and len(df) == 12
    assert list(df["country_code"]) == ["AUT"] * 6 + ["MYS"] * 6 and list(df["year"]) == list(range(2018, 2024)) * 2
    assert set(df["unit"]) == {"Index"} and not df["imputed"].any()
    scores = {(r.country_code, r.year): r.score for r in df.itertuples()}
    assert scores[("MYS", 2018)] == 0.83317 and scores[("MYS", 2023)] == 0.81645
    assert scores[("AUT", 2018)] == 0.95597 and scores[("AUT", 2020)] == 0.95275 and scores[("AUT", 2023)] == 0.94826

    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == [(s["country_code"], s["year"], s["score"]) for s in GOLDEN["scores"]]
    assert sorted(set(everything["year"])) == list(range(1980, 2026))  # compute route: every available year
    assert not everything["imputed"].any()
    assert all(len(i) == 1 and i[0]["dataset_code"] == "UNSDG_REDLST" and i[0]["imputed"] is False for i in everything["inputs"])
    assert before.equals(after)  # canonical observations are source values, untouched by scoring
    assert all(row.imputed is False for row in stored_scores(db))


def test_missing_observations_stay_unscored(db):
    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_REDLST", client=client_for(FixtureServer()))
        with db.transaction() as session:
            session.execute(text("DELETE FROM observation WHERE dataset_code = 'UNSDG_REDLST' AND country_code = 'AUT' AND year BETWEEN 2010 AND 2015"))
            session.execute(text("DELETE FROM observation WHERE dataset_code = 'UNSDG_REDLST' AND country_code = 'KEN'"))  # an SSPI67 member with no rows at all
        run = sspi.run("REDLST")
        df = sspi.query(indicators=["REDLST"])
    assert run.written == 230 - 6 - 46 and run.imputed_scores == ()
    assert "KEN" not in set(df["country_code"]) and "CHE" not in set(df["country_code"])
    assert not set(df[df["country_code"] == "AUT"]["year"]) & set(range(2010, 2016))
    assert not df["imputed"].any()


def test_rerun_converges_and_removes_stale_rows(db):
    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_REDLST", client=client_for(FixtureServer()))
        sspi.run("REDLST")
        first = [tuple(r)[:6] for r in stored_scores(db)]
        assert sspi.run("REDLST").written == 230
        assert [tuple(r)[:6] for r in stored_scores(db)] == first
        with db.transaction() as session:
            session.execute(text("DELETE FROM observation WHERE country_code = 'ALB'"))
        assert sspi.run("REDLST").written == 184
        assert "ALB" not in {r.country_code for r in stored_scores(db)}


def test_redlst_and_biodiv_are_independent(db):
    with SSPI(database=db) as sspi:
        result = sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT", "UNSDG_REDLST"], client=client_for(FixtureServer()))
        assert result.source_fetches == ("14.5.1", "15.1.2", "15.5.1") and result.observations_written == 312 + 230
        assert sspi.run("BIODIV").written == 1590
        biodiv = sspi.query(indicators=["BIODIV"])
        assert sspi.run("REDLST").written == 230
        assert sspi.query(indicators=["BIODIV"]).equals(biodiv)
        both = sspi.query(indicators=["BIODIV", "REDLST"], countries=["AUT"], years=(2020, 2020))
    assert [(r.indicator_code, r.score, bool(r.imputed)) for r in both.itertuples()] == [("BIODIV", 0.5858737782051282, True), ("REDLST", 0.95275, False)]


def test_metadata_goalpost_drift_fails_the_run_and_writes_nothing(db):
    import dataclasses

    from sspi.metadata import MetadataCatalog

    class DriftedCatalog:
        def __init__(self, real):
            self.real = real

        def indicator(self, code):
            return dataclasses.replace(self.real.indicator(code), lower_goalpost=0.5)

    from sspi.indicators import run_indicator

    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_REDLST", client=client_for(FixtureServer()))
    with pytest.raises(IndicatorDefinitionError, match="goalposts"):
        run_indicator("REDLST", db, metadata=DriftedCatalog(MetadataCatalog.load()))
    assert stored_scores(db) == []
    with db.transaction() as session:
        assert len(Repository(session).get_observations(dataset_codes=["UNSDG_REDLST"])) == 230
