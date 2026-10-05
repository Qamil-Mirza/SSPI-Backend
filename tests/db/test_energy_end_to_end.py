"""The three Energy indicators on the isolated database, with the UN SDG and
IEA sources served from the committed fixtures by a mock transport. No
network.

    sspi.ingest([seven IEA datasets, "UNSDG_NRGINT", "UNSDG_AIRPOL"])
    sspi.run("ALTNRG"), sspi.run("NRGINT"), sspi.run("AIRPOL")
    sspi.query(...)

Stored scores are compared with the legacy golden files exactly.
"""

import json
from pathlib import Path

import httpx
from sqlalchemy import text

from sspi import SSPI
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion import IEAClient, UNSDGClient
from sspi.ingestion.iea import BASE_URL as IEA_URL

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
GOLDEN = Path(__file__).parents[1] / "golden"
PAYLOADS = {name: json.loads((FIXTURES / f"{name.replace('.', '_')}_sample.json").read_text())["data"] for name in ("7.3.1", "11.6.2")}
DATASETS = ["UNSDG_NRGINT", "UNSDG_AIRPOL"]
IEA_DATASETS = ["IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL"]
IEA_PAYLOAD = (FIXTURES.parent / "iea" / "TESbySource_sample.json").read_bytes()
LEGACY = {code: json.loads((GOLDEN / f"{code.lower()}_cases.json").read_text()) for code in ("ALTNRG", "NRGINT", "AIRPOL")}


