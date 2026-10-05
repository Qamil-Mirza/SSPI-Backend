"""GINIPT: formula, goalposts, the two imputation stages on hand-built data,
the situations the legacy route cannot handle, and the registered
definition. No database."""

import pytest

from sspi.errors import ImputationError, ScoreDependencyError
from sspi.imputation import is_imputed
from sspi.indicators import IndicatorDefinition, compute_indicator, registry
from sspi.indicators.ginipt import DEFINITION, LOWER_GOALPOST, REGRESSION_MODEL, UNIT, UPPER_GOALPOST, GiniptImputation, score_ginipt
from sspi.indicators.strategy import fit_centered_least_squares, regression_impute_scores
from sspi.metadata import MetadataCatalog
from sspi.scoring import IndicatorScore, Observation, goalpost


def gini(country, year, value):
    return Observation("WB_GINIPT", country, year, value, "GINI Coeffecient")


def ishrat(country, year, score, **provenance):
    return IndicatorScore("ISHRAT", country, year, score, "ratio", (), (), provenance)


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


# --- formula ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [(70, 0.0), (71.1, 0.0), (20, 1.0), (15, 1.0), (45, 0.5), (40.7, (40.7 - 70) / (20 - 70))])
def test_formula_is_an_inverted_goalpost(value, expected):
    """Lower goalpost 70, upper 20: a lower Gini scores higher; values outside are clamped."""
    assert score_ginipt(value) == expected == goalpost(value, 70, 20)


def test_definition_matches_the_canonical_metadata():
    catalog = MetadataCatalog.load()
    DEFINITION.check_against(catalog)
    indicator = catalog.indicator("GINIPT")
    assert registry.get("GINIPT") is DEFINITION and DEFINITION.dataset_codes == tuple(indicator.dataset_codes) == ("WB_GINIPT",)
    assert DEFINITION.goalposts == (LOWER_GOALPOST, UPPER_GOALPOST) == (indicator.lower_goalpost, indicator.upper_goalpost) == (70, 20)
    assert (indicator.pillar_code, indicator.category_code) == ("MS", "NEQ")
    assert DEFINITION.unit == UNIT == "Coefficient" and isinstance(DEFINITION.imputation, GiniptImputation)
    assert DEFINITION.score_dependencies == ("ISHRAT",) and DEFINITION.auxiliary_datasets == () and DEFINITION.recipient_group is None


# --- stage 1: series fill -----------------------------------------------------------------------


def run(observations, features):
    return compute_indicator(DEFINITION, observations, dependency_scores={"ISHRAT": features})


FEATURES = [ishrat("AAA", 2010, 0.2), ishrat("AAA", 2012, 0.4), ishrat("BBB", 2010, 0.3), ishrat("ZZZ", 2010, 0.5), ishrat("ZZZ", 2024, 0.6)]


def test_series_fill_extrapolates_to_2000_and_2023_and_interpolates_gaps():
    result = run([gini("AAA", 2010, 40.0), gini("AAA", 2012, 30.0), gini("BBB", 2010, 50.0)], FEATURES)
    assert [(s.country_code, s.year) for s in result.observed_scores] == [("AAA", 2010), ("AAA", 2012), ("BBB", 2010)]
    filled = by_identity(s for s in result.imputed_scores if s.inputs)
    assert sorted(y for c, y in filled if c == "AAA") == [*range(2000, 2010), 2011, *range(2013, 2024)]
    assert sorted(y for c, y in filled if c == "BBB") == [*range(2000, 2010), *range(2011, 2024)]
    interpolated, backward, forward = filled[("AAA", 2011)], filled[("AAA", 2000)], filled[("AAA", 2023)]
    assert interpolated.inputs[0].value == 35.0 and interpolated.score == score_ginipt(35.0) and interpolated.inputs[0].provenance["imputation_method"] == "Linear Interpolation"
    assert backward.inputs[0].value == 40.0 and backward.inputs[0].provenance["imputation_method"] == "Backward Extrapolation" and backward.inputs[0].provenance["imputation_distance"] == 10
    assert forward.inputs[0].value == 30.0 and forward.inputs[0].provenance["imputation_method"] == "Forward Extrapolation" and forward.inputs[0].provenance["imputation_distance"] == 11
    assert all(is_imputed(s) and s.provenance == {} and s.unit == UNIT for s in filled.values())


