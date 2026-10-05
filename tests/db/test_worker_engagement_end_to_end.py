"""EMPLOY and COLBAR on the isolated database, with the ILO SDMX API served
from the committed responses by a mock transport. No network.

    sspi.ingest("ILO_EMPLOY_TO_POP") -> sspi.run("EMPLOY")
    sspi.ingest("ILO_COLBAR")        -> sspi.run("COLBAR")
    sspi.query(...)

Stored scores are compared with the legacy golden files exactly.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion import ILOClient
from sspi.ingestion.ilo import BASE_URL

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ilo"
GOLDEN = Path(__file__).parents[1] / "golden"
RESPONSES = {
    BASE_URL + "DF_EMP_DWAP_SEX_AGE_RT/.A..SEX_T.AGE_YTHADULT_Y15-64": (FIXTURES / "DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json").read_bytes(),
    BASE_URL + "DF_ILR_CBCT_NOC_RT": (FIXTURES / "DF_ILR_CBCT_NOC_RT.json").read_bytes(),
}
CASES = {
    # indicator: (dataset, observations, imputed scores, observed unit)
    "EMPLOY": ("ILO_EMPLOY_TO_POP", 2690, 2576, "Percentage"),
    "COLBAR": ("ILO_COLBAR", 865, 1511, "%"),
}


class Server:
    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        self.requests.append(url)
        if url in RESPONSES and request.url.params["format"] == "jsondata":
            return httpx.Response(200, content=RESPONSES[url], headers={"content-type": "application/json"})
        return httpx.Response(404)

    def client(self):
        return ILOClient(http=httpx.Client(transport=httpx.MockTransport(self)))


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, unit, imputed, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


@pytest.mark.parametrize("indicator", sorted(CASES))
def test_ingest_run_query_matches_legacy_exactly(db, indicator):
    dataset, observation_count, imputed_count, unit = CASES[indicator]
    golden = json.loads((GOLDEN / f"{indicator.lower()}_cases.json").read_text())
    server = Server()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(dataset, client=server.client())
        assert sspi.query(indicators=[indicator]).empty  # ingest() never runs an indicator
        requests_before_run = list(server.requests)
        run = sspi.run(indicator)
        assert server.requests == requests_before_run and len(server.requests) == 1  # one request; run() never ingests
        everything = sspi.query(indicators=[indicator], include_inputs=True, include_provenance=True)
        observations = sspi.query(datasets=[dataset], include_provenance=True)
        again = sspi.run(indicator)
    assert ingestion.counts == {dataset: observation_count} and ingestion.source_fetches == (sspi.dataset(dataset).source.query_code,)
    assert ingestion.per_dataset[0].skipped_areas == () and ingestion.per_dataset[0].missing_values == 0
    assert len(run.observed_scores) == observation_count and len(run.imputed_scores) == imputed_count and run.unscored == ()
    assert run.written == again.written == observation_count + imputed_count == len(everything)
    assert dtypes(everything.drop(columns=["inputs", "provenance"])) == INDICATOR_DTYPES

    observed = {(r["country_code"], r["year"]): r for r in golden["observed_scores"]}
    imputed = {(r["country_code"], r["year"]): r for r in golden["imputed_scores"]}
    legacy = {**observed, **imputed}
    assert {(r.country_code, r.year): (r.score, r.unit) for r in everything.itertuples()} == {k: (r["score"], r["unit"]) for k, r in legacy.items()}
    assert {(r.country_code, r.year) for r in everything.itertuples() if r.imputed} == set(imputed)
    assert set(everything[~everything["imputed"]]["unit"]) == {unit} and set(everything[everything["imputed"]]["unit"]) == {"Tax Rate"}
    assert all(p == {} for p in everything["provenance"]) and all(len(i) == 1 for i in everything["inputs"])
    assert all(i[0]["imputation_method"] in ("Forward Extrapolation", "Backward Extrapolation", "Linear Interpolation") for i, flag in zip(everything["inputs"], everything["imputed"]) if flag)

    # dataset queries return canonical source observations only: a filled value is never stored as an observation
    assert dtypes(observations.drop(columns=["provenance"])) == DATASET_DTYPES and len(observations) == observation_count
    assert set(zip(observations["country_code"], observations["year"])) == set(observed)
    assert not any(p.get("imputed") for p in observations["provenance"]) and {p["source_organization"] for p in observations["provenance"]} == {"ILO"}
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == [(r[0], r[1], r[2]) for r in stored(db, indicator)]  # the rerun converged


def test_researcher_workflow_for_both_indicators(db):
    server = Server()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(["ILO_EMPLOY_TO_POP", "ILO_COLBAR"], client=server.client())
        sspi.run("EMPLOY")
        sspi.run("COLBAR")
        scores = sspi.query(indicators=["EMPLOY", "COLBAR"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        missing = sspi.query(indicators=["COLBAR"], countries=["IND", "SAU", "KWT"])
        kosovo = sspi.query(indicators=["EMPLOY"], countries=["KOS"])
    assert len(server.requests) == 2 and ingestion.observations_written == 2690 + 865  # two dataflows, two requests
    assert dtypes(scores) == INDICATOR_DTYPES and len(scores) == 2 * 3 * 14  # a full 2010-2023 series for each
    colbar = scores[scores["indicator_code"] == "COLBAR"]
    malaysia = {r.year: r for r in colbar.itertuples() if r.country_code == "MYS"}
    assert malaysia[2018].score == 0.004 and not malaysia[2018].imputed and malaysia[2018].unit == "%"
    assert malaysia[2023].score == 0.004 and malaysia[2023].imputed and malaysia[2023].unit == "Tax Rate"  # carried forward from 2018
    assert colbar[colbar["year"] > 2020]["imputed"].all()  # the source stops in 2020
    employ = scores[scores["indicator_code"] == "EMPLOY"]
    austria = {r.year: r for r in employ.itertuples() if r.country_code == "AUT"}
    assert austria[2023].score == (73.804 - 50) / 45 and not austria[2023].imputed and austria[2023].unit == "Percentage"
    assert missing.empty  # COLBAR-1: countries the ILO series does not cover have no score
    assert not kosovo.empty  # the ILO's own area code, kept as the legacy cleaner kept it
