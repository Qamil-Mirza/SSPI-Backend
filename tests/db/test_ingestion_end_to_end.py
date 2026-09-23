"""Fixture API payloads -> normalization -> Observation[] -> replace_dataset ->
PostgreSQL -> get_observations, on the isolated test database, for all three
BIODIV input datasets."""

import json
from pathlib import Path

from sspi.db import Repository
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}


def test_unsdg_marine_fixture_round_trips_through_postgres(db):
    dataset = MetadataCatalog.load().dataset("UNSDG_MARINE")
    result = normalize_unsdg_dataset(dataset, PAYLOADS["14.5.1"])

    with db.transaction() as session:
        written = Repository(session).replace_dataset(dataset.code, result.observations)
    assert written == len(result.observations) == 104

    with db.transaction() as session:
        repo = Repository(session)
        mys = repo.get_observations(dataset_codes=["UNSDG_MARINE"], countries=["MYS"], years=(2010, 2023))
        everything = repo.get_observations(dataset_codes=["UNSDG_MARINE"])

    assert [o.year for o in mys] == list(range(2010, 2024))
    assert mys[0].value == next(o.value for o in result.observations if o.country_code == "MYS" and o.year == 2010)
    assert all(o.unit == "PERCENT" and o.dataset_code == "UNSDG_MARINE" for o in mys)
    assert mys[0].provenance["source_geo_area_code"] == "458"
    assert mys[0].provenance["source_series"] == "ER_MRN_MPA"
    assert everything == result.observations  # exact round trip, provenance included

    # Rerunning the ingestion converges instead of duplicating.
    with db.transaction() as session:
        Repository(session).replace_dataset(dataset.code, result.observations)
    with db.transaction() as session:
        assert len(Repository(session).get_observations(dataset_codes=["UNSDG_MARINE"])) == 104


def test_all_three_biodiv_datasets_round_trip_through_postgres(db):
    catalog = MetadataCatalog.load()
    dependencies = catalog.dataset_dependencies("BIODIV")
    results = {}
    with db.transaction() as session:
        repo = Repository(session)
        for dataset in dependencies:
            rows = PAYLOADS[dataset.source.query_code]  # one shared 15.1.2 payload serves two datasets
            results[dataset.code] = normalize_unsdg_dataset(dataset, rows)
            repo.replace_dataset(dataset.code, results[dataset.code].observations)

    with db.transaction() as session:
        repo = Repository(session)
        stored = repo.get_observations(dataset_codes=[d.code for d in dependencies])
        mys_2020 = repo.get_observations(dataset_codes=[d.code for d in dependencies], countries=["MYS"], years=(2020, 2020))
        austria = repo.get_observations(countries=["AUT"])

    assert len(stored) == 3 * 104
    assert stored == sorted((o for r in results.values() for o in r.observations), key=lambda o: (o.dataset_code, o.country_code, o.year))
    assert {(o.dataset_code, o.value) for o in mys_2020} == {("UNSDG_MARINE", 19.70109), ("UNSDG_TERRST", 37.03085), ("UNSDG_FRSHWT", 32.45402)}
    # Landlocked country: two of the three BIODIV inputs exist, the marine one does not. Not filled here.
    assert {o.dataset_code for o in austria} == {"UNSDG_TERRST", "UNSDG_FRSHWT"}
