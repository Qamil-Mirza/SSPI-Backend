"""The three Greenhouse Gases indicators on the isolated database, with the
FAOSTAT, World Bank and IEA sources served from the committed fixtures by a
mock transport. No network.

    sspi.ingest([the eleven Greenhouse Gases datasets])
    sspi.run("BEEFMK"), sspi.run("COALPW"), sspi.run("GTRANS")
    sspi.query(indicators=[...], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_ghg.py). Stored scores are compared with
the legacy golden files exactly. No Greenhouse Gases category score exists.
"""

import io
import json
import zipfile
from pathlib import Path

import httpx
from sqlalchemy import text

from sspi import SSPI
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import FAOBulkClient, IEAClient, WorldBankClient
from sspi.ingestion.fao import BULK_BASE_URL, DOMAIN_ARTIFACTS
from sspi.ingestion.iea import BASE_URL as IEA_URL
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_ghg import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
TES_DATASETS = ["IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL"]
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["BEEFMK", "COALPW", "GTRANS"]
LEGACY = {code: json.loads((GOLDEN / f"{code.lower()}_cases.json").read_text()) for code in INDICATORS}


def _fbs_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("FoodBalanceSheets_E_All_Data_(Normalized).csv", (FIXTURES / "fao" / "FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv").read_text(encoding="utf-8"))
        z.writestr("FoodBalanceSheets_E_Flags.csv", "Flag,Description\n")
    return buffer.getvalue()


FBS_ZIP = _fbs_zip()
IEA_PAYLOADS = {name: (FIXTURES / "iea" / f"{name}_sample.json").read_bytes() for name in ("TESbySource", "CO2BySector")}
WB_PAYLOAD = (FIXTURES / "wb" / "SP.POP.TOTL_sample.json").read_bytes()


class Servers:
    """One mock transport serving the three sources from the committed fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0])
        if url == BULK_BASE_URL + DOMAIN_ARTIFACTS["FBS"]:
            return httpx.Response(200, content=FBS_ZIP)
        if url.startswith(WB_URL + "SP.POP.TOTL?"):
            return httpx.Response(200, content=WB_PAYLOAD, headers={"content-type": "application/json"})
        if url.startswith(IEA_URL) and url.removeprefix(IEA_URL) in IEA_PAYLOADS:
            return httpx.Response(200, content=IEA_PAYLOADS[url.removeprefix(IEA_URL)], headers={"content-type": "application/json"})
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"UNFAO": FAOBulkClient(http=http), "WB": WorldBankClient(http=http), "IEA": IEAClient(http=http)}


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def legacy_scores(code):
    """(score, stored by the impute route) by identity."""
    return {(r["country_code"], r["year"]): (r["score"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in LEGACY[code][key]}


def counts(db):
    with db.transaction() as session:
        return session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one()


def test_greenhouse_gases_workflow_from_an_empty_database(db):
    assert tuple(counts(db)) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == ["UNFAO_BFPROD", "UNFAO_BFCONS", "WB_POPULN", *TES_DATASETS, "IEA_TCO2EM"] and tuple(DATASETS) == required_datasets()
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(DATASETS, client=servers.clients())
        assert ingestion.datasets == tuple(DATASETS)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        ghg = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = {code: sspi.query(indicators=[code], include_inputs=True, include_provenance=True) for code in INDICATORS}
        transport = sspi.query(datasets=["IEA_TCO2EM"], countries=["USA"], years=(2023, 2023), include_provenance=True)

    # one fetch per source artifact: FBS serves both beef datasets, TESbySource the seven COALPW datasets
    assert ingestion.source_fetches == ("FBS", "SP.POP.TOTL", "TESbySource", "CO2BySector")
    assert servers.requests == [BULK_BASE_URL + DOMAIN_ARTIFACTS["FBS"], WB_URL + "SP.POP.TOTL", IEA_URL + "TESbySource", IEA_URL + "CO2BySector"]
    assert ingestion.counts == {
        "UNFAO_BFPROD": 128, "UNFAO_BFCONS": 128, "WB_POPULN": 828,
        "IEA_TLCOAL": 258, "IEA_NATGAS": 282, "IEA_NCLEAR": 126, "IEA_HYDROP": 249, "IEA_GEOPWR": 201, "IEA_BIOWAS": 284, "IEA_FSLOIL": 284,
        "IEA_TCO2EM": 305,
    }

    expected = {"BEEFMK": (114, 126), "COALPW": (91, 1518), "GTRANS": (270, 4)}
    for code, run in runs.items():
        assert (len(run.observed_scores), len(run.imputed_scores), run.written) == (*expected[code], sum(expected[code]))
        frame = everything[code]
        assert {(r.country_code, r.year): (r.score, r.imputed) for r in frame.itertuples()} == legacy_scores(code) and len(frame) == sum(expected[code])

    # the researcher-facing frame: three leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in ghg.dtypes.items()} == INDICATOR_DTYPES and sorted(set(ghg["indicator_code"])) == INDICATORS
    assert len(ghg) == 3 * 3 * 14 and set(ghg["unit"]) == {"Index"}
    imputed = {(r.indicator_code, r.country_code) for r in ghg.itertuples() if r.imputed}
    assert imputed == {("COALPW", "MYS"), ("COALPW", "AUT")}  # no nuclear row: every COALPW score rests on a zero-filled input (COALPW-1, ALTNRG-2)

    # what is stored with a score
    beef = {(r.country_code, r.year): r for r in everything["BEEFMK"].itertuples()}
    singapore = beef[("SGP", 2005)]
    assert singapore.imputed and singapore.inputs == () and singapore.provenance["imputation_method"] == "ImputeReferenceClassAverage" and singapore.provenance["reference_score_count"] == 114
    carried = beef[("USA", 2005)]
    assert carried.provenance == {"imputed": True, "imputation_method": "Backward Extrapolation", "imputation_distance": 5, "source_year": 2010} and carried.score == beef[("USA", 2010)].score
    car = {(r.country_code, r.year): r for r in everything["GTRANS"].itertuples()}[("PAK", 2023)]
    carbon = next(i for i in car.inputs if i["dataset_code"] == "IEA_TCO2EM")
    pakistan_2019 = {(r.country_code, r.year): r for r in everything["GTRANS"].itertuples()}[("PAK", 2019)]
    assert car.imputed and (carbon["imputed"], carbon["imputation_method"]) == (True, "Forward Extrapolation")
    assert carbon["value"] == next(i for i in pakistan_2019.inputs if i["dataset_code"] == "IEA_TCO2EM")["value"] and not pakistan_2019.imputed
    (usa,) = transport.itertuples()
    assert usa.unit == "Tonnes C02 per inhabitant" and usa.provenance["source_unit"] == "MtCO2" and usa.value == usa.provenance["source_value"] * 10**9


def test_reruns_converge_and_each_indicator_stands_alone(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        sspi.ingest(["IEA_TCO2EM", "WB_POPULN"], client=servers.clients())
        assert sspi.run("BEEFMK").written == 0  # no beef rows: nothing scored, and Singapore gets no mean of nothing
        first = sspi.run("GTRANS")
        before = stored(db, "GTRANS")
        assert sspi.run("GTRANS").written == first.written == 274 and stored(db, "GTRANS") == before
        sspi.ingest(DATASETS, client=servers.clients())  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and snapshot["GTRANS"] == before
