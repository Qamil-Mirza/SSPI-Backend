"""impute_dataset: recipient selection and the legacy operation order,
reference class -> backward -> forward -> interpolation, on one dataset."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import (
    BACKWARD_EXTRAPOLATION,
    FORWARD_EXTRAPOLATION,
    LINEAR_INTERPOLATION,
    REFERENCE_CLASS_AVERAGE,
    ImputationResult,
    impute_dataset,
    missing_countries,
)
from sspi.scoring import Observation


def obs(country, year, value, dataset="DS_A", unit="PERCENT", **prov):
    return Observation(dataset, country, year, value, unit, prov)


# --- recipients ---------------------------------------------------------------


def test_missing_countries_is_recipients_minus_any_represented_country_sorted():
    observations = [obs("MYS", 2025, 1.0), obs("USA", 2000, 2.0)]  # a single 2025 row makes MYS represented
    assert missing_countries(["USA", "CHE", "AUT", "MYS"], observations) == ("AUT", "CHE")
    assert missing_countries([], observations) == ()
    assert missing_countries(["ZZZ"], []) == ("ZZZ",)


def test_duplicate_recipients_collapse():
    assert missing_countries(["AUT", "AUT"], []) == ("AUT",)


# --- composition --------------------------------------------------------------


def test_result_shape_observed_untouched_imputed_in_legacy_order():
    observed = [obs("MYS", 2003, 10.0, s="m"), obs("MYS", 2005, 20.0), obs("MYS", 2010, 30.0), obs("USA", 2000, 5.0)]
    result = impute_dataset(observed, "DS_A", recipients=["AUT", "MYS", "USA"], start_year=2000, end_year=2012)
    assert isinstance(result, ImputationResult)
    assert result.observed == tuple(observed)
    methods = [o.provenance["imputation_method"] for o in result.imputed]
    # reference rows, then backward, then forward, then interpolation
    assert methods == [REFERENCE_CLASS_AVERAGE] * 13 + [BACKWARD_EXTRAPOLATION] * 3 + [FORWARD_EXTRAPOLATION] * 14 + [LINEAR_INTERPOLATION] * 5
    assert [o.country_code for o in result.imputed[:13]] == ["AUT"] * 13
    assert result.combined == result.observed + result.imputed
    assert len(result.combined) == len(observed) + 13 + 3 + 14 + 5


def test_reference_mean_uses_observed_rows_only_not_extrapolated_ones():
    observed = [obs("MYS", 2003, 10.0), obs("USA", 2010, 30.0)]
    result = impute_dataset(observed, "DS_A", ["AUT"], 2000, 2023)
    aut = [o for o in result.imputed if o.country_code == "AUT"]
    assert {o.value for o in aut} == {20.0}
    assert aut[0].provenance["reference_observation_count"] == 2


def test_forward_and_interpolation_see_the_running_combined_list():
    # Same outcome as legacy chaining: backward rows are contiguous with the first year,
    # so later steps neither re-fill nor re-anchor on them.
    observed = [obs("MYS", 2002, 4.0), obs("MYS", 2004, 6.0)]
    result = impute_dataset(observed, "DS_A", [], 2000, 2006)
    assert [(o.year, o.value, o.provenance["imputation_method"]) for o in result.imputed] == [
        (2000, 4.0, BACKWARD_EXTRAPOLATION),
        (2001, 4.0, BACKWARD_EXTRAPOLATION),
        (2005, 6.0, FORWARD_EXTRAPOLATION),
        (2006, 6.0, FORWARD_EXTRAPOLATION),
        (2003, 5.0, LINEAR_INTERPOLATION),
    ]


def test_no_identity_is_produced_twice_and_observed_never_overwritten():
    observed = [obs("MYS", 2001, 1.0), obs("MYS", 2003, 3.0), obs("MYS", 2025, 9.0)]
    result = impute_dataset(observed, "DS_A", ["MYS", "AUT"], 2000, 2023)
    identities = [(o.country_code, o.year) for o in result.combined]
    assert len(identities) == len(set(identities))
    assert {(o.country_code, o.year) for o in result.observed} <= set(identities)
    assert all("imputed" not in o.provenance for o in result.observed)
    assert all(o.provenance["imputed"] is True for o in result.imputed)


def test_observed_rows_outside_the_range_pass_through_and_bound_nothing():
    observed = [obs("MYS", 1998, 1.0), obs("MYS", 2024, 9.0)]
    result = impute_dataset(observed, "DS_A", [], 2000, 2023)
    years = sorted(o.year for o in result.imputed)
    assert years == list(range(1999, 2024))  # interpolation fills 1999..2023, no extrapolation at all
    assert {o.provenance["imputation_method"] for o in result.imputed} == {LINEAR_INTERPOLATION}


def test_represented_recipient_gets_no_reference_rows():
    observed = [obs("MYS", 2020, 1.0)]
    result = impute_dataset(observed, "DS_A", ["MYS"], 2000, 2023)
    assert {o.provenance["imputation_method"] for o in result.imputed} == {BACKWARD_EXTRAPOLATION, FORWARD_EXTRAPOLATION}


def test_empty_dataset_with_recipients_is_an_error_as_in_legacy():
    with pytest.raises(ImputationError, match="empty"):
        impute_dataset([], "DS_A", ["AUT"], 2000, 2023)
    assert impute_dataset([], "DS_A", [], 2000, 2023) == ImputationResult((), ())


def test_observations_must_all_belong_to_the_named_dataset():
    with pytest.raises(ImputationError, match="DS_B"):
        impute_dataset([obs("MYS", 2000, 1.0, dataset="DS_B")], "DS_A", [], 2000, 2023)


def test_recipient_order_is_deterministic_regardless_of_input_order():
    observed = [obs("MYS", 2000, 1.0)]
    a = impute_dataset(observed, "DS_A", ["USA", "AUT"], 2000, 2001)
    b = impute_dataset(observed, "DS_A", ["AUT", "USA"], 2000, 2001)
    assert a == b
    # two reference rows per recipient, then MYS's own forward fill for 2001
    assert [o.country_code for o in a.imputed] == ["AUT", "AUT", "USA", "USA", "MYS"]
