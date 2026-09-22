"""Translated from the old tests/unit/utilities/test_create_computed_series.py.

Old `create_computed_series` appended a dict with `Computed: True` and a
`ValueFunction` source-text field into each document's `Datasets` list, in
place. The new `add_computed_series` returns new `ObservationGroup`s whose
`computed` tuple holds `ComputedValue` records; inputs are untouched.

Dropped (representation-only or deliberately not ported):
- test_create_computed_series_non_numeric_values / _none_values /
  _missing_value_key: pinned non-numeric *observation* values, which a typed
  Observation cannot hold. The surviving semantic (a non-numeric value already
  in the group blocks later specs) is covered by
  test_non_numeric_earlier_computed_value_blocks_later_spec.
- test_create_computed_series_value_function_source and the
  `"ValueFunction" in computed_dataset` asserts: inspect.getsource provenance
  is intentionally not ported (flagged for redesign).
- test_create_computed_series_mutates_original_list: replaced by
  test_add_computed_series_does_not_mutate_input.
"""

import pytest

from sspi.scoring import ComputedSeries, ComputedValue, Observation, add_computed_series, group_observations


def obs(code, country, year, value):
    return Observation(code, country, year, value, "Index")


def groups_for(*observations, indicator="TEST_INDICATOR"):
    return group_observations(list(observations), indicator)


def computed_by_code(group):
    return {c.dataset_code: c for c in group.computed}


def test_single_computation():
    def multiply_values(DATASET_A, DATASET_B):
        return DATASET_A * DATASET_B

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10), obs("DATASET_B", "USA", 2020, 5))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_PRODUCT", "Index", multiply_values)])

    assert len(result) == 1
    assert len(result[0].inputs) == 2
    assert len(result[0].computed) == 1
    product = computed_by_code(result[0])["COMPUTED_PRODUCT"]
    assert isinstance(product, ComputedValue)
    assert product.value == 50
    assert product.unit == "Index"


def test_multiple_computations_applied_in_order():
    def add_values(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    def subtract_values(DATASET_A, DATASET_B):
        return DATASET_A - DATASET_B

    groups = groups_for(obs("DATASET_A", "USA", 2020, 15), obs("DATASET_B", "USA", 2020, 8))
    result = add_computed_series(
        groups,
        [ComputedSeries("COMPUTED_SUM", "Total", add_values), ComputedSeries("COMPUTED_DIFF", "Difference", subtract_values)],
    )
    assert [c.dataset_code for c in result[0].computed] == ["COMPUTED_SUM", "COMPUTED_DIFF"]
    by_code = computed_by_code(result[0])
    assert by_code["COMPUTED_SUM"].value == 23
    assert by_code["COMPUTED_DIFF"].value == 7
    assert by_code["COMPUTED_SUM"].unit == "Total"
    assert by_code["COMPUTED_DIFF"].unit == "Difference"


def test_computed_per_group():
    def ratio_values(DATASET_A, DATASET_B):
        return DATASET_A / DATASET_B

    groups = groups_for(
        obs("DATASET_A", "USA", 2020, 20), obs("DATASET_B", "USA", 2020, 4),
        obs("DATASET_A", "CAN", 2020, 30), obs("DATASET_B", "CAN", 2020, 6),
    )
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_RATIO", "Ratio", ratio_values)])
    usa = next(g for g in result if g.country_code == "USA")
    can = next(g for g in result if g.country_code == "CAN")
    assert computed_by_code(usa)["COMPUTED_RATIO"].value == 5.0
    assert computed_by_code(can)["COMPUTED_RATIO"].value == 5.0


def test_missing_dataset_skips_silently():
    def multiply_values(DATASET_A, DATASET_B):
        return DATASET_A * DATASET_B

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_PRODUCT", "Index", multiply_values)])
    assert len(result) == 1
    assert len(result[0].inputs) == 1
    assert result[0].computed == ()


def test_value_function_exception_is_swallowed():
    def divide_by_zero(DATASET_A, DATASET_B):
        return DATASET_A / DATASET_B

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10), obs("DATASET_B", "USA", 2020, 0))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_RATIO", "Ratio", divide_by_zero)])
    assert result[0].computed == ()


