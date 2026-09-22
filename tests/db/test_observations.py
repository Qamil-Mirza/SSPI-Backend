"""Observation persistence: round trip, filtering, identity, repeated writes."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from sspi.db import Repository
from sspi.errors import InvalidObservationError
from sspi.scoring import Observation


def obs(code="UNSDG_MARINE", country="MYS", year=2020, value=60.0, unit="PERCENT", **provenance):
    return Observation(code, country, year, value, unit, provenance)


PANEL = [
    obs("UNSDG_MARINE", "MYS", 2010, 40.0), obs("UNSDG_MARINE", "MYS", 2020, 60.0), obs("UNSDG_MARINE", "MYS", 2023, 61.5),
    obs("UNSDG_MARINE", "USA", 2010, 70.0), obs("UNSDG_MARINE", "USA", 2020, 72.25),
    obs("UNSDG_TERRST", "MYS", 2020, 30.0), obs("UNSDG_TERRST", "USA", 2020, 45.0),
    obs("UNSDG_FRSHWT", "MYS", 2020, 55.0, "PERCENT", description="freshwater sites"),
    obs("WB_POPULN", "KEN", 2005, 3.6e7, "People"),
]


def test_round_trip_is_an_equivalent_observation(db):
    original = obs(value=60, provenance_note="x", description="Percentage of marine sites", source={"query": "14.5.1"}, n=1)
    with db.transaction() as session:
        assert Repository(session).save_observations([original]) == 1
    with db.transaction() as session:
        (loaded,) = Repository(session).get_observations(dataset_codes=["UNSDG_MARINE"])
    assert loaded == original
    assert loaded.value == 60.0 and isinstance(loaded.value, float)
    assert loaded.provenance == {"provenance_note": "x", "description": "Percentage of marine sites", "source": {"query": "14.5.1"}, "n": 1}


def test_exact_float_values_survive(db):
    values = [0.1 + 0.2, 1e-300, 1.7976931348623157e308, -0.0, 123456789.123456789]
    rows = [obs("DS", "USA", 2000 + i, v) for i, v in enumerate(values)]
    with db.transaction() as session:
        Repository(session).save_observations(rows)
    with db.transaction() as session:
        loaded = Repository(session).get_observations(dataset_codes=["DS"])
    assert [o.value for o in loaded] == values


@pytest.fixture
def panel(db):
    with db.transaction() as session:
        Repository(session).save_observations(PANEL)
    return db


def keys(observations):
    return [(o.dataset_code, o.country_code, o.year) for o in observations]


def test_no_filters_returns_everything_in_key_order(panel):
    with panel.transaction() as session:
        loaded = Repository(session).get_observations()
    assert keys(loaded) == sorted(keys(PANEL))


def test_filter_by_dataset(panel):
    with panel.transaction() as session:
        loaded = Repository(session).get_observations(dataset_codes=["UNSDG_TERRST", "UNSDG_FRSHWT"])
    assert keys(loaded) == [("UNSDG_FRSHWT", "MYS", 2020), ("UNSDG_TERRST", "MYS", 2020), ("UNSDG_TERRST", "USA", 2020)]


def test_filter_by_country(panel):
    with panel.transaction() as session:
        loaded = Repository(session).get_observations(countries=["USA"])
    assert {o.country_code for o in loaded} == {"USA"}
    assert len(loaded) == 3


def test_filter_by_year_range_is_inclusive(panel):
    with panel.transaction() as session:
        loaded = Repository(session).get_observations(years=(2010, 2020))
    assert {o.year for o in loaded} == {2010, 2020}
    assert len(loaded) == 7


def test_combined_filters(panel):
    with panel.transaction() as session:
        loaded = Repository(session).get_observations(dataset_codes=["UNSDG_MARINE"], countries=["MYS", "USA"], years=(2020, 2023))
    assert keys(loaded) == [("UNSDG_MARINE", "MYS", 2020), ("UNSDG_MARINE", "MYS", 2023), ("UNSDG_MARINE", "USA", 2020)]


def test_empty_filter_list_returns_nothing(panel):
    with panel.transaction() as session:
        repo = Repository(session)
        assert repo.get_observations(dataset_codes=[]) == []
        assert repo.get_observations(countries=[]) == []


def test_invalid_year_range_rejected(panel):
    with panel.transaction() as session:
        with pytest.raises(ValueError):
            Repository(session).get_observations(years=(2020, 2010))


def test_save_is_an_upsert_not_a_duplicate(db):
    with db.transaction() as session:
        Repository(session).save_observations([obs(value=60.0, unit="PERCENT", note="first")])
    with db.transaction() as session:
        Repository(session).save_observations([obs(value=65.0, unit="pct", note="second")])
    with db.transaction() as session:
        loaded = Repository(session).get_observations()
        count = session.execute(text("SELECT count(*) FROM observation")).scalar_one()
    assert count == 1
    assert loaded == [obs(value=65.0, unit="pct", note="second")]


def test_same_identity_twice_in_one_batch_is_rejected_before_writing(db):
    with pytest.raises(InvalidObservationError, match="duplicate"):
        with db.transaction() as session:
            Repository(session).save_observations([obs(value=1.0), obs(value=2.0)])
    with db.transaction() as session:
        assert Repository(session).get_observations() == []


def test_extra_dimension_keys_are_rejected_by_invariant(db):
    for key in ("AdditionalIdentifiers", "additional_identifiers", "dimensions"):
        with pytest.raises(InvalidObservationError, match="dataset_code, country_code, year"):
            with db.transaction() as session:
                Repository(session).save_observations([obs(**{key: {"CityCode": "KUL"}})])


def test_non_json_provenance_is_rejected(db):
    with pytest.raises(InvalidObservationError, match="JSON"):
        with db.transaction() as session:
            Repository(session).save_observations([obs(when=object())])


def test_non_observation_input_is_rejected(db):
    with pytest.raises(TypeError):
        with db.transaction() as session:
            Repository(session).save_observations([{"dataset_code": "X"}])  # type: ignore[list-item]


def test_replace_dataset_removes_rows_absent_from_new_batch(panel):
    with panel.transaction() as session:
        count = Repository(session).replace_dataset("UNSDG_MARINE", [obs("UNSDG_MARINE", "MYS", 2021, 99.0)])
    assert count == 1
    with panel.transaction() as session:
        repo = Repository(session)
        assert keys(repo.get_observations(dataset_codes=["UNSDG_MARINE"])) == [("UNSDG_MARINE", "MYS", 2021)]
        assert len(repo.get_observations(dataset_codes=["UNSDG_TERRST"])) == 2  # untouched


def test_replace_dataset_with_empty_batch_clears_the_dataset(panel):
    with panel.transaction() as session:
        assert Repository(session).replace_dataset("UNSDG_MARINE", []) == 0
    with panel.transaction() as session:
        assert Repository(session).get_observations(dataset_codes=["UNSDG_MARINE"]) == []


def test_replace_dataset_refuses_foreign_rows(panel):
    with pytest.raises(InvalidObservationError, match="UNSDG_TERRST"):
        with panel.transaction() as session:
            Repository(session).replace_dataset("UNSDG_MARINE", [obs("UNSDG_TERRST", "MYS", 2021, 1.0)])
    with panel.transaction() as session:
        assert len(Repository(session).get_observations(dataset_codes=["UNSDG_MARINE"])) == 5


def test_delete_dataset(panel):
    with panel.transaction() as session:
        assert Repository(session).delete_dataset("UNSDG_MARINE") == 5
        assert Repository(session).delete_dataset("UNSDG_MARINE") == 0
    with panel.transaction() as session:
        assert len(Repository(session).get_observations()) == len(PANEL) - 5


def test_database_constraints_back_the_domain_rules(db):
    with db.transaction() as session:
        session.execute(text("INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'USA', 2000, 1.0, 'u')"))
    for statement in (
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'USA', 2000, 2.0, 'u')",  # PK
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('ds', 'USA', 2001, 1.0, 'u')",  # lowercase code
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'usa', 2001, 1.0, 'u')",  # lowercase country
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'EU28', 2001, 1.0, 'u')",  # not 3 letters
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'USA', 2001, 'NaN', 'u')",
        "INSERT INTO observation (dataset_code, country_code, year, value, unit) VALUES ('DS', 'USA', 2001, 'Infinity', 'u')",
    ):
        with pytest.raises(IntegrityError):
            with db.transaction() as session:
                session.execute(text(statement))
