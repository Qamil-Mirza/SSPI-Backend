"""ISHRAT and GINIPT on the isolated database, with the WID bulk archive and the
World Bank API served from the committed fixtures by a mock transport. No
network.

    sspi.ingest([two WID datasets]) -> sspi.run("ISHRAT")
    sspi.ingest("WB_GINIPT")        -> sspi.run("GINIPT")   (needs ISHRAT scores)
    sspi.query(...)

Stored scores are compared with the legacy golden files exactly.
"""

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.db import Repository
from sspi.errors import ScoreDependencyError
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion import WIDClient, WorldBankClient
from sspi.ingestion.wid import ARCHIVES
from sspi.ingestion.worldbank import BASE_URL

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
WID_DATASETS = ["WID_NINCSH_PRETAX_P90P100", "WID_NINCSH_PRETAX_P0P50"]
ISHRAT_GOLDEN = json.loads((GOLDEN / "ishrat_cases.json").read_text())
GINIPT_GOLDEN = json.loads((GOLDEN / "ginipt_cases.json").read_text())


def _wid_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted((FIXTURES / "wid").glob("WID_*.csv")):
            z.writestr(path.name, path.read_text(encoding="utf-8"))
        z.writestr("README.md", "not a country file")
    return buffer.getvalue()


WID_ZIP = _wid_zip()
WB_PAYLOAD = (FIXTURES / "wb" / "SI.POV.GINI_sample.json").read_bytes()


