"""A score is imputed iff any input observation carries a truthy ``imputed``
provenance flag: the legacy ``filter_imputations`` rule, as one pure function."""

from sspi.imputation import is_imputed
from sspi.scoring import ComputedValue, IndicatorScore, Observation


def obs(code, **prov):
    return Observation(code, "MYS", 2020, 1.0, "PERCENT", prov)


def score(*inputs, computed=()):
    return IndicatorScore("BIODIV", "MYS", 2020, 0.5, "Index", tuple(inputs), tuple(computed))


def test_all_observed_inputs_is_not_imputed():
    assert is_imputed(score(obs("A"), obs("B", source="x"))) is False


def test_one_imputed_input_makes_the_score_imputed():
    assert is_imputed(score(obs("A"), obs("B", imputed=True, imputation_method="Linear Interpolation"))) is True


def test_truthiness_matches_the_legacy_filter():
    assert is_imputed(score(obs("A", imputed=1))) is True
    assert is_imputed(score(obs("A", imputed=False))) is False
    assert is_imputed(score(obs("A", imputed=0))) is False
    assert is_imputed(score(obs("A", imputed=None))) is False


def test_no_inputs_is_not_imputed():
    assert is_imputed(score()) is False


def test_computed_values_carry_no_flag_and_do_not_count():
    assert is_imputed(score(obs("A"), computed=[ComputedValue("C", 1.0, "u")])) is False


def test_accepts_a_plain_sequence_of_observations_too():
    assert is_imputed([obs("A"), obs("B", imputed=True)]) is True
    assert is_imputed(()) is False
