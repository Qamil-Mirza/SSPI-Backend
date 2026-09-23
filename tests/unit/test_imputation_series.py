"""Backward extrapolation, forward extrapolation and linear interpolation on
Observation series: legacy formulas, legacy bounds, legacy ordering."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import (
    BACKWARD_EXTRAPOLATION,
    FORWARD_EXTRAPOLATION,
    LINEAR_INTERPOLATION,
    extrapolate_backward,
    extrapolate_forward,
    interpolate_linear,
)
from sspi.scoring import Observation


def obs(country, year, value, dataset="DS_A", unit="PERCENT", **prov):
    return Observation(dataset, country, year, value, unit, prov)


def ident(o):
    return (o.dataset_code, o.country_code, o.year)


# --- backward -----------------------------------------------------------------


def test_backward_fills_years_before_first_with_first_value():
    out = extrapolate_backward([obs("MYS", 2003, 7.5, src="a"), obs("MYS", 2004, 8.0, src="b")], 2000)
    assert [(o.year, o.value) for o in out] == [(2000, 7.5), (2001, 7.5), (2002, 7.5)]
    assert all(o.dataset_code == "DS_A" and o.country_code == "MYS" and o.unit == "PERCENT" for o in out)
    assert dict(out[0].provenance) == {"src": "a", "imputed": True, "imputation_method": BACKWARD_EXTRAPOLATION, "imputation_distance": 3, "anchor_year": 2003}
    assert [o.provenance["imputation_distance"] for o in out] == [3, 2, 1]


def test_backward_does_nothing_when_series_starts_at_or_before_start_year():
    assert extrapolate_backward([obs("MYS", 2000, 1.0)], 2000) == ()
    assert extrapolate_backward([obs("MYS", 1995, 1.0), obs("MYS", 2005, 2.0)], 2000) == ()


def test_backward_uses_earliest_observation_regardless_of_input_order():
    out = extrapolate_backward([obs("MYS", 2003, 13.25), obs("MYS", 2001, 10.5)], 2000)
    assert [(o.year, o.value) for o in out] == [(2000, 10.5)]


# --- forward ------------------------------------------------------------------


def test_forward_fills_years_after_last_with_last_value():
    out = extrapolate_forward([obs("MYS", 2019, 1.0), obs("MYS", 2020, 2.0, src="last")], 2023)
    assert [(o.year, o.value) for o in out] == [(2021, 2.0), (2022, 2.0), (2023, 2.0)]
    assert dict(out[-1].provenance) == {"src": "last", "imputed": True, "imputation_method": FORWARD_EXTRAPOLATION, "imputation_distance": 3, "anchor_year": 2020}


def test_forward_does_nothing_when_series_ends_at_or_after_end_year():
    assert extrapolate_forward([obs("MYS", 2023, 1.0)], 2023) == ()
    assert extrapolate_forward([obs("MYS", 2020, 4.0), obs("MYS", 2025, 9.0)], 2023) == ()


# --- interpolation ------------------------------------------------------------


def test_interior_gap_is_linear_between_neighbours():
    out = interpolate_linear([obs("MYS", 2000, 10.0, src="lo"), obs("MYS", 2002, 20.0, src="hi")])
    assert [(o.year, o.value) for o in out] == [(2001, 15.0)]
    assert dict(out[0].provenance) == {
        "src": "lo",  # legacy copied the lower neighbour's document
        "imputed": True,
        "imputation_method": LINEAR_INTERPOLATION,
        "imputation_distance": 1,
        "anchor_years": [2000, 2002],
        "anchor_values": [10.0, 20.0],
    }


def test_multi_year_gap_and_distance_is_min_to_either_neighbour():
    out = interpolate_linear([obs("MYS", 2000, 10.0), obs("MYS", 2005, 20.0)])
    assert [(o.year, o.value, o.provenance["imputation_distance"]) for o in out] == [(2001, 12.0, 1), (2002, 14.0, 2), (2003, 16.0, 2), (2004, 18.0, 1)]


def test_interpolation_uses_legacy_operation_order_for_float_equality():
    prev, nxt = 10.5, 13.25
    out = interpolate_linear([obs("MYS", 2003, nxt), obs("MYS", 2000, prev)])
    slope = (nxt - prev) / 3
    assert [o.value for o in out] == [prev + slope * 1, prev + slope * 2]


def test_interpolation_is_not_bounded_by_any_year_range():
    out = interpolate_linear([obs("MYS", 1995, 0.0), obs("MYS", 2005, 10.0)])
    assert [o.year for o in out] == list(range(1996, 2005))
    out = interpolate_linear([obs("MYS", 2020, 4.0), obs("MYS", 2025, 9.0)])
    assert [o.year for o in out] == [2021, 2022, 2023, 2024]


def test_no_gap_no_output():
    assert interpolate_linear([obs("MYS", 2000, 1.0), obs("MYS", 2001, 2.0)]) == ()
    assert interpolate_linear([obs("MYS", 2010, 42.0)]) == ()


# --- shared behaviour ----------------------------------------------------------


@pytest.mark.parametrize("fn, arg", [(extrapolate_backward, (2000,)), (extrapolate_forward, (2023,)), (interpolate_linear, ())])
def test_empty_input_gives_empty_output(fn, arg):
    assert fn([], *arg) == ()


def test_observed_values_are_never_returned_or_altered():
    series = [obs("MYS", 2003, 7.5), obs("MYS", 2010, 9.5)]
    before = [(ident(o), o.value, dict(o.provenance)) for o in series]
    added = extrapolate_backward(series, 2000) + extrapolate_forward(series, 2023) + interpolate_linear(series)
    assert not ({ident(o) for o in added} & {ident(o) for o in series})
    assert [(ident(o), o.value, dict(o.provenance)) for o in series] == before
    assert all(o.provenance["imputed"] is True for o in added)
    assert all("imputed" not in o.provenance for o in series)


def test_series_are_keyed_by_country_and_dataset_in_first_appearance_order():
    series = [obs("USA", 2022, 50.0), obs("MYS", 2001, 1.0), obs("MYS", 2003, 3.0, dataset="DS_B"), obs("USA", 2020, 40.0)]
    backward = extrapolate_backward(series, 2000)
    assert [ident(o) for o in backward][:3] == [("DS_A", "USA", 2000), ("DS_A", "USA", 2001), ("DS_A", "USA", 2002)]
    assert ("DS_B", "MYS", 2000) in {ident(o) for o in backward}
    assert [o.year for o in interpolate_linear(series) if o.country_code == "USA"] == [2021]


def test_single_observation_is_carried_both_ways():
    series = [obs("MYS", 2010, 42.0, tag="x")]
    b, f = extrapolate_backward(series, 2000), extrapolate_forward(series, 2023)
    assert [o.year for o in b] == list(range(2000, 2010)) and {o.value for o in b} == {42.0}
    assert [o.year for o in f] == list(range(2011, 2024)) and {o.value for o in f} == {42.0}
    assert all(o.provenance["tag"] == "x" for o in b + f)


@pytest.mark.parametrize("fn, arg", [(extrapolate_backward, (2000,)), (extrapolate_forward, (2023,)), (interpolate_linear, ())])
def test_duplicate_identity_is_rejected(fn, arg):
    with pytest.raises(ImputationError, match="duplicate"):
        fn([obs("MYS", 2001, 1.0), obs("MYS", 2001, 2.0)], *arg)


@pytest.mark.parametrize("fn, arg", [(extrapolate_backward, (2000,)), (extrapolate_forward, (2023,)), (interpolate_linear, ())])
def test_results_are_tuples_of_observations(fn, arg):
    out = fn([obs("MYS", 2003, 7.5), obs("MYS", 2006, 9.0)], *arg)
    assert isinstance(out, tuple) and all(isinstance(o, Observation) for o in out)