def test_non_numeric_earlier_computed_value_blocks_later_spec():
    # Legacy: the numeric guard scans every value already in the group, so a
    # non-numeric computed value from spec 1 makes spec 2 skip the group.
    def text_value(DATASET_A):
        return "text"

    def double(DATASET_A):
        return DATASET_A * 2

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10))
    result = add_computed_series(
        groups, [ComputedSeries("COMPUTED_TEXT", "n/a", text_value), ComputedSeries("COMPUTED_DOUBLE", "x2", double)]
    )
    assert [c.dataset_code for c in result[0].computed] == ["COMPUTED_TEXT"]
    assert result[0].computed[0].value == "text"


def test_bool_result_is_recorded_but_counts_as_non_numeric():
    # Legacy exact-type check: bool is not int/float for the purposes of the guard.
    def is_big(DATASET_A):
        return DATASET_A > 5

    def double(DATASET_A):
        return DATASET_A * 2

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10))
    result = add_computed_series(
        groups, [ComputedSeries("COMPUTED_FLAG", "bool", is_big), ComputedSeries("COMPUTED_DOUBLE", "x2", double)]
    )
    assert [c.dataset_code for c in result[0].computed] == ["COMPUTED_FLAG"]
    assert result[0].computed[0].value is True


def test_single_argument_function():
    def square_value(DATASET_A):
        return DATASET_A ** 2

    groups = groups_for(obs("DATASET_A", "USA", 2020, 7))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_SQUARE", "Squared", square_value)])
    square = computed_by_code(result[0])["COMPUTED_SQUARE"]
    assert square.value == 49
    assert square.unit == "Squared"


def test_three_argument_function():
    def weighted_average(DATASET_A, DATASET_B, DATASET_C):
        return (DATASET_A * 0.5) + (DATASET_B * 0.3) + (DATASET_C * 0.2)

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10), obs("DATASET_B", "USA", 2020, 20), obs("DATASET_C", "USA", 2020, 30))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_WEIGHTED", "WeightedAvg", weighted_average)])
    weighted = computed_by_code(result[0])["COMPUTED_WEIGHTED"]
    assert weighted.value == (10 * 0.5) + (20 * 0.3) + (30 * 0.2)
    assert weighted.unit == "WeightedAvg"


def test_empty_specification_leaves_groups_unchanged():
    groups = groups_for(obs("DATASET_A", "USA", 2020, 10))
    result = add_computed_series(groups, [])
    assert result == groups


def test_empty_groups():
    def add_values(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    assert add_computed_series([], [ComputedSeries("COMPUTED_SUM", "Total", add_values)]) == []


def test_computed_value_carries_code_unit_and_value_only():
    def simple_addition(DATASET_A, DATASET_B):
        return DATASET_A + DATASET_B

    groups = groups_for(obs("DATASET_A", "USA", 2020, 15), obs("DATASET_B", "USA", 2020, 25))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_SUM", "Total", simple_addition)])
    computed = computed_by_code(result[0])["COMPUTED_SUM"]
    assert computed == ComputedValue("COMPUTED_SUM", 40.0, "Total")


def test_float_and_int_observation_values():
    def complex_calculation(DATASET_A, DATASET_B):
        return (DATASET_A * 1.5) + (DATASET_B / 2.0)

    groups = groups_for(obs("DATASET_A", "USA", 2020, 10), obs("DATASET_B", "USA", 2020, 5.5))
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_COMPLEX", "Complex", complex_calculation)])
    assert computed_by_code(result[0])["COMPUTED_COMPLEX"].value == (10 * 1.5) + (5.5 / 2.0)


def test_add_computed_series_does_not_mutate_input():
    def double_value(DATASET_A):
        return DATASET_A * 2

    groups = groups_for(obs("DATASET_A", "USA", 2020, 5))
    before = list(groups)
    result = add_computed_series(groups, [ComputedSeries("COMPUTED_DOUBLE", "Doubled", double_value)])
    assert result is not groups
    assert groups == before
    assert groups[0].computed == ()
    assert len(result[0].computed) == 1


def test_computed_series_accepts_legacy_tuple_spec():
    def double_value(DATASET_A):
        return DATASET_A * 2

    groups = groups_for(obs("DATASET_A", "USA", 2020, 5))
    result = add_computed_series(groups, [("COMPUTED_DOUBLE", "Doubled", double_value)])
    assert computed_by_code(result[0])["COMPUTED_DOUBLE"].value == 10


def test_computed_series_spec_rejects_non_callable():
    with pytest.raises(TypeError):
        ComputedSeries("X", "unit", "not callable")
