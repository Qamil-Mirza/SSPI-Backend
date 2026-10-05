"""NITROG, DEFRST and CARBON on the isolated database, with the EPI archive and
the FAOSTAT bulk file served from the committed fixtures by mock transports.
No network.

    sspi.ingest("EPI_NITROG") -> sspi.run("NITROG") -> sspi.query(...)
    sspi.ingest(["UNFAO_FRSTLV", "UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_CRBNAV"]) -> sspi.run("DEFRST"), sspi.run("CARBON")

DEFRST and CARBON parity runs on the fixture variants without the recipient
that now has source rows (ARE for DEFRST, KWT for CARBON); on the fixture as
committed the legacy routes store conflicting rows and the new backend
raises and selects no result (pending methodology decisions, DEFRST-1 and
CARBON-1; no precedence rule exists).
"""

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import EPIClient, FAOBulkClient
from sspi.ingestion.epi import ARCHIVES
from sspi.ingestion.fao import BULK_BASE_URL, DOMAIN_ARTIFACTS

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
EPI_CSV = (FIXTURES / "epi" / "epi2024indicators_P5_Indicator_SNM_ind_na.csv").read_text(encoding="utf-8")
FAO_CSV = (FIXTURES / "fao" / "Inputs_LandUse_E_All_Data_(Normalized)_sample.csv").read_text(encoding="utf-8")
FAO_DATASETS = ["UNFAO_FRSTLV", "UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_CRBNAV"]


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text_ in files.items():
            z.writestr(name, text_)
    return buffer.getvalue()


class Servers:
    """One mock transport per source, serving the committed fixtures; optionally without one FAO area."""

    def __init__(self, drop_area=None):
        self.requests = []
        rows = FAO_CSV.splitlines(keepends=True)
        if drop_area is not None:
            rows = [rows[0]] + [r for r in rows[1:] if f'"{drop_area}"' not in r]
        self.fao_zip = zipped({"Inputs_LandUse_E_All_Data_(Normalized).csv": "".join(rows)})
        self.epi_zip = zipped({"P5_Indicator/SNM_ind_na.csv": EPI_CSV, "__MACOSX/P5_Indicator/._SNM_ind_na.csv": "x"})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if url == BULK_BASE_URL + DOMAIN_ARTIFACTS["RL"]:
            return httpx.Response(200, content=self.fao_zip)
        if url == ARCHIVES["epi2026_indicators_na_2026-08-31"]:
            return httpx.Response(200, content=self.epi_zip)  # the 2024 file served under the current archive name: a fixture, not the live edition
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"EPI": EPIClient(http=http), "UNFAO": FAOBulkClient(http=http)}


