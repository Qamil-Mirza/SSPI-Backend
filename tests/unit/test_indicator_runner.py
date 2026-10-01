"""compute_indicator: the pure orchestration of observed scoring, imputation
and imputed scoring for one indicator definition, no database involved."""

import pytest

from sspi.errors import InvalidObservationError
from sspi.imputation import BACKWARD_EXTRAPOLATION, FORWARD_EXTRAPOLATION, LINEAR_INTERPOLATION, REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import IndicatorDefinition, IndicatorRun, compute_indicator, registry
from sspi.indicators.biodiv import score_biodiv_imputed, score_biodiv_observed
from sspi.indicators.strategy import ImputeInputsThenScore
from sspi.scoring import Observation, UnscoredReason

BIODIV = registry.get("BIODIV")
CODES = ("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT")


def obs(dataset, country, year, value, **prov):
    return Observation(dataset, country, year, value, "PERCENT", prov)


def full(country, years, values=(60.0, 30.0, 90.0)):
    return [obs(code, country, y, v) for y in years for code, v in zip(CODES, values)]


def methods(score):
    return {o.dataset_code: o.provenance.get("imputation_method") for o in score.inputs if o.provenance.get("imputed")}


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


def test_result_shape():
    result = compute_indicator(BIODIV, full("MYS", range(2000, 2024)), recipients=[])
    assert isinstance(result, IndicatorRun)
    assert result.indicator_code == "BIODIV"
    assert result.written is None
    assert len(result.observed_scores) == 24 and result.imputed_scores == () and result.unscored == ()
    assert result.scores == result.observed_scores + result.imputed_scores


def test_all_three_observed_gives_an_observed_score_with_the_compute_formula():
    result = compute_indicator(BIODIV, full("MYS", [2020]), recipients=["MYS"])
    (score,) = result.observed_scores
    assert score.score == score_biodiv_observed(60.0, 30.0, 90.0) == (0.9 + 0.3 + 0.6) / 3
    assert score.unit == "Index" and score.indicator_code == "BIODIV"
    assert not is_imputed(score)


def test_reference_class_input_gives_an_imputed_score():
    observations = full("MYS", [2020]) + [obs("UNSDG_TERRST", "AUT", 2020, 50.0), obs("UNSDG_FRSHWT", "AUT", 2020, 70.0)]
    result = compute_indicator(BIODIV, observations, recipients=["AUT", "MYS"])
    imputed = by_identity(result.imputed_scores)
    assert (("AUT", 2020) in imputed) and ("MYS", 2020) not in imputed
    assert methods(imputed[("AUT", 2020)]) == {"UNSDG_MARINE": REFERENCE_CLASS_AVERAGE}
    assert imputed[("AUT", 2020)].score == score_biodiv_imputed(60.0, 50.0, 70.0)
    # AUT gets reference rows for every imputation year, and terrst/frshwt extrapolated to match
    assert sorted(y for c, y in imputed if c == "AUT") == list(range(2000, 2024))


def test_interpolation_input_gives_an_imputed_score():
    observations = full("MYS", [2019, 2021]) + [obs("UNSDG_TERRST", "MYS", 2020, 30.0), obs("UNSDG_FRSHWT", "MYS", 2020, 90.0)]
    result = compute_indicator(BIODIV, observations, recipients=["MYS"])
    imputed = by_identity(result.imputed_scores)
    assert methods(imputed[("MYS", 2020)]) == {"UNSDG_MARINE": LINEAR_INTERPOLATION}
    assert sorted(by_identity(result.observed_scores)) == [("MYS", 2019), ("MYS", 2021)]


def test_extrapolation_inputs_give_imputed_scores():
    observations = full("MYS", [2010, 2011])
    result = compute_indicator(BIODIV, observations, recipients=[])
    imputed = by_identity(result.imputed_scores)
    assert methods(imputed[("MYS", 2000)]) == dict.fromkeys(CODES, BACKWARD_EXTRAPOLATION)
    assert methods(imputed[("MYS", 2023)]) == dict.fromkeys(CODES, FORWARD_EXTRAPOLATION)
    assert sorted(y for _, y in imputed) == [y for y in range(2000, 2024) if y not in (2010, 2011)]


