"""CARBON: formula, compute-route filter, the input-level imputation strategy
and the refusal on recipients that already have observed scores. No
database, no network."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.carbon import DEFINITION, IMPUTATION_YEARS, REFERENCE_CLASS_RECIPIENTS, CarbonImputation, keep_for_scoring, score_carbon
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation


def level(country, year, value):
    return Observation("UNFAO_CRBNLV", country, year, value, "million t")


def average(country, year, value, years=range(1990, 2026)):
    return Observation("UNFAO_CRBNAV", country, year, value, "millions of kilograms (1990s Average)")


def series(country, levels, baseline, years=range(1990, 2026)):
    return [level(country, y, v) for y, v in levels.items()] + [average(country, y, baseline) for y in years]


@pytest.mark.parametrize("lv, av, expected", [(100.0, 100.0, 5 / 55), (150.0, 100.0, 1.0), (94.0, 100.0, 0.0), (120.0, 100.0, 25 / 55), (3.0, 0.0, 0)])
def test_formula_is_percent_change_goalposted_with_zero_guard(lv, av, expected):
    assert score_carbon(lv, av) == expected


def test_compute_filter_keeps_level_rows_from_2000_and_every_average_row():
    assert not keep_for_scoring(level("AAA", 1999, 1.0)) and keep_for_scoring(level("AAA", 2000, 1.0)) and keep_for_scoring(average("AAA", 1990, 1.0))


def test_definition_is_registered_and_consistent_with_metadata():
    assert registry.get("CARBON") is DEFINITION
    assert DEFINITION.dataset_codes == ("UNFAO_CRBNLV", "UNFAO_CRBNAV") and DEFINITION.goalposts == (-5, 50)
    assert isinstance(DEFINITION.imputation, CarbonImputation) and DEFINITION.auxiliary_datasets == () and DEFINITION.recipient_group is None
    DEFINITION.check_against(MetadataCatalog.load())


def test_observed_scores_follow_the_source_years_including_after_2022():
    rows = series("AAA", {1995: 90.0, 2000: 100.0, 2025: 130.0}, 100.0)
    run = compute_indicator(DEFINITION, rows)
    assert {(s.year, s.score) for s in run.observed_scores} == {(2000, score_carbon(100.0, 100.0)), (2025, score_carbon(130.0, 100.0))}


def test_strategy_imputes_both_inputs_for_the_three_recipients_from_every_row():
    rows = series("AAA", {1990: 10.0, 2000: 20.0}, 10.0) + series("ZZZ", {1990: 30.0, 2000: 40.0}, 30.0)
    rows += [level("BEL", y, 1000.0) for y in (2000, 2001)]  # level rows but no 1990s mean: no observed score, rows still enter the mean
    run = compute_indicator(DEFINITION, rows)
    level_mean = sum(o.value for o in rows if o.dataset_code == "UNFAO_CRBNLV") / 6
    average_mean = sum(o.value for o in rows if o.dataset_code == "UNFAO_CRBNAV") / 72
    imputed = {(s.country_code, s.year): s for s in run.imputed_scores}
    assert {c for c, _ in imputed} == set(REFERENCE_CLASS_RECIPIENTS) and {y for _, y in imputed} == set(range(IMPUTATION_YEARS[0], IMPUTATION_YEARS[1] + 1))
    for s in imputed.values():
        by_code = {o.dataset_code: o for o in s.inputs}
        assert by_code["UNFAO_CRBNLV"].value == level_mean and by_code["UNFAO_CRBNAV"].value == average_mean
        assert by_code["UNFAO_CRBNLV"].provenance["reference_observation_count"] == 6 and by_code["UNFAO_CRBNAV"].provenance["reference_observation_count"] == 72
        assert s.score == score_carbon(level_mean, average_mean) and is_imputed(s) and not s.provenance
    assert ("BEL", 2000) not in {(u.country_code, u.year) for u in run.unscored}  # filled by imputation
    assert {(s.country_code, s.year) for s in run.observed_scores}.isdisjoint(imputed)


def test_recipient_with_observed_scores_is_refused_naming_the_conflict():
    """Pending methodology decision (CARBON-1): no precedence rule exists, so the strategy stops rather than skipping or keeping
    the imputation. The WATMAN-3 canonical-first policy is NOT generalized here."""
    rows = series("AAA", {1990: 10.0, 2000: 20.0}, 10.0) + series("KWT", {1990: 0.1, 2000: 0.2}, 0.1)
    with pytest.raises(ImputationError, match=r"\['KWT'\].*CARBON-1") as info:
        compute_indicator(DEFINITION, rows)
    message = str(info.value)
    assert "source data has changed" in message and "hard-coded" in message and "No precedence" in message and "Methodology review is required" in message


def test_no_extrapolation_happens():
    rows = series("AAA", {1990: 10.0, 2000: 20.0, 2010: 21.0}, 10.0)
    run = compute_indicator(DEFINITION, rows)
    assert {s.country_code for s in run.imputed_scores} == set(REFERENCE_CLASS_RECIPIENTS)  # AAA's 2011-2023 gap stays unscored
    assert {(u.country_code, u.year) for u in run.unscored} >= {("AAA", y) for y in range(2011, 2024)}
