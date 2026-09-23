"""Ingestion through the facade on the isolated database, with the UN SDG
source served from the committed fixtures by a mock transport. No network.

    sspi.ingest([...]) -> PostgreSQL -> sspi.query(datasets=...) -> sspi.run("BIODIV") -> sspi.query(indicators=...)
"""

import copy
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.db import Repository
from sspi.errors import NormalizationError, SourceResponseError
from sspi.ingestion import UNSDGClient
from sspi.ingestion.runner import IngestionRun
from sspi.scoring import Observation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}


class FixtureServer:
    """Serves the fixture rows for the requested SDG indicator on one page and records requests."""

    def __init__(self, payloads=PAYLOADS, broken: str | None = None):
        self.payloads, self.broken, self.requests = payloads, broken, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.params["indicator"])
        indicator = request.url.params["indicator"]
        if indicator == self.broken:
            return httpx.Response(200, json={"totalElements": "not-an-int", "data": []})
        rows = self.payloads[indicator]
        return httpx.Response(200, json={"size": 500, "totalElements": len(rows), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": rows})


def client_for(server) -> UNSDGClient:
    return UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(server)), sleep=lambda s: None)


def observation_count(db, dataset=None):
    with db.transaction() as session:
        return len(Repository(session).get_observations(dataset_codes=[dataset] if dataset else None))


def test_ingest_one_dataset(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        result = sspi.ingest("UNSDG_MARINE", client=client_for(server))
        df = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2020, 2020))
    assert isinstance(result, IngestionRun)
    assert result.datasets == ("UNSDG_MARINE",) and result.observations_written == 104 and result.counts == {"UNSDG_MARINE": 104}
    assert result.source_fetches == ("14.5.1",) and server.requests == ["14.5.1"]
    assert df["value"].item() == 19.70109


def test_ingest_all_three_biodiv_datasets_with_one_shared_fetch(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        result = sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], client=client_for(server))
    assert result.datasets == ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT")
    assert result.source_fetches == ("14.5.1", "15.1.2") and server.requests == ["14.5.1", "15.1.2"]  # 15.1.2 once for two datasets
    assert result.counts == {"UNSDG_MARINE": 104, "UNSDG_TERRST": 104, "UNSDG_FRSHWT": 104} and result.observations_written == 312
    per = {d.dataset_code: d for d in result.per_dataset}
    assert per["UNSDG_TERRST"].source_query == per["UNSDG_FRSHWT"].source_query == "15.1.2"
    assert per["UNSDG_MARINE"].skipped_areas == (("1", "World"), ("150", "Europe"))  # regional aggregates have no ISO3 code
    assert per["UNSDG_MARINE"].missing_values == 152  # empty source year entries, counted not stored
    assert all(len(d.skipped_areas) == 2 and d.missing_values == 152 for d in result.per_dataset)
    assert observation_count(db) == 312


def test_ingest_is_a_replace_and_reruns_converge(db):
    with db.transaction() as session:
        Repository(session).save_observations([Observation("UNSDG_MARINE", "ZZZ", 1990, 1.0, "PERCENT", {"note": "stale row not at the source"})])
    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_MARINE", client=client_for(FixtureServer()))
        first = sspi.query(datasets=["UNSDG_MARINE"])
        sspi.ingest("UNSDG_MARINE", client=client_for(FixtureServer()))
        second = sspi.query(datasets=["UNSDG_MARINE"])
    assert len(first) == 104 and "ZZZ" not in set(first["country_code"])
    assert first.equals(second) and observation_count(db, "UNSDG_MARINE") == 104


def test_malformed_source_response_writes_nothing(db):
    with db.transaction() as session:
        Repository(session).save_observations([Observation("UNSDG_MARINE", "ZZZ", 1990, 1.0, "PERCENT")])
    with SSPI(database=db) as sspi:
        with pytest.raises(SourceResponseError):
            sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], client=client_for(FixtureServer(broken="15.1.2")))
    assert observation_count(db) == 1  # marine was fetched fine but never written: the batch is all or nothing


def test_normalization_failure_writes_nothing(db):
    payloads = copy.deepcopy(PAYLOADS)
    payloads["15.1.2"][0]["units"] = "KM2"  # a freshwater row now disagrees with the canonical unit
    with SSPI(database=db) as sspi:
        with pytest.raises(NormalizationError, match="unit"):
            sspi.ingest(["UNSDG_MARINE", "UNSDG_FRSHWT"], client=client_for(FixtureServer(payloads)))
    assert observation_count(db) == 0


def test_persistence_failure_rolls_back_every_dataset_in_the_batch(db, monkeypatch):
    with db.transaction() as session:
        Repository(session).save_observations([Observation("UNSDG_MARINE", "ZZZ", 1990, 1.0, "PERCENT")])
    original = Repository.replace_dataset
    calls = []

    def fail_on_third(self, code, observations):
        calls.append(code)
        if len(calls) == 3:
            raise RuntimeError("simulated persistence failure")
        return original(self, code, observations)

    monkeypatch.setattr(Repository, "replace_dataset", fail_on_third)
    with SSPI(database=db) as sspi:
        with pytest.raises(RuntimeError, match="simulated"):
            sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], client=client_for(FixtureServer()))
    assert calls == ["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"]
    monkeypatch.undo()
    assert observation_count(db) == 1  # the stale marine row survived: nothing from the batch was committed


def test_ingest_never_touches_indicator_scores(db):
    with SSPI(database=db) as sspi:
        sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], client=client_for(FixtureServer()))
        sspi.run("BIODIV")
        with db.transaction() as session:
            before = session.execute(text("SELECT indicator_code, country_code, year, score, imputed, written_at FROM indicator_score ORDER BY 1, 2, 3")).all()
        sspi.ingest("UNSDG_MARINE", client=client_for(FixtureServer()))
        with db.transaction() as session:
            after = session.execute(text("SELECT indicator_code, country_code, year, score, imputed, written_at FROM indicator_score ORDER BY 1, 2, 3")).all()
    assert before == after and len(before) == 1590  # stale until sspi.run("BIODIV") is called again, by design


def test_v1_researcher_workflow(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], client=client_for(server))
        marine = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2018, 2023))
        run = sspi.run("BIODIV")
        df = sspi.query(indicators=["BIODIV"], countries=["MYS", "AUT"], years=(2018, 2023))
    assert ingestion.observations_written == 312 and len(marine) == 6 and run.written == 1590
    mys = df[(df["country_code"] == "MYS") & (df["year"] == 2020)].iloc[0]
    aut = df[(df["country_code"] == "AUT") & (df["year"] == 2020)].iloc[0]
    assert (mys["score"], bool(mys["imputed"])) == (0.2972865333333333, False)
    assert (aut["score"], bool(aut["imputed"])) == (0.5858737782051282, True)
