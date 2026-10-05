"""``SeriesFillThenScore`` and the two indicators that use it (EMPLOY,
COLBAR): formulas, units, which years are filled and for whom. Pure, no
database."""

import pytest

from sspi.imputation import is_imputed
from sspi.indicators import IndicatorDefinition, colbar, compute_indicator, employ, registry
from sspi.indicators.strategy import ImputationStrategy, SeriesFillThenScore
from sspi.scoring import Observation, goalpost


def obs(country, year, value, dataset="ILO_COLBAR", unit="Proportion"):
    return Observation(dataset, country, year, value, unit)


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


def test_formulas_and_goalposts():
    assert employ.score_employ(72.5) == goalpost(72.5, 50, 95) == 0.5
    assert employ.score_employ(40) == 0.0 and employ.score_employ(99) == 1.0
    assert colbar.score_colbar(98.0) == 0.98 and colbar.score_colbar(0.4) == 0.004 and colbar.score_colbar(120) == 1.0
    assert registry.get("EMPLOY").goalposts == (50, 95) and registry.get("COLBAR").goalposts == (0, 100)
    assert registry.get("EMPLOY").dataset_codes == ("ILO_EMPLOY_TO_POP",) and registry.get("COLBAR").dataset_codes == ("ILO_COLBAR",)


def test_strategy_declares_no_group_no_auxiliary_data_and_no_score_dependency():
    for code in ("EMPLOY", "COLBAR"):
        definition = registry.get(code)
        assert isinstance(definition.imputation, ImputationStrategy) and isinstance(definition.imputation, SeriesFillThenScore)
        assert definition.recipient_group is None and definition.auxiliary_datasets == () and definition.score_dependencies == ()
        assert definition.imputation.years == (2000, 2023) and definition.imputation.formula is definition.observed_score


def test_series_is_carried_backward_to_2000_forward_to_2023_and_interpolated():
    result = compute_indicator(registry.get("COLBAR"), [obs("MYS", 2002, 10.0), obs("MYS", 2005, 40.0), obs("MYS", 2020, 50.0)])
    scores = by_identity(result.scores)
    assert sorted(y for _, y in scores) == list(range(2000, 2024))
    assert [y for (_, y), s in sorted(scores.items()) if not is_imputed(s)] == [2002, 2005, 2020]
    assert scores[("MYS", 2000)].score == scores[("MYS", 2001)].score == 0.10  # backward: the earliest value
    assert scores[("MYS", 2003)].score == pytest.approx(0.20) and scores[("MYS", 2004)].score == pytest.approx(0.30)  # linear
    assert scores[("MYS", 2021)].score == scores[("MYS", 2023)].score == 0.50  # forward: the latest value
    methods = {y: s.inputs[0].provenance["imputation_method"] for (_, y), s in scores.items() if is_imputed(s)}
    assert methods[2000] == "Backward Extrapolation" and methods[2003] == "Linear Interpolation" and methods[2023] == "Forward Extrapolation"
    assert scores[("MYS", 2023)].inputs[0].provenance["imputation_distance"] == 3 and scores[("MYS", 2000)].inputs[0].provenance["imputation_distance"] == 2
    assert all(s.provenance == {} for s in result.scores)  # the score is ordinary; its input is what was imputed


def test_observed_and_imputed_scores_carry_the_two_legacy_unit_literals():
    colbar_run = compute_indicator(registry.get("COLBAR"), [obs("MYS", 2010, 10.0)])
    employ_run = compute_indicator(registry.get("EMPLOY"), [obs("MYS", 2010, 60.0, "ILO_EMPLOY_TO_POP", "Rate")])
    assert {s.unit for s in colbar_run.observed_scores} == {"%"} and {s.unit for s in employ_run.observed_scores} == {"Percentage"}
    assert {s.unit for s in colbar_run.imputed_scores} == {s.unit for s in employ_run.imputed_scores} == {"Tax Rate"}
    assert {s.inputs[0].unit for s in colbar_run.imputed_scores} == {"Proportion"}  # inputs keep the dataset's unit


def test_without_a_unit_override_the_strategy_uses_the_definition_unit():
    definition = IndicatorDefinition("COLBAR", colbar.score_colbar, imputation=SeriesFillThenScore(colbar.score_colbar, (2000, 2023)), unit="%")
    run = compute_indicator(definition, [obs("MYS", 2010, 10.0)])
    assert {s.unit for s in run.scores} == {"%"} and len(run.imputed_scores) == 23


def test_years_outside_the_window_are_scored_when_observed_and_only_interpolated_otherwise():
    rows = [obs("AUT", 1995, 90.0), obs("AUT", 1997, 92.0), obs("AUT", 2023, 98.0), obs("AUT", 2025, 96.0)]
    result = compute_indicator(registry.get("COLBAR"), rows)
    scores = by_identity(result.scores)
    assert {1995, 1997, 2023, 2025} <= {y for _, y in scores} and not is_imputed(scores[("AUT", 2025)])  # no year filter on observed scores
    assert is_imputed(scores[("AUT", 1996)]) and is_imputed(scores[("AUT", 2024)])  # interior gaps are filled whatever the year
    assert ("AUT", 1994) not in scores and ("AUT", 2026) not in scores  # the series already reaches past both targets: nothing is carried
    assert scores[("AUT", 2024)].score == pytest.approx(0.97)


def test_each_area_is_filled_on_its_own_and_an_area_with_no_observation_gets_nothing():
    result = compute_indicator(registry.get("COLBAR"), [obs("MYS", 2010, 10.0), obs("KOS", 2015, 30.0)])
    scores = by_identity(result.scores)
    assert {c for c, _ in scores} == {"MYS", "KOS"} and len(scores) == 48  # no country group: any area code in the dataset is treated
    assert all(scores[("MYS", y)].score == 0.10 and scores[("KOS", y)].score == 0.30 for y in range(2000, 2024))
    assert compute_indicator(registry.get("COLBAR"), []).scores == ()  # nothing observed: nothing scored, nothing raised


def test_results_do_not_depend_on_input_order():
    rows = [obs("MYS", 2002, 10.0), obs("MYS", 2005, 40.0), obs("AUT", 2010, 98.0)]
    forward, backward = compute_indicator(registry.get("COLBAR"), rows), compute_indicator(registry.get("COLBAR"), rows[::-1])
    assert by_identity(forward.scores) == by_identity(backward.scores)