def test_series_fill_is_not_bounded_by_2000_for_interpolation_and_never_overwrites_observations():
    result = run([gini("AAA", 1985, 40.0), gini("AAA", 1990, 50.0), gini("AAA", 2010, 40.0), gini("AAA", 2025, 30.0), gini("BBB", 2010, 50.0)], FEATURES)
    filled = by_identity(s for s in result.imputed_scores if s.inputs)
    years = sorted(y for c, y in filled if c == "AAA")
    assert years == [y for y in range(1986, 2025) if y not in (1990, 2010)]  # pre-2000 gaps interpolated; nothing before 1985 or after the 2025 observation
    assert filled[("AAA", 1987)].inputs[0].value == 44.0
    assert set(filled).isdisjoint({(s.country_code, s.year) for s in result.observed_scores})


# --- stage 2: regression fallback ---------------------------------------------------------------


def test_countries_without_gini_data_are_predicted_from_ishrat_for_every_ishrat_year():
    observations = [gini("AAA", 2010, 40.0), gini("AAA", 2012, 30.0), gini("BBB", 2010, 50.0)]
    result = run(observations, FEATURES)
    predicted = [s for s in result.imputed_scores if not s.inputs]
    assert [(s.country_code, s.year) for s in predicted] == [("ZZZ", 2010), ("ZZZ", 2024)]  # 2024 kept: prediction years are ISHRAT's years
    # training: (AAA 2010: 0.2 -> 0.6), (AAA 2012: 0.4 -> 0.8), (BBB 2010: 0.3 -> 0.4)
    coefficient, intercept = fit_centered_least_squares([0.2, 0.4, 0.3], [0.6, 0.8, 0.4])
    assert coefficient == pytest.approx(1.0) and intercept == pytest.approx(0.3)
    for s in predicted:
        x = s.provenance["feature_score"]
        assert s.score == x * coefficient + intercept and s.unit == UNIT and s.inputs == () and is_imputed(s)
        assert s.provenance["imputation_method"] == "RegressionImputation" and s.provenance["feature_indicator"] == "ISHRAT"
        assert s.provenance["regression_model"] == REGRESSION_MODEL and s.provenance["training_score_count"] == 3
        assert s.provenance["implied_value"] == (20 - 70) * s.score + 70 and s.provenance["goalposts"] == [70, 20]


def test_predictions_are_clipped_to_the_unit_interval():
    features = [ishrat("AAA", 2010, 0.0), ishrat("AAA", 2011, 1.0), ishrat("HIGH", 2010, 5.0), ishrat("LOW", 2010, -5.0)]
    result = run([gini("AAA", 2010, 60.0), gini("AAA", 2011, 30.0)], features)
    predicted = by_identity(s for s in result.imputed_scores if not s.inputs)
    assert predicted[("HIGH", 2010)].score == 1.0 and predicted[("HIGH", 2010)].provenance["raw_prediction"] > 1.0 and predicted[("HIGH", 2010)].provenance["implied_value"] == 20.0
    assert predicted[("LOW", 2010)].score == 0.0 and predicted[("LOW", 2010)].provenance["raw_prediction"] < 0.0 and predicted[("LOW", 2010)].provenance["implied_value"] == 70.0


def test_training_uses_observed_scores_only_and_series_filled_countries_are_not_recipients():
    """A country with any Gini row is covered by the series fill, never by the regression; filled scores do not train."""
    observations = [gini("AAA", 2010, 40.0), gini("AAA", 2012, 30.0), gini("BBB", 2010, 50.0)]
    features = FEATURES + [ishrat("AAA", 2011, 0.9), ishrat("BBB", 2024, 0.1)]  # AAA 2011 is series-filled, BBB 2024 has no GINIPT score at all
    result = run(observations, features)
    predicted = [s for s in result.imputed_scores if not s.inputs]
    assert {s.country_code for s in predicted} == {"ZZZ"} and all(s.provenance["training_score_count"] == 3 for s in predicted)
    assert ("BBB", 2024) not in by_identity(result.scores)