class FixtureServer:
    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(IEA_URL):
            self.requests.append(str(request.url))
            return httpx.Response(200, content=IEA_PAYLOAD, headers={"content-type": "application/json"})
        indicator = request.url.params["indicator"]
        self.requests.append(indicator)
        rows = PAYLOADS[indicator]
        return httpx.Response(200, json={"size": 500, "totalElements": len(rows), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": rows})


def client_for(server) -> UNSDGClient:
    return UNSDGClient(http=httpx.Client(transport=httpx.MockTransport(server)), sleep=lambda s: None)


def clients_for(server) -> dict:
    http = httpx.Client(transport=httpx.MockTransport(server))
    return {"IEA": IEAClient(http=http), "UNSDG": UNSDGClient(http=http, sleep=lambda s: None)}


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


def legacy_scores(code):
    """(score, stored by the impute route) by identity."""
    return {(r["country_code"], r["year"]): (r["score"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in LEGACY[code][key]}


def test_energy_workflow(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(DATASETS, client=client_for(server))
        assert sspi.query(indicators=["NRGINT", "AIRPOL"]).empty  # ingest() never runs an indicator
        requests_before_run = list(server.requests)
        intensity, pollution = sspi.run("NRGINT"), sspi.run("AIRPOL")
        assert server.requests == requests_before_run  # run() never ingests
        energy = sspi.query(indicators=["ALTNRG", "NRGINT", "AIRPOL"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))  # ALTNRG has not been run here
        everything = {code: sspi.query(indicators=[code], include_inputs=True, include_provenance=True) for code in ("NRGINT", "AIRPOL")}
        observations = sspi.query(datasets=DATASETS, include_provenance=True)
        malaysia = sspi.query(datasets=["UNSDG_AIRPOL"], countries=["MYS"], years=(2000, 2010))
    assert server.requests == ["7.3.1", "11.6.2"] and ingestion.source_fetches == ("7.3.1", "11.6.2")
    assert ingestion.counts == {"UNSDG_NRGINT": 598, "UNSDG_AIRPOL": 196}
    assert [d.missing_values for d in ingestion.per_dataset] == [618, 700] and all([code for code, _ in d.skipped_areas] == ["2", "150", "1"] for d in ingestion.per_dataset)
    assert (len(intensity.observed_scores), len(intensity.imputed_scores), intensity.written, intensity.unscored) == (598, 1, 599, ())
    assert (len(pollution.observed_scores), len(pollution.imputed_scores), pollution.written, pollution.unscored) == (196, 1412, 1608, ())

    # the researcher-facing frame: two indicators, three countries, 2010-2023; an indicator that has not been run has no rows
    assert dtypes(energy) == INDICATOR_DTYPES and sorted(set(energy["indicator_code"])) == ["AIRPOL", "NRGINT"] and len(energy) == 2 * 3 * 14
    assert set(energy["unit"]) == {"Index"} and not energy["imputed"].any()  # both sources cover 2010-2023 for these three

    # exact legacy parity of everything stored, and the imputed flag
    for code, frame in everything.items():
        assert {(r.country_code, r.year): (r.score, r.imputed) for r in frame.itertuples()} == legacy_scores(code) and len(frame) == len(legacy_scores(code))
    rows = {(r.country_code, r.year): r for r in everything["AIRPOL"].itertuples()}
    carried, mean = rows[("MYS", 2000)], rows[("FRA", 2000)]
    assert carried.imputed and carried.provenance == {"imputed": True, "imputation_method": "Backward Extrapolation", "imputation_distance": 10, "source_year": 2010}
    assert len(carried.inputs) == 1 and carried.inputs == rows[("MYS", 2010)].inputs and carried.score == rows[("MYS", 2010)].score
    assert mean.imputed and len(mean.inputs) == 0 and mean.provenance["imputation_method"] == "ImputeReferenceClassAverage" and mean.provenance["reference_score_count"] == 196
    virgin_islands = {r.year: r for r in everything["NRGINT"].itertuples() if r.country_code == "VIR"}
    assert virgin_islands[2023].imputed and virgin_islands[2023].provenance["source_year"] == 2022 and not virgin_islands[2022].imputed

    # dataset queries return canonical source observations only: no extrapolated or averaged row is ever stored as an observation
    assert dtypes(observations.drop(columns=["provenance"])) == DATASET_DTYPES and len(observations) == 598 + 196
    assert not any(p.get("imputed") for p in observations["provenance"])
    assert list(malaysia["year"]) == [2010] and "FRA" not in set(observations[observations["dataset_code"] == "UNSDG_AIRPOL"]["country_code"])
    pollution_rows = observations[observations["dataset_code"] == "UNSDG_AIRPOL"]
    assert {p["source_dimensions"]["location"] for p in pollution_rows["provenance"]} == {"ALLAREA"} and set(pollution_rows["unit"]) == {"mgr/m^3"}


def test_reruns_converge_and_each_indicator_stands_alone(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        sspi.ingest("UNSDG_AIRPOL", client=client_for(server))
        assert sspi.run("NRGINT").written == 0  # its dataset is not ingested: nothing to score, nothing invented
        first = sspi.run("AIRPOL")
        before = stored(db, "AIRPOL")
        assert sspi.run("AIRPOL").written == first.written == 1608 and stored(db, "AIRPOL") == before
        sspi.ingest("UNSDG_NRGINT", client=client_for(server))
        assert sspi.run("NRGINT").written == 599 and stored(db, "AIRPOL") == before
        sspi.ingest(DATASETS, client=client_for(server))  # re-ingesting replaces the observations with the same rows
        assert sspi.run("AIRPOL").written == 1608 and stored(db, "AIRPOL") == before
        assert len(sspi.query(datasets=DATASETS)) == 598 + 196


def test_altnrg_workflow(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(IEA_DATASETS, client=clients_for(server))
        assert sspi.query(indicators=["ALTNRG"]).empty  # ingest() never runs an indicator
        run = sspi.run("ALTNRG")
        assert len(server.requests) == 1  # run() never ingests
        frame = sspi.query(indicators=["ALTNRG"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=["ALTNRG"], include_inputs=True, include_provenance=True)
        observations = sspi.query(datasets=IEA_DATASETS, include_provenance=True)
        nuclear = sspi.query(datasets=["IEA_NCLEAR"])
    assert server.requests == ["https://api.iea.org/stats/indicator/TESbySource"] and ingestion.source_fetches == ("TESbySource",)  # seven datasets, one request
    assert ingestion.counts == {"IEA_TLCOAL": 258, "IEA_NATGAS": 282, "IEA_NCLEAR": 126, "IEA_HYDROP": 249, "IEA_GEOPWR": 201, "IEA_BIOWAS": 284, "IEA_FSLOIL": 284}
    assert [d.missing_values for d in ingestion.per_dataset] == [4, 0, 0, 0, 10, 0, 0] and all(("WORLD", "WORLD") in d.skipped_areas for d in ingestion.per_dataset)
    assert (len(run.observed_scores), len(run.imputed_scores), run.written, len(run.unscored)) == (91, 1518, 1609, 91)

    assert dtypes(frame) == INDICATOR_DTYPES and len(frame) == 3 * 14 and set(frame["unit"]) == {"Index"}
    flags = {country: set(frame[frame["country_code"] == country]["imputed"]) for country in ("MYS", "AUT", "USA")}
    assert flags == {"MYS": {True}, "AUT": {True}, "USA": {False}}  # no nuclear row: zero-filled input, so flagged imputed (ALTNRG-2)

    # exact legacy parity of everything stored, and the imputed flag
    assert {(r.country_code, r.year): (r.score, r.imputed) for r in everything.itertuples()} == legacy_scores("ALTNRG") and len(everything) == 1609
    rows = {(r.country_code, r.year): r for r in everything.itertuples()}
    assert all(r.provenance == {} and len(r.inputs) == 7 for r in everything.itertuples())  # imputation is on the inputs, never on the score
    zero = next(i for i in rows[("MYS", 2020)].inputs if i["dataset_code"] == "IEA_NCLEAR")
    assert (zero["value"], zero["unit"], zero["imputation_method"]) == (0.0, "PJ", "Zero imputation for missing energy type")
    assert not any(i.get("imputed") for i in rows[("USA", 2020)].inputs)

    # dataset queries return canonical source observations only: no zero-filled, carried or interpolated row is ever stored
    assert dtypes(observations.drop(columns=["provenance"])) == DATASET_DTYPES and len(observations) == 1684 and set(observations["unit"]) == {"TJ"}
    assert not any(p.get("imputed") for p in observations["provenance"]) and (observations["value"] != 0).all()
    assert sorted(set(nuclear["country_code"])) == ["JPN", "LTU", "PAK", "USA"] and nuclear[nuclear["country_code"] == "LTU"]["year"].max() == 2009
    assert {p["source_dimensions"]["product"] for p in observations[observations["dataset_code"] == "IEA_GEOPWR"]["provenance"]} == {"GEOTHERM"}


def test_altnrg_needs_all_seven_datasets_and_reruns_converge(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        sspi.ingest(IEA_DATASETS[:6], client=clients_for(server))  # everything but oil
        partial = sspi.run("ALTNRG")
        # Legacy behaviour, kept: a dataset with no rows at all is zero-filled for every SSPI67 member, so a run with one
        # dataset not ingested still writes 66 x 24 imputed scores, computed without oil. Ingest all seven before running.
        assert partial.observed_scores == () and partial.written == 1584 == 66 * 24 and len(partial.imputed_scores) == 1584
        sspi.ingest(IEA_DATASETS, client=clients_for(server))
        first = sspi.run("ALTNRG")
        before = stored(db, "ALTNRG")
        assert sspi.run("ALTNRG").written == first.written == 1609 and stored(db, "ALTNRG") == before
        assert sspi.run("AIRPOL").written == 0 and stored(db, "ALTNRG") == before  # another indicator's run does not touch it
        assert sspi.executable_indicators()[-3:] == ("ALTNRG", "NRGINT", "AIRPOL")


def test_the_supported_energy_workflow(db):
    server = FixtureServer()
    with SSPI(database=db) as sspi:
        sspi.ingest(IEA_DATASETS + DATASETS, client=clients_for(server))
        for code in ("ALTNRG", "NRGINT", "AIRPOL"):
            sspi.run(code)
        energy = sspi.query(indicators=["ALTNRG", "NRGINT", "AIRPOL"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
    assert dtypes(energy) == INDICATOR_DTYPES and len(energy) == 3 * 3 * 14
    assert sorted(set(energy["indicator_code"])) == ["AIRPOL", "ALTNRG", "NRGINT"] and len(server.requests) == 3