def test_group_still_incomplete_after_imputation_is_unscored():
    # ALB is not a recipient: marine only, nothing fills the other two.
    observations = full("MYS", [2020]) + [obs("UNSDG_MARINE", "ALB", 2020, 5.0)]
    result = compute_indicator(BIODIV, observations, recipients=["MYS"])
    unscored = {(u.country_code, u.year): u for u in result.unscored}
    assert (unscored[("ALB", 2020)].reason, unscored[("ALB", 2020)].details) == (UnscoredReason.MISSING_DATASETS, ("UNSDG_TERRST", "UNSDG_FRSHWT"))
    # ALB's marine row is extrapolated across 2000-2023, and every one of those years stays unscorable
    assert sorted(unscored) == [("ALB", y) for y in range(2000, 2024)]
    assert not any(u.country_code == "MYS" for u in result.unscored)


def test_incomplete_groups_created_by_extrapolation_are_reported_once_each():
    observations = [obs("UNSDG_MARINE", "ALB", 2020, 5.0)]
    result = compute_indicator(BIODIV, observations, recipients=[])
    assert sorted((u.country_code, u.year) for u in result.unscored) == [("ALB", y) for y in range(2000, 2024)]
    assert result.observed_scores == () and result.imputed_scores == ()


def test_observed_and_imputed_sets_are_complementary_and_classified_by_inputs():
    observations = full("MYS", [2000, 2001, 2003]) + full("USA", range(2000, 2024))
    result = compute_indicator(BIODIV, observations, recipients=["MYS", "USA", "AUT"])
    observed, imputed = by_identity(result.observed_scores), by_identity(result.imputed_scores)
    assert set(observed).isdisjoint(imputed)
    assert all(not is_imputed(s) for s in observed.values())
    assert all(is_imputed(s) for s in imputed.values())
    assert set(observed) == {("MYS", 2000), ("MYS", 2001), ("MYS", 2003)} | {("USA", y) for y in range(2000, 2024)}
    assert set(imputed) == {("MYS", y) for y in range(2000, 2024) if y not in (2000, 2001, 2003)} | {("AUT", y) for y in range(2000, 2024)}


def test_observed_path_has_no_year_filter_but_imputation_is_bounded():
    result = compute_indicator(BIODIV, full("MYS", [1999, 2025]), recipients=["MYS"])
    assert sorted(y for _, y in by_identity(result.observed_scores)) == [1999, 2025]
    # interior gap 2000..2024 is interpolated (unbounded); nothing outside 1999..2025 is added
    assert sorted(y for _, y in by_identity(result.imputed_scores)) == list(range(2000, 2025))


def test_results_are_deterministic_regardless_of_input_order():
    observations = full("MYS", [2000, 2005]) + [obs("UNSDG_TERRST", "AUT", 2010, 1.0), obs("UNSDG_FRSHWT", "AUT", 2010, 2.0)]
    a = compute_indicator(BIODIV, observations, recipients=["USA", "AUT"])
    b = compute_indicator(BIODIV, list(reversed(observations)), recipients=["AUT", "USA"])
    assert by_identity(a.observed_scores) == by_identity(b.observed_scores)
    assert by_identity(a.imputed_scores) == by_identity(b.imputed_scores)
    assert {(u.country_code, u.year) for u in a.unscored} == {(u.country_code, u.year) for u in b.unscored}


def test_imputed_path_orders_inputs_in_metadata_dependency_order():
    result = compute_indicator(BIODIV, full("MYS", [2010, 2011]), recipients=[])
    score = by_identity(result.imputed_scores)[("MYS", 2000)]
    assert [o.dataset_code for o in score.inputs] == list(CODES)


def test_observations_for_datasets_the_indicator_does_not_consume_are_rejected():
    with pytest.raises(InvalidObservationError, match="WB_POPULN"):
        compute_indicator(BIODIV, full("MYS", [2020]) + [obs("WB_POPULN", "MYS", 2020, 1.0)], recipients=[])