def test_imputed_dependency_scores_are_not_used_as_features():
    features = FEATURES + [ishrat("YYY", 2010, 0.5, imputed=True, imputation_method="x")]
    predicted = [s for s in run([gini("AAA", 2010, 40.0), gini("AAA", 2012, 30.0), gini("BBB", 2010, 50.0)], features).imputed_scores if not s.inputs]
    assert {s.country_code for s in predicted} == {"ZZZ"}  # the legacy route read the observed-score collection


# --- what the legacy route cannot do ------------------------------------------------------------


def test_missing_dependency_scores_stop_the_run_before_anything_is_computed():
    with pytest.raises(ScoreDependencyError, match=r"GINIPT requires existing ISHRAT scores for its legacy imputation procedure and none were found\. Run ISHRAT first"):
        compute_indicator(DEFINITION, [gini("AAA", 2010, 40.0)])
    with pytest.raises(ScoreDependencyError, match="Run ISHRAT first"):
        compute_indicator(DEFINITION, [gini("AAA", 2010, 40.0)], dependency_scores={"ISHRAT": []})
    observed_only = compute_indicator(IndicatorDefinition("GINIPT", score_ginipt, imputation=None, unit=UNIT), [gini("AAA", 2010, 40.0)])
    assert [(s.country_code, s.year, s.score) for s in observed_only.scores] == [("AAA", 2010, 0.6)]


def test_no_observed_scores_and_no_recipients_are_refused_as_the_legacy_route_failed():
    with pytest.raises(ImputationError, match="no observed GINIPT scores"):
        run([], FEATURES)
    with pytest.raises(ImputationError, match="nothing to predict"):
        run([gini("AAA", 2010, 40.0), gini("BBB", 2010, 50.0), gini("ZZZ", 2015, 45.0)], FEATURES)
    with pytest.raises(ImputationError, match="no \\(country, year\\) has both"):
        run([gini("QQQ", 2010, 40.0)], FEATURES)  # recipients exist but nothing to train on


# --- the regression primitive -------------------------------------------------------------------


def test_regression_primitive_validates_its_inputs():
    target = [IndicatorScore("T", "AAA", 2010, 0.5, "u", ()), IndicatorScore("T", "BBB", 2010, 0.7, "u", ())]
    feature = [ishrat("AAA", 2010, 0.2), ishrat("BBB", 2010, 0.4), ishrat("CCC", 2010, 0.3)]
    kwargs = {"goalposts": (0, 1), "model": "T ~ ISHRAT"}
    (predicted,) = regression_impute_scores("T", "u", feature, target, feature[2:], **kwargs)
    assert predicted.score == pytest.approx(0.6) and predicted.indicator_code == "T" and "imputation_details" not in predicted.provenance
    with pytest.raises(ImputationError, match="already have observed scores"):
        regression_impute_scores("T", "u", feature, target, feature[:1], **kwargs)
    with pytest.raises(ImputationError, match="exactly one feature indicator"):
        regression_impute_scores("T", "u", feature + [IndicatorScore("OTHER", "DDD", 2010, 0.1, "u", ())], target, feature[2:], **kwargs)
    with pytest.raises(ImputationError, match="duplicate feature score identity"):
        regression_impute_scores("T", "u", feature + [ishrat("AAA", 2010, 0.9)], target, feature[2:], **kwargs)
    # a missing score is dropped, as the legacy pivot dropped it
    (again,) = regression_impute_scores("T", "u", feature + [ishrat("EEE", 2010, None)], target + [IndicatorScore("T", "EEE", 2010, 0.1, "u", ())], feature[2:], **kwargs)
    assert again.score == predicted.score and again.provenance["training_score_count"] == 2


def test_fit_needs_matching_non_empty_inputs():
    with pytest.raises(ImputationError):
        fit_centered_least_squares([], [])
    with pytest.raises(ImputationError):
        fit_centered_least_squares([0.1, 0.2], [0.3])
