"""IndicatorScore persistence: round trip incl. inputs, nullable score, rejection
of malformed legacy scores, repeated writes."""

import math

import pytest
from sqlalchemy import text

from sspi.db import Repository
from sspi.errors import InvalidScoreError
from sspi.scoring import ComputedValue, IndicatorScore, Observation


def obs(code, country="MYS", year=2020, value=50.0, unit="PERCENT", **provenance):
    return Observation(code, country, year, value, unit, provenance)


def score(indicator="BIODIV", country="MYS", year=2020, value=0.5, unit="Index", inputs=(), computed=()):
    return IndicatorScore(indicator, country, year, value, unit, tuple(inputs), tuple(computed))


def test_round_trip_with_inputs_and_computed_values(db):
    original = score(
        value=0.55,
        inputs=[obs("UNSDG_MARINE", value=60, description="marine"), obs("UNSDG_TERRST", value=50, imputed=True, imputation_method="Linear Interpolation", imputation_distance=2)],
        computed=[ComputedValue("IEA_ALTNRG_PERCENTAGE", 42.5, "% of TES"), ComputedValue("INT_VALUE", 3, "count")],
    )
    with db.transaction() as session:
        assert Repository(session).save_scores([original]) == 1
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores(indicator_codes=["BIODIV"])
    assert loaded == original
    assert loaded.inputs[1].provenance == {"imputed": True, "imputation_method": "Linear Interpolation", "imputation_distance": 2}
    assert loaded.computed[1].value == 3 and isinstance(loaded.computed[1].value, int)


def test_none_score_round_trips_as_none(db):
    with db.transaction() as session:
        Repository(session).save_scores([score(value=None, inputs=[obs("DATASET_A", value=30)])])
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
        stored = session.execute(text("SELECT score FROM indicator_score")).scalar_one()
    assert loaded.score is None
    assert stored is None
    assert loaded.unit == "Index"


@pytest.mark.parametrize(
    "bad, match",
    [
        ((0.5,), "not numeric"),  # SENIOR trailing-comma tuple
        ("0.5", "not numeric"),
        (True, "not numeric"),
        (float("nan"), "finite"),
        (float("inf"), "finite"),
        (1.5, "between 0 and 1"),
        (-0.1, "between 0 and 1"),
    ],
)
def test_malformed_or_out_of_range_scores_are_rejected_and_nothing_written(db, bad, match):
    with pytest.raises(InvalidScoreError, match=match) as info:
        with db.transaction() as session:
            Repository(session).save_scores([score(value=0.2), score(country="USA", value=bad)])
    assert "BIODIV/USA/2020" in str(info.value)
    with db.transaction() as session:
        assert Repository(session).get_scores() == []


def test_boundary_scores_accepted(db):
    with db.transaction() as session:
        Repository(session).save_scores([score(country="AAA", value=0), score(country="BBB", value=1), score(country="CCC", value=0.0)])
    with db.transaction() as session:
        assert [s.score for s in Repository(session).get_scores()] == [0.0, 1.0, 0.0]


def test_non_string_unit_rejected(db):
    with pytest.raises(InvalidScoreError, match="unit"):
        with db.transaction() as session:
            Repository(session).save_scores([score(unit=None)])


def test_non_finite_computed_value_rejected(db):
    with pytest.raises(InvalidScoreError, match="computed"):
        with db.transaction() as session:
            Repository(session).save_scores([score(computed=[ComputedValue("X", float("inf"), "u")])])


def test_filters_and_ordering(db):
    rows = [
        score("BIODIV", "MYS", 2010, 0.1), score("BIODIV", "MYS", 2020, 0.2), score("BIODIV", "USA", 2020, 0.3),
        score("REDLST", "MYS", 2020, 0.4), score("REDLST", "KEN", 2015, 0.5),
    ]
    with db.transaction() as session:
        Repository(session).save_scores(rows)
    with db.transaction() as session:
        repo = Repository(session)
        assert [(s.indicator_code, s.country_code, s.year) for s in repo.get_scores()] == [
            ("BIODIV", "MYS", 2010), ("BIODIV", "MYS", 2020), ("BIODIV", "USA", 2020), ("REDLST", "KEN", 2015), ("REDLST", "MYS", 2020)
        ]
        assert [s.score for s in repo.get_scores(indicator_codes=["REDLST"])] == [0.5, 0.4]
        assert [s.score for s in repo.get_scores(countries=["MYS"], years=(2015, 2020))] == [0.2, 0.4]
        assert repo.get_scores(indicator_codes=[]) == []


