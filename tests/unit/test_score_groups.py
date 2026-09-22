"""Translated from the old tests/unit/utilities/test_score_indicator_documents.py
(plus the filter_incomplete_data partition, which is now built into the typed
result).

Old `score_indicator_documents` stamped `Score` and `Unit` onto dicts in place
and left skipped documents without those keys; `filter_incomplete_data` then
split on key presence. The new `score_groups` returns `ScoringResult(scored,
unscored)` with distinct record types, so "skipped" is a type, not a missing
key.

Dropped (representation-only):
- test_score_indicator_documents_non_numeric_values / _none_values /
  _missing_value_field: pinned non-numeric *observation* values. The
  surviving semantic (a non-numeric computed value vetoes the group) is
  test_non_numeric_computed_value_makes_group_unscored.
- test_score_indicator_documents_mutates_in_place: replaced by
  test_score_groups_does_not_mutate_input.
- All of test_filter_incomplete_data.py: every test there pins dict-key
  presence semantics (`Unit: None` counts as present, `Year: "2020"` accepted,
  lowercase key rejected). The one semantic survivor, "a None score is still a
  score", is test_none_score_is_still_scored.
"""

import pytest

from sspi.scoring import (
    ComputedValue,
    IndicatorScore,
    Observation,
    ObservationGroup,
    ScoringResult,
    UnscoredGroup,
    UnscoredReason,
    group_observations,
    score_groups,
)


def obs(code, country, year, value, unit="Index", **provenance):
    return Observation(code, country, year, value, unit, provenance)


def one_group(*observations, indicator="TEST_INDICATOR"):
    return group_observations(list(observations), indicator)


def test_basic_string_unit():
    def score_function(DATASET_A, DATASET_B):
        return (DATASET_A + DATASET_B) / 2

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200)), score_function, "Average")
    assert isinstance(result, ScoringResult)
    assert result.unscored == []
    assert len(result.scored) == 1
    assert result.scored[0].score == 150.0
    assert result.scored[0].unit == "Average"


def test_callable_unit_receives_same_positional_args():
    def score_function(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    def unit_function(DATASET_A, DATASET_B):
        return "High A" if DATASET_A > DATASET_B else "High B"

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200)), score_function, unit_function)
    assert result.scored[0].score == 300
    assert result.scored[0].unit == "High B"


def test_multiple_groups_keep_input_order():
    def score_function(DATASET_A, DATASET_B):
        return DATASET_A * DATASET_B

    groups = one_group(
        obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200),
        obs("DATASET_A", "CAN", 2020, 150), obs("DATASET_B", "CAN", 2020, 250),
    )
    result = score_groups(groups, score_function, "Product")
    assert [s.score for s in result.scored] == [20000, 37500]
    assert all(s.unit == "Product" for s in result.scored)


def test_single_dataset_exact_float():
    def score_function(SOLO_DATASET):
        return SOLO_DATASET / 100

    result = score_groups(one_group(obs("SOLO_DATASET", "USA", 2020, 85.5)), score_function, "Normalized")
    assert result.scored[0].score == 0.855
    assert result.scored[0].unit == "Normalized"


def test_complex_scoring():
    def complex_score(GDP, POPULATION, AREA):
        gdp_per_capita = GDP / POPULATION
        density = POPULATION / AREA
        return gdp_per_capita * density ** 0.5

    result = score_groups(
        one_group(obs("GDP", "USA", 2020, 50000), obs("POPULATION", "USA", 2020, 330), obs("AREA", "USA", 2020, 9834)),
        complex_score, "Composite Index",
    )
    assert result.scored[0].score == pytest.approx((50000 / 330) * (330 / 9834) ** 0.5, rel=1e-6)


def test_missing_dataset_makes_group_unscored_with_reason():
    def score_function(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 100)), score_function, "Sum")
    assert result.scored == []
    assert len(result.unscored) == 1
    unscored = result.unscored[0]
    assert isinstance(unscored, UnscoredGroup)
    assert unscored.indicator_code == "TEST_INDICATOR"
    assert unscored.country_code == "USA"
    assert unscored.year == 2020
    assert unscored.reason is UnscoredReason.MISSING_DATASETS
    assert unscored.details == ("DATASET_B",)
    assert [o.dataset_code for o in unscored.inputs] == ["DATASET_A"]


def test_missing_details_list_every_missing_code_in_signature_order():
    def score_function(DATASET_C, DATASET_A, DATASET_B):
        return 0

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 1)), score_function, "x")
    assert result.unscored[0].details == ("DATASET_C", "DATASET_B")


def test_parameter_with_default_is_still_required():
    # Legacy: every parameter name is looked up, defaults are never used.
    def score_function(DATASET_A, DATASET_B=None):
        return DATASET_A

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 1)), score_function, "x")
    assert result.scored == []
    assert result.unscored[0].details == ("DATASET_B",)


def test_non_numeric_computed_value_makes_group_unscored():
    group = ObservationGroup(
        "TEST_INDICATOR", "USA", 2020,
        inputs=(obs("DATASET_A", "USA", 2020, 100),),
        computed=(ComputedValue("COMPUTED_X", "not_a_number", "n/a"), ComputedValue("COMPUTED_Y", None, "n/a")),
    )

    def score_function(DATASET_A):  # does not even use the computed values
        return DATASET_A

    result = score_groups([group], score_function, "Sum")
    assert result.scored == []
    assert result.unscored[0].reason is UnscoredReason.NON_NUMERIC_COMPUTED_VALUE
    assert result.unscored[0].details == ("COMPUTED_X", "COMPUTED_Y")