def test_imputed_observations_must_not_enter_the_observed_path():
    leaked = [obs("UNSDG_MARINE", "MYS", 2020, 1.0, imputed=True, imputation_method="x")]
    with pytest.raises(InvalidObservationError, match="imputed"):
        compute_indicator(BIODIV, full("MYS", [2019]) + leaked, recipients=[])


def test_recipients_only_affect_the_reference_class():
    # KEN has no rows and is not a recipient: no reference rows, no scores; USA is a recipient with full data: nothing added.
    result = compute_indicator(BIODIV, full("USA", range(2000, 2024)), recipients=["USA"])
    assert result.imputed_scores == () and len(result.observed_scores) == 24


def test_a_definition_with_one_formula_for_both_paths_works():
    def f(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        return 0.25

    definition = IndicatorDefinition("BIODIV", f, imputation=ImputeInputsThenScore(f, (2019, 2021), "SSPI67"))
    result = compute_indicator(definition, full("MYS", [2020]), recipients=["AUT"])
    assert {s.score for s in result.scores} == {0.25}
    assert sorted(y for c, y in by_identity(result.imputed_scores) if c == "AUT") == [2019, 2020, 2021]


def test_strategy_results_are_checked_by_the_runner():
    from sspi.indicators.strategy import IndicatorImputationResult
    from sspi.scoring import IndicatorScore

    def f(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        return 0.25

    class ReturnsObservedLooking:
        auxiliary_datasets = ()
        recipient_group = None

        def impute(self, context):
            fake = IndicatorScore("BIODIV", "AUT", 2020, 0.5, "Index", context.observations[:3])  # no imputed input, no provenance
            return IndicatorImputationResult((fake,), ())

    class CollidesWithObserved:
        auxiliary_datasets = ()
        recipient_group = None

        def impute(self, context):
            dup = IndicatorScore("BIODIV", "MYS", 2020, 0.5, "Index", (), (), {"imputed": True, "imputation_method": "x"})
            return IndicatorImputationResult((dup,), ())

    with pytest.raises(InvalidObservationError, match="do not classify as imputed"):
        compute_indicator(IndicatorDefinition("BIODIV", f, imputation=ReturnsObservedLooking()), full("MYS", [2020]))
    with pytest.raises(InvalidObservationError, match="already scored"):
        compute_indicator(IndicatorDefinition("BIODIV", f, imputation=CollidesWithObserved()), full("MYS", [2020]))


def test_strategy_receives_only_declared_auxiliary_rows_and_recipients_only_when_asked():
    from sspi.indicators.strategy import IndicatorImputationResult

    seen = {}

    def f(UNSDG_MARINE, UNSDG_TERRST, UNSDG_FRSHWT):
        return 0.25

    class Recording:
        auxiliary_datasets = ("UNSDG_REDLST",)
        recipient_group = None

        def impute(self, context):
            seen["auxiliary"] = {k: len(v) for k, v in context.auxiliary.items()}
            seen["recipients"] = context.recipients
            seen["observed"] = len(context.observed_scores)
            return IndicatorImputationResult((), ())

    definition = IndicatorDefinition("BIODIV", f, imputation=Recording())
    aux = [obs("UNSDG_REDLST", "MYS", 2020, 0.9)]
    result = compute_indicator(definition, full("MYS", [2020]), recipients=["AUT"], auxiliary=aux)
    assert seen == {"auxiliary": {"UNSDG_REDLST": 1}, "recipients": (), "observed": 1} and result.imputed_scores == ()
    with pytest.raises(InvalidObservationError, match="auxiliary observations for datasets"):
        compute_indicator(definition, full("MYS", [2020]), auxiliary=[obs("UNSDG_WTSTRS", "MYS", 2020, 1.0)])


def test_run_indicator_rejects_unknown_codes_before_touching_the_database():
    from sspi.errors import UnknownCodeError
    from sspi.indicators import run_indicator

    with pytest.raises(UnknownCodeError, match="no executable definition"):
        run_indicator("NITROG", database=None)