def test_save_scores_is_an_upsert(db):
    with db.transaction() as session:
        Repository(session).save_scores([score(value=0.5, inputs=[obs("A", value=1)])])
    with db.transaction() as session:
        Repository(session).save_scores([score(value=0.9, unit="Index v2", inputs=[obs("A", value=2)])])
    with db.transaction() as session:
        loaded = Repository(session).get_scores()
        count = session.execute(text("SELECT count(*) FROM indicator_score")).scalar_one()
    assert count == 1
    assert loaded == [score(value=0.9, unit="Index v2", inputs=[obs("A", value=2)])]


def test_same_identity_twice_in_batch_rejected(db):
    with pytest.raises(InvalidScoreError, match="duplicate"):
        with db.transaction() as session:
            Repository(session).save_scores([score(value=0.1), score(value=0.2)])


def test_replace_indicator_scores(db):
    with db.transaction() as session:
        Repository(session).save_scores([score("BIODIV", "MYS", 2010, 0.1), score("BIODIV", "MYS", 2020, 0.2), score("REDLST", "MYS", 2020, 0.4)])
    with db.transaction() as session:
        assert Repository(session).replace_indicator_scores("BIODIV", [score("BIODIV", "USA", 2021, 0.7)]) == 1
    with db.transaction() as session:
        repo = Repository(session)
        assert [(s.indicator_code, s.country_code, s.year) for s in repo.get_scores()] == [("BIODIV", "USA", 2021), ("REDLST", "MYS", 2020)]
    with pytest.raises(InvalidScoreError, match="REDLST"):
        with db.transaction() as session:
            Repository(session).replace_indicator_scores("BIODIV", [score("REDLST", "USA", 2021, 0.7)])


def test_delete_indicator_scores(db):
    with db.transaction() as session:
        Repository(session).save_scores([score("BIODIV", "MYS", 2010, 0.1), score("REDLST", "MYS", 2020, 0.4)])
    with db.transaction() as session:
        assert Repository(session).delete_indicator_scores("BIODIV") == 1
        assert Repository(session).delete_indicator_scores("BIODIV") == 0
    with db.transaction() as session:
        assert [s.indicator_code for s in Repository(session).get_scores()] == ["REDLST"]


def test_score_check_constraint_backs_repository_rule(db):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with db.transaction() as session:
            session.execute(text("INSERT INTO indicator_score (indicator_code, country_code, year, score, unit, inputs, imputed) VALUES ('BIODIV', 'MYS', 2020, 1.5, 'Index', '{}', false)"))
    with db.transaction() as session:
        session.execute(text("INSERT INTO indicator_score (indicator_code, country_code, year, score, unit, inputs, imputed) VALUES ('BIODIV', 'MYS', 2020, NULL, 'Index', '{}', false)"))
    assert math.isnan(float("nan"))  # keep math import honest


def test_imputation_provenance_survives_the_json_round_trip_unchanged(db):
    from sspi.imputation import impute_dataset

    observed = [obs("DS", country="MYS", year=y, value=float(y)) for y in (2001, 2003)]
    imputed = impute_dataset(observed, "DS", ["AUT"], 2000, 2004).imputed
    original = score(inputs=imputed)
    with db.transaction() as session:
        Repository(session).save_scores([original])
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
    assert loaded == original
    assert {o.provenance["imputation_method"] for o in loaded.inputs} == {"ImputeReferenceClassAverage", "Backward Extrapolation", "Forward Extrapolation", "Linear Interpolation"}