def test_non_numeric_check_precedes_missing_check():
    group = ObservationGroup(
        "TEST_INDICATOR", "USA", 2020,
        inputs=(obs("DATASET_A", "USA", 2020, 100),),
        computed=(ComputedValue("COMPUTED_X", "text", "n/a"),),
    )

    def score_function(DATASET_A, DATASET_B):
        return DATASET_A

    result = score_groups([group], score_function, "Sum")
    assert result.unscored[0].reason is UnscoredReason.NON_NUMERIC_COMPUTED_VALUE


def test_computed_values_are_bound_by_name_and_override_observations():
    # Legacy last-wins: computed values were appended after observations.
    group = ObservationGroup(
        "TEST_INDICATOR", "USA", 2020,
        inputs=(obs("DATASET_A", "USA", 2020, 1),),
        computed=(ComputedValue("DATASET_A", 10, "n/a"), ComputedValue("DATASET_B", 5, "n/a")),
    )

    def score_function(DATASET_A, DATASET_B):
        return DATASET_A - DATASET_B

    result = score_groups([group], score_function, "Diff")
    assert result.scored[0].score == 5


def test_scored_record_preserves_inputs_computed_and_provenance():
    original = obs("DATASET_A", "USA", 2020, 100, "Index", ExistingField="existing_value", Metadata={"source": "test"})
    group = ObservationGroup("PRESERVE_INDICATOR", "USA", 2020, inputs=(original,), computed=(ComputedValue("C", 1.0, "u"),))

    def score_function(DATASET_A):
        return DATASET_A * 2

    result = score_groups([group], score_function, "Doubled")
    scored = result.scored[0]
    assert isinstance(scored, IndicatorScore)
    assert scored.score == 200
    assert scored.unit == "Doubled"
    assert scored.indicator_code == "PRESERVE_INDICATOR"
    assert scored.country_code == "USA"
    assert scored.year == 2020
    assert scored.inputs == (original,)
    assert scored.inputs[0].provenance == {"ExistingField": "existing_value", "Metadata": {"source": "test"}}
    assert scored.computed == (ComputedValue("C", 1.0, "u"),)


def test_empty_groups():
    def score_function(DATASET_A):
        return DATASET_A

    assert score_groups([], score_function, "Unit") == ScoringResult([], [])


def test_score_groups_does_not_mutate_input():
    groups = one_group(obs("DATASET_A", "USA", 2020, 100))
    before = list(groups)
    score_groups(groups, lambda DATASET_A: DATASET_A / 2, "Halved")
    assert groups == before


def test_binding_is_by_name_not_position():
    def score_function(DATASET_A, DATASET_B):
        return DATASET_A - DATASET_B

    result = score_groups(one_group(obs("DATASET_B", "USA", 2020, 200), obs("DATASET_A", "USA", 2020, 100)), score_function, "Difference")
    assert result.scored[0].score == -100


@pytest.mark.parametrize(
    "a, b, expected",
    [(0, 100, 100), (-50, 150, 100), (1e15, 2e15, 3e15)],
)
def test_zero_negative_and_large_values(a, b, expected):
    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, a), obs("DATASET_B", "USA", 2020, b)), lambda DATASET_A, DATASET_B: DATASET_A + DATASET_B, "Sum")
    assert result.scored[0].score == expected


def test_float_values():
    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 33.33), obs("DATASET_B", "USA", 2020, 66.67)), lambda DATASET_A, DATASET_B: DATASET_A + DATASET_B, "Sum")
    assert result.scored[0].score == pytest.approx(100.0, rel=1e-6)


def test_extra_datasets_are_ignored_for_binding_but_kept_as_inputs():
    def score_function(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    result = score_groups(
        one_group(obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 200), obs("DATASET_C", "USA", 2020, 300)),
        score_function, "Sum",
    )
    assert result.scored[0].score == 300
    assert [o.dataset_code for o in result.scored[0].inputs] == ["DATASET_A", "DATASET_B", "DATASET_C"]


def test_score_function_exceptions_propagate():
    with pytest.raises(ZeroDivisionError):
        score_groups(one_group(obs("DATASET_A", "USA", 2020, 100), obs("DATASET_B", "USA", 2020, 0)), lambda DATASET_A, DATASET_B: DATASET_A / DATASET_B, "Ratio")


def test_none_score_is_still_scored():
    # Legacy compatibility: whatever the score function returns is recorded.
    def none_returning_score(DATASET_A, DATASET_B):
        return None if DATASET_A < 50 else DATASET_A + DATASET_B

    result = score_groups(one_group(obs("DATASET_A", "USA", 2020, 30), obs("DATASET_B", "USA", 2020, 80)), none_returning_score, "Sum")
    assert len(result.scored) == 1
    assert result.scored[0].score is None
    assert result.unscored == []


def test_unit_must_be_str_or_callable():
    with pytest.raises(TypeError):
        score_groups(one_group(obs("DATASET_A", "USA", 2020, 1)), lambda DATASET_A: DATASET_A, 123)