def stored_scores(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


def test_nitrog_workflow(db):
    golden = json.loads((GOLDEN / "nitrog_cases.json").read_text())
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest("EPI_NITROG", client=servers.clients())
        assert sspi.query(indicators=["NITROG"]).empty
        run = sspi.run("NITROG")
        df = sspi.query(indicators=["NITROG"], countries=["MYS", "AUT", "USA"], years=(2018, 2023))
        everything = sspi.query(indicators=["NITROG"], include_inputs=True, include_provenance=True)
        source = sspi.query(datasets=["EPI_NITROG"], countries=["MYS"], years=(2020, 2020), include_provenance=True)
    assert servers.requests == [ARCHIVES["epi2026_indicators_na_2026-08-31"]] and ingestion.source_fetches == ("epi2026_indicators_na_2026-08-31",)
    assert ingestion.counts == {"EPI_NITROG": 5820} and ingestion.per_dataset[0].missing_values == 780 and ingestion.per_dataset[0].skipped_areas == ()
    assert run.written == 5820 == len(run.observed_scores) and run.imputed_scores == () and run.unscored == ()
    assert dtypes(df) == INDICATOR_DTYPES and len(df) == 18 and not df["imputed"].any()
    assert [(r.country_code, r.year, r.score) for r in df.itertuples() if r.year == 2020] == [("AUT", 2020, 63.9 / 100), ("MYS", 2020, 62.5 / 100), ("USA", 2020, 77.1 / 100)]  # goalpost(x, 0, 100) = x / 100 in float arithmetic
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == [(s["country_code"], s["year"], s["score"]) for s in golden["scores"]]
    assert all(p == {} for p in everything["provenance"]) and all(len(i) == 1 for i in everything["inputs"])
    assert source["value"].item() == 62.5 and source["provenance"].iloc[0]["source_series"] == "SNM" and source["provenance"].iloc[0]["source_column"] == "SNM.ind.2020"
    assert all(row.imputed is False for row in stored_scores(db, "NITROG"))


def test_fao_datasets_share_one_download_and_derived_datasets_are_canonical(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(FAO_DATASETS, client=servers.clients())
        frstlv = sspi.query(datasets=["UNFAO_FRSTLV"], countries=["AUT"], years=(1990, 2000))
        frstav = sspi.query(datasets=["UNFAO_FRSTAV"], countries=["AUT"], include_provenance=True)
        crbnav = sspi.query(datasets=["UNFAO_CRBNAV"], countries=["AUT"])
        china = sspi.query(datasets=["UNFAO_FRSTLV"], countries=["CHN"], years=(2020, 2020), include_provenance=True)
    assert servers.requests == [BULK_BASE_URL + DOMAIN_ARTIFACTS["RL"]] and ingestion.source_fetches == ("RL",)
    assert ingestion.counts == {"UNFAO_FRSTLV": 373, "UNFAO_FRSTAV": 297, "UNFAO_CRBNLV": 481, "UNFAO_CRBNAV": 432}
    assert {tuple(a) for a in ingestion.per_dataset[0].skipped_areas} == {("5000", "World"), ("5400", "Europe"), ("351", "China"), ("15", "Belgium-Luxembourg")}
    assert set(frstlv["unit"]) == {"1000 ha"} and set(frstav["unit"]) == {"hectares (1990s Average)"}  # legacy derived label, kept (PROVENANCE)
    assert list(frstav["year"]) == list(range(1990, 2023)) and list(crbnav["year"]) == list(range(1990, 2026))  # DEFRST-2 asymmetry
    nineties = list(frstlv[frstlv["year"] < 2000]["value"])
    assert set(frstav["value"]) == {sum(nineties) / len(nineties)} and frstav["provenance"].iloc[0]["derivation"] == "mean_1990_1999_repeated_1990_2022"
    assert china["provenance"].iloc[0]["source_area_name"] == "China, mainland" and china["provenance"].iloc[0]["source_m49_code"] == "156"


def test_defrst_workflow(db):
    golden = json.loads((GOLDEN / "defrst_cases.json").read_text())
    variant = next(v for v in golden["variants"] if v["name"] == "without_are_source_rows")
    with SSPI(database=db) as sspi:
        sspi.ingest(["UNFAO_FRSTLV", "UNFAO_FRSTAV"], client=Servers(drop_area="United Arab Emirates").clients())
        run = sspi.run("DEFRST")
        df = sspi.query(indicators=["DEFRST"], countries=["MYS", "AUT", "USA"], years=(2018, 2023))
        everything = sspi.query(indicators=["DEFRST"], include_inputs=True, include_provenance=True)
        bel = sspi.query(indicators=["DEFRST"], countries=["BEL"], include_inputs=True, include_provenance=True)
    assert run.written == 184 + 80 and len(run.observed_scores) == 184 and len(run.imputed_scores) == 80
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == sorted(
        [(s["country_code"], s["year"], s["score"]) for s in variant["scores"] + variant["imputed_scores"]]
    )
    assert len(df) == 18 and list(df[df["imputed"]]["year"].unique()) == [2023]  # 2023 is always an extrapolation of 2022 (DEFRST-2)
    aut = {r.year: r for r in df[df["country_code"] == "AUT"].itertuples()}
    assert aut[2023].score == aut[2022].score
    provenance = {(r.country_code, r.year): r.provenance for r in everything.itertuples()}
    assert provenance[("AUT", 2023)] == {"imputed": True, "imputation_method": "Forward Extrapolation", "imputation_distance": 1, "source_year": 2022}
    assert provenance[("AUT", 2022)] == {}
    assert len(bel) == 24 and bel["imputed"].all() and all(i == () for i in bel["inputs"])  # reference-class scores have no inputs
    assert {p["imputation_method"] for p in bel["provenance"]} == {"ImputeReferenceClassAverage"} and {p["reference_score_count"] for p in bel["provenance"]} == {184}
    rows = stored_scores(db, "DEFRST")
    assert all(row.imputed == bool(row.provenance.get("imputed")) for row in rows)  # score-level imputation only; inputs are never imputed here
    assert len(rows) == len({(r.country_code, r.year) for r in rows})


def test_carbon_workflow(db):
    golden = json.loads((GOLDEN / "carbon_cases.json").read_text())
    variant = next(v for v in golden["variants"] if v["name"] == "without_kwt_source_rows")
    with SSPI(database=db) as sspi:
        sspi.ingest(["UNFAO_CRBNLV", "UNFAO_CRBNAV"], client=Servers(drop_area="Kuwait").clients())
        run = sspi.run("CARBON")
        df = sspi.query(indicators=["CARBON"], countries=["MYS", "AUT", "USA"], years=(2018, 2023))
        everything = sspi.query(indicators=["CARBON"], include_inputs=True, include_provenance=True)
        lux = sspi.query(indicators=["CARBON"], countries=["LUX"], include_inputs=True)
    assert run.written == 283 + 72 and len(run.observed_scores) == 283 and len(run.imputed_scores) == 72
    assert [(r.country_code, r.year, r.score) for r in everything.itertuples()] == sorted(
        [(s["country_code"], s["year"], s["score"]) for s in variant["scores"] + variant["imputed_scores"]]
    )
    assert len(df) == 18 and not df["imputed"].any()  # the carbon average follows the source: observed scores through 2023 and beyond
    assert all(p == {} for p in everything["provenance"])  # CARBON imputes inputs, not scores
    assert len(lux) == 24 and lux["imputed"].all()
    assert {i["imputation_method"] for inputs in lux["inputs"] for i in inputs} == {"ImputeReferenceClassAverage"} and all(len(i) == 2 for i in lux["inputs"])
    assert all(row.imputed == (row.country_code in {"KWT", "BEL", "LUX"}) for row in stored_scores(db, "CARBON"))


@pytest.mark.parametrize("indicator, datasets, recipient, conflict", [("DEFRST", ["UNFAO_FRSTLV", "UNFAO_FRSTAV"], "ARE", "DEFRST-1"), ("CARBON", ["UNFAO_CRBNLV", "UNFAO_CRBNAV"], "KWT", "CARBON-1")])
def test_current_source_data_is_refused_until_a_precedence_is_decided(db, indicator, datasets, recipient, conflict):
    """Pending methodology decision: a hard-coded recipient now has observed scores; the legacy route would store two scores per
    identity; the new backend selects no result and persists nothing, not even a previous result's replacement."""
    with SSPI(database=db) as sspi:
        sspi.ingest(datasets, client=Servers().clients())
        with pytest.raises(ImputationError, match=f"{recipient}.*{conflict}") as info:
            sspi.run(indicator)
        assert "source data has changed" in str(info.value) and "Methodology review is required" in str(info.value)
        assert sspi.query(indicators=[indicator]).empty  # nothing partial is persisted
        assert not sspi.query(datasets=datasets).empty  # the ingested observations are intact
    with db.transaction() as session:
        assert session.execute(text("SELECT count(*) FROM indicator_score WHERE indicator_code = :i"), {"i": indicator}).scalar() == 0


def test_the_whole_land_category_queries_together(db):
    """The five Land indicators that run on fixtures share one query; nothing is aggregated."""
    with SSPI(database=db) as sspi:
        sspi.ingest("EPI_NITROG", client=Servers().clients())
        sspi.ingest(FAO_DATASETS, client=Servers(drop_area="United Arab Emirates").clients())
        with db.transaction() as session:  # KWT's carbon rows are the CARBON-1 case; remove them for this combined check
            session.execute(text("DELETE FROM observation WHERE dataset_code IN ('UNFAO_CRBNLV', 'UNFAO_CRBNAV') AND country_code = 'KWT'"))
        for code in ("NITROG", "DEFRST", "CARBON"):
            sspi.run(code)
        land = sspi.query(indicators=["NITROG", "DEFRST", "CARBON"], countries=["MYS", "AUT", "USA"], years=(2018, 2023))
    assert dtypes(land) == INDICATOR_DTYPES and len(land) == 54
    assert set(land["indicator_code"]) == {"NITROG", "DEFRST", "CARBON"} and land.groupby("indicator_code").size().to_dict() == {"CARBON": 18, "DEFRST": 18, "NITROG": 18}
    assert land[land["imputed"]].groupby("indicator_code").size().to_dict() == {"DEFRST": 3}
