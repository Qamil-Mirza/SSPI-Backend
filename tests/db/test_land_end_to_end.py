"""Land datasets and CHMPOL on the isolated database, with the UN SDG source
served from the committed fixtures by a mock transport. No network.

    sspi.ingest([...]) -> canonical observations -> sspi.run("CHMPOL") -> scores -> sspi.query(...)

WATMAN parity runs on the Singapore-blanked variant of the 6.4.1 fixture, the
data the legacy impute route was written against; on the fixture as committed
the legacy route raises and the new backend applies the canonical-first policy
(an intentional divergence, WATMAN-3).
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion import UNSDGClient

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {name: json.loads((FIXTURES / f"{name.replace('.', '_')}_sample.json").read_text())["data"] for name in ("12.4.1", "6.4.1", "6.4.2")}
GOLDEN = json.loads((Path(__file__).parents[1] / "golden" / "chmpol_cases.json").read_text())
CHMPOL_DATASETS = ["UNSDG_STKHLM", "UNSDG_MINMAT", "UNSDG_MONTRL", "UNSDG_BASELA", "UNSDG_ROTDAM"]


class FixtureServer:
    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        indicator = request.url.params["indicator"]
        self.requests.append(indicator)
        rows = PAYLOADS[indicator]
        return httpx.Response(200, json={"size": 500, "totalElements": len(rows), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": rows})


def client_for(server) -> UNSDGClient:
    return UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(server)), sleep=lambda s: None)


def stored_scores(db):
    with db.transaction() as session:
        return session.execute(text("SELECT indicator_code, country_code, year, score, imputed FROM indicator_score ORDER BY 1, 2, 3")).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


def test_chmpol_workflow(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(CHMPOL_DATASETS, client=client_for(server))
        assert sspi.query(indicators=["CHMPOL"]).empty
        run = sspi.run("CHMPOL")
        df = sspi.query(indicators=["CHMPOL"], countries=["MYS", "AUT"], years=(2018, 2023))
        everything = sspi.query(indicators=["CHMPOL"], include_inputs=True)
        rotdam = sspi.query(datasets=["UNSDG_ROTDAM"], countries=["AUT"], include_provenance=True)
        stkhlm = sspi.query(datasets=["UNSDG_STKHLM"], countries=["AUT"])
    assert server.requests == ["12.4.1"] and ingestion.source_fetches == ("12.4.1",)
    assert ingestion.counts == {"UNSDG_STKHLM": 15, "UNSDG_MINMAT": 10, "UNSDG_MONTRL": 21, "UNSDG_BASELA": 21, "UNSDG_ROTDAM": 15}
    assert run.written == 8 == len(run.observed_scores) and run.imputed_scores == () and len(run.unscored) == 13
    assert dtypes(df) == INDICATOR_DTYPES
    assert [(r.country_code, r.year, r.score) for r in df.itertuples()] == [("AUT", 2020, 0.6476257200000001)]  # MYS has no Stockholm/Minamata rows
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == [(s["country_code"], s["year"], s["score"]) for s in GOLDEN["scores"]]
    assert not everything["imputed"].any() and all(len(i) == 5 for i in everything["inputs"])
    # canonical pre-scoring observations, and the preserved legacy Rotterdam mapping (CHMPOL-1)
    assert dtypes(rotdam.drop(columns=["provenance"])) == DATASET_DTYPES
    assert list(rotdam["value"]) == list(stkhlm["value"]) and {p["source_series"] for p in rotdam["provenance"]} == {"SG_HAZ_CMRSTHOLM"}
    assert all(row.imputed is False for row in stored_scores(db))


def test_chmpol_rerun_converges_and_missing_datasets_leave_groups_unscored(db):
    with SSPI(database=db) as sspi:
        sspi.ingest(CHMPOL_DATASETS, client=client_for(FixtureServer()))
        first = sspi.run("CHMPOL")
        before = stored_scores(db)
        assert sspi.run("CHMPOL").written == first.written and stored_scores(db) == before
        with db.transaction() as session:
            session.execute(text("DELETE FROM observation WHERE dataset_code = 'UNSDG_MINMAT' AND country_code = 'AUT'"))
        again = sspi.run("CHMPOL")
        df = sspi.query(indicators=["CHMPOL"])
    assert again.written == first.written - 2 and "AUT" not in set(df["country_code"]) and again.imputed_scores == ()


def test_watman_datasets_are_ingestible_and_canonical(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        result = sspi.ingest(["UNSDG_WTSTRS", "UNSDG_WUSEFF", "UNSDG_CWUEFF"], client=client_for(server))
        wuseff = sspi.query(datasets=["UNSDG_WUSEFF"], countries=["MYS"], years=(2000, 2006))
        cwueff = sspi.query(datasets=["UNSDG_CWUEFF"], countries=["MYS"], years=(2000, 2006), include_provenance=True)
        wtstrs = sspi.query(datasets=["UNSDG_WTSTRS"], countries=["MYS", "AUT"], years=(2022, 2022))
    assert server.requests == ["6.4.2", "6.4.1"] and result.source_fetches == ("6.4.2", "6.4.1")  # 6.4.1 once for WUSEFF and CWUEFF
    assert result.counts == {"UNSDG_WTSTRS": 168, "UNSDG_WUSEFF": 150, "UNSDG_CWUEFF": 108}
    assert list(wuseff["year"]) == list(range(2000, 2007)) and set(wuseff["unit"]) == {"USD/m3"}
    assert list(cwueff["year"]) == [2006] and set(cwueff["unit"]) == {"Percent"}  # derived series starts in 2006
    values = list(wuseff[wuseff["year"] <= 2005]["value"])
    baseline = sum(values) / len(values)  # legacy arithmetic, not pandas' pairwise mean
    assert cwueff["value"].item() == ((wuseff[wuseff["year"] == 2006]["value"].item() - baseline) / baseline) * 100
    assert cwueff["provenance"].iloc[0]["derived_from"] == "UNSDG_WUSEFF"
    assert [(r.country_code, r.value) for r in wtstrs.itertuples()] == [("AUT", 8.68), ("MYS", 3.44)]  # the TOTAL activity slice only


def blank_sgp_2005(rows):
    out = []
    for row in rows:
        row = dict(row)
        if row["geoAreaCode"] == "702" and row.get("activity") == "TOTAL":
            row["years"] = json.dumps([{"year": e["year"], "value": ""} if e["year"] == "[2005]" else e for e in json.loads(row["years"])])
        out.append(row)
    return out


class SgpVariantServer(FixtureServer):
    def __call__(self, request):
        response = super().__call__(request)
        if request.url.params["indicator"] == "6.4.1":
            payload = response.json()
            payload["data"] = blank_sgp_2005(payload["data"])
            return httpx.Response(200, json=payload)
        return response


def test_watman_workflow(db):
    golden = json.loads((Path(__file__).parents[1] / "golden" / "watman_cases.json").read_text())
    variant = next(v for v in golden["variants"] if v["name"] == "sgp_without_2005")
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(["UNSDG_CWUEFF", "UNSDG_WTSTRS", "UNSDG_WUSEFF"], client=client_for(SgpVariantServer()))
        run = sspi.run("WATMAN")
        df = sspi.query(indicators=["WATMAN"], countries=["MYS", "AUT"], years=(2018, 2023))
        everything = sspi.query(indicators=["WATMAN"], include_inputs=True, include_provenance=True)
        che = sspi.query(indicators=["WATMAN"], countries=["CHE"], include_inputs=True)
        cwueff = sspi.query(datasets=["UNSDG_CWUEFF"], countries=["CHE", "SGP"])
    assert ingestion.counts["UNSDG_CWUEFF"] == 90 and run.written == 90 + 78 and len(run.observed_scores) == 90 and len(run.imputed_scores) == 78
    assert run.unscored == ()
    assert len(df) == 12 and not df["imputed"].any()
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == sorted(
        [(s["country_code"], s["year"], s["score"]) for s in variant["scores"] + variant["imputed_scores"]]
    )
    assert all(p == {} for p in everything["provenance"])  # WATMAN imputes inputs, not scores
    assert everything["imputed"].sum() == 78
    assert cwueff.empty  # CHE and SGP have no canonical CWUEFF; their scores come from the imputation strategy only
    assert len(che) == 24 and che["imputed"].all()
    assert {i["imputation_method"] for inputs in che["inputs"] for i in inputs if i["dataset_code"] == "UNSDG_CWUEFF"} == {"Synthetic CWUEFF from WUSEFF extrapolation"}
    assert all(row.imputed == (row.country_code in {"CHE", "SGP"} or row.year < 2006) for row in stored_scores(db))


def test_watman_on_current_source_data_applies_the_canonical_first_policy(db):
    """Intentional divergence (WATMAN-3): the legacy route cannot run on this data; the new backend keeps SGP's canonical series."""
    with SSPI(database=db) as sspi:
        sspi.ingest(["UNSDG_CWUEFF", "UNSDG_WTSTRS", "UNSDG_WUSEFF"], client=client_for(FixtureServer()))
        run = sspi.run("WATMAN")
        sgp = sspi.query(indicators=["WATMAN"], countries=["SGP"], include_inputs=True)
        canonical = sspi.query(datasets=["UNSDG_CWUEFF"], countries=["SGP"])
    assert run.written == 108 + 60 and len(run.observed_scores) == 108 and len(run.imputed_scores) == 60 and run.unscored == ()
    assert list(canonical["year"]) == list(range(2006, 2024))
    assert len(sgp) == 24 and list(sgp[sgp["imputed"]]["year"]) == list(range(2000, 2006))
    assert {i["imputation_method"] for inputs in sgp["inputs"] for i in inputs if i["dataset_code"] == "UNSDG_CWUEFF"} == {None, "Backward Extrapolation"}
    assert len(stored_scores(db)) == len({(r.country_code, r.year) for r in stored_scores(db)})