class Servers:
    """One mock transport serving both sources from the committed fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url).split("?")[0])
        if str(request.url) == ARCHIVES["wid_all_data"]:
            return httpx.Response(200, content=WID_ZIP)
        if str(request.url).startswith(BASE_URL + "SI.POV.GINI?"):
            return httpx.Response(200, content=WB_PAYLOAD, headers={"content-type": "application/json"})
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"WID": WIDClient(http=http), "WB": WorldBankClient(http=http)}


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


def ingest_and_run_ishrat(sspi, servers):
    clients = servers.clients()
    ingestion = sspi.ingest(WID_DATASETS, client=clients)
    clients["WID"].close()
    return ingestion, sspi.run("ISHRAT")


def test_ishrat_workflow(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        clients = servers.clients()
        ingestion = sspi.ingest(WID_DATASETS, client=clients)
        clients["WID"].close()
        assert sspi.query(indicators=["ISHRAT"]).empty  # ingest() never runs an indicator
        run = sspi.run("ISHRAT")
        df = sspi.query(indicators=["ISHRAT"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=["ISHRAT"], include_inputs=True, include_provenance=True)
        shares = sspi.query(datasets=WID_DATASETS, countries=["MYS"], years=(2024, 2024), include_provenance=True)
        all_shares = sspi.query(datasets=WID_DATASETS)
    assert servers.requests == [ARCHIVES["wid_all_data"]] and ingestion.source_fetches == ("wid_all_data",)  # two datasets, one archive download; run() fetched nothing
    assert ingestion.counts == {"WID_NINCSH_PRETAX_P90P100": 1650, "WID_NINCSH_PRETAX_P0P50": 1650}
    assert run.written == 1650 == len(run.observed_scores) and run.imputed_scores == () and run.unscored == ()
    assert dtypes(df) == INDICATOR_DTYPES and len(df) == 3 * 14 and not df["imputed"].any()
    assert set(df["unit"]) == {"Ratio of Bottom 50% Income Share to to Top 10% Income Share"}
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == [(s["country_code"], s["year"], s["score"]) for s in ISHRAT_GOLDEN["scores"]]
    assert all(p == {} for p in everything["provenance"]) and all(len(i) == 2 for i in everything["inputs"])
    # dataset queries return the canonical values: the legacy float32 representation, published text in provenance
    assert dtypes(all_shares) == DATASET_DTYPES and len(all_shares) == 3300
    by_dataset = {r.dataset_code: r for r in shares.itertuples()}
    assert by_dataset["WID_NINCSH_PRETAX_P0P50"].value == 0.1921000034 and by_dataset["WID_NINCSH_PRETAX_P0P50"].provenance["source_value"] == "0.1921"
    assert by_dataset["WID_NINCSH_PRETAX_P90P100"].value == 0.3652999997 and by_dataset["WID_NINCSH_PRETAX_P90P100"].provenance["source_percentile"] == "p90p100"
    assert all(row.imputed is False and row.provenance == {} for row in stored(db, "ISHRAT"))


def test_ginipt_refuses_without_ishrat_scores_and_writes_nothing(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        sspi.ingest("WB_GINIPT", client=servers.clients())
        with pytest.raises(ScoreDependencyError, match=r"GINIPT requires existing ISHRAT scores for its legacy imputation procedure and none were found\. Run ISHRAT first") as info:
            sspi.run("GINIPT")
        assert "Nothing was computed or written for GINIPT" in str(info.value)
        assert sspi.query(indicators=["GINIPT"]).empty and sspi.query(indicators=["ISHRAT"]).empty  # nothing partial, and ISHRAT was not run on the caller's behalf
        assert len(sspi.query(datasets=["WB_GINIPT"])) == 1727  # observations intact
    assert stored(db, "GINIPT") == [] and stored(db, "ISHRAT") == []


def test_ginipt_workflow(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        _, ishrat_run = ingest_and_run_ishrat(sspi, servers)  # ISHRAT runs on its own, before any Gini data exists
        ingestion = sspi.ingest("WB_GINIPT", client=servers.clients())
        assert sspi.query(indicators=["GINIPT"]).empty
        requests_before_run = list(servers.requests)
        run = sspi.run("GINIPT")
        assert servers.requests == requests_before_run  # run() never ingests
        scores = sspi.query(indicators=["GINIPT", "ISHRAT"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=["GINIPT"], include_inputs=True, include_provenance=True)
        gini = sspi.query(datasets=["WB_GINIPT"], include_provenance=True)
        recipients = sspi.query(indicators=["GINIPT"], countries=["KWT", "NZL", "SAU", "SGP"])
    assert ishrat_run.written == 1650
    assert ingestion.counts == {"WB_GINIPT": 1727} and ingestion.source_fetches == ("SI.POV.GINI",)
    assert ingestion.per_dataset[0].missing_values == 184 and [a[0] for a in ingestion.per_dataset[0].skipped_areas] == ["AFE", "WLD", "XD", "XKX"]
    assert len(run.observed_scores) == 1727 and len(run.imputed_scores) == 1371 + 100 and run.written == 3198 and run.unscored == ()

    # the researcher-facing frame
    assert dtypes(scores) == INDICATOR_DTYPES and len(scores) == 2 * 3 * 14
    ginipt = scores[scores["indicator_code"] == "GINIPT"]
    assert set(ginipt["unit"]) == {"Coefficient"} and len(ginipt) == 42  # observed or series-filled for every year 2010-2023
    malaysia = {r.year: r.imputed for r in ginipt.itertuples() if r.country_code == "MYS"}
    assert malaysia[2011] is False and malaysia[2012] is True and malaysia[2023] is True  # 2011 observed; 2012 interpolated; 2023 carried forward from 2021

    # exact legacy parity of everything stored
    legacy = {(r["country_code"], r["year"]): r["score"] for key in ("observed_scores", "series_fill_scores") for r in GINIPT_GOLDEN[key]}
    legacy.update({(r["country_code"], r["year"]): r["score"] for r in GINIPT_GOLDEN["regression"]["predicted_scores"]})
    assert {(r.country_code, r.year): r.score for r in everything.itertuples()} == legacy and len(everything) == len(legacy) == 3198
    observed_ids = {(r["country_code"], r["year"]) for r in GINIPT_GOLDEN["observed_scores"]}
    assert {(r.country_code, r.year) for r in everything.itertuples() if not r.imputed} == observed_ids

    # the two imputation stages are distinguishable from what is stored
    assert len(recipients) == 100 and recipients["imputed"].all() and set(recipients["year"]) == set(range(2000, 2025))
    rows = {(r.country_code, r.year): r for r in everything.itertuples()}
    predicted = rows[("SGP", 2024)]
    assert len(predicted.inputs) == 0 and predicted.provenance["imputation_method"] == "RegressionImputation" and predicted.provenance["feature_indicator"] == "ISHRAT"
    assert predicted.provenance["coefficient"] == GINIPT_GOLDEN["regression"]["coefficient"] and predicted.provenance["training_score_count"] == 1077
    filled = rows[("MYS", 2012)]
    assert filled.provenance == {} and len(filled.inputs) == 1 and filled.inputs[0]["imputation_method"] == "Linear Interpolation"

    # dataset queries return canonical source observations only: no filled or predicted row is ever stored as an observation
    assert len(gini) == 1727 and not any(p.get("imputed") for p in gini["provenance"])
    assert set(gini["country_code"]).isdisjoint({"KWT", "NZL", "SAU", "SGP"})
    assert ("MYS", 2012) not in set(zip(gini["country_code"], gini["year"]))


def test_reruns_converge_and_a_failed_rerun_leaves_the_previous_result_untouched(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingest_and_run_ishrat(sspi, servers)
        sspi.ingest("WB_GINIPT", client=servers.clients())
        first = sspi.run("GINIPT")
        before = stored(db, "GINIPT")
        again = sspi.run("GINIPT")
        assert again.written == first.written == 3198 and stored(db, "GINIPT") == before
        assert sspi.run("ISHRAT").written == 1650 and stored(db, "GINIPT") == before  # rerunning the dependency does not touch the dependent

        with db.transaction() as session:
            assert Repository(session).delete_indicator_scores("ISHRAT") == 1650
        with pytest.raises(ScoreDependencyError, match="Run ISHRAT first"):
            sspi.run("GINIPT")
        assert stored(db, "GINIPT") == before  # no partial replacement: the earlier complete result is still there

        sspi.run("ISHRAT")
        assert sspi.run("GINIPT").written == 3198 and stored(db, "GINIPT") == before


def test_other_indicators_are_unaffected_by_the_dependency_mechanism(db):
    """An indicator with no score dependencies reads no scores and runs exactly as before, whatever else is stored."""
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingest_and_run_ishrat(sspi, servers)
        before = stored(db, "ISHRAT")
        sspi.ingest("WB_GINIPT", client=servers.clients())
        sspi.run("GINIPT")
        assert sspi.run("ISHRAT").written == 1650 and stored(db, "ISHRAT") == before
        assert sspi.executable_indicators() == ("BIODIV", "REDLST", "CHMPOL", "WATMAN", "NITROG", "DEFRST", "CARBON", "ISHRAT", "GINIPT", "EMPLOY", "COLBAR", "ALTNRG", "NRGINT", "AIRPOL", "BEEFMK", "COALPW", "GTRANS", "MSWGEN", "PUPTCH", "ENRPRI", "ENRSEC", "YRSEDU")
