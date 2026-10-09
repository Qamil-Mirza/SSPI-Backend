"""BEEFMK, COALPW and GTRANS: formulas, goalposts, definitions, and the
strategy behaviour each relies on (``ExtrapolateScores`` with a hard-coded
recipient list, ``ConstantFillInputsThenScore`` with COALPW's zero-total
rule, ``ExtrapolateInputsForwardThenScore``). Pure, no database."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import is_imputed
from sspi.indicators import beefmk, coalpw, compute_indicator, gtrans, registry
from sspi.indicators.strategy import ConstantFillInputsThenScore, ExtrapolateInputsForwardThenScore, ExtrapolateScores, ImputationStrategy
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation, goalpost

TES = ("IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL")


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


def test_definitions_agree_with_canonical_metadata():
    catalog = MetadataCatalog.load()
    for code in ("BEEFMK", "COALPW", "GTRANS"):
        definition = registry.get(code)
        definition.check_against(catalog)
        assert (catalog.indicator(code).pillar_code, catalog.indicator(code).category_code) == ("SUS", "GHG")
        assert definition.unit == "Index" and isinstance(definition.imputation, ImputationStrategy) and definition.score_dependencies == () and definition.auxiliary_datasets == ()
    assert registry.get("COALPW").dataset_codes == TES == registry.get("ALTNRG").dataset_codes


# --- COALPW -------------------------------------------------------------------------------------


def test_coalpw_scores_the_coal_fraction_of_the_seven_product_total_less_is_better():
    assert coalpw.score_coalpw_observed(200, 300, 100, 100, 100, 100, 100) == goalpost(0.2, 0.4, 0) == 0.5
    assert coalpw.score_coalpw_observed(400, 600, 0.0, 0.0, 0.0, 0.0, 0.0) == 0.0  # 40 % coal or more scores 0
    assert coalpw.score_coalpw_observed(1, 999999, 0.0, 0.0, 0.0, 0.0, 0.0) == goalpost(1 / 1000000, 0.4, 0)
    assert registry.get("COALPW").goalposts == (0.4, 0)
    assert coalpw.score_coalpw_imputed(200, 300, 100, 100, 100, 100, 100) == 0.5


def test_coalpw_zero_total_is_one_in_the_impute_route_unlike_altnrg():
    assert coalpw.score_coalpw_imputed(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) == 1.0
    assert registry.get("ALTNRG").imputation.formula(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) == 0.0


def test_coalpw_strategy_is_altnrgs_with_its_own_formula():
    strategy, altnrg = registry.get("COALPW").imputation, registry.get("ALTNRG").imputation
    assert isinstance(strategy, ConstantFillInputsThenScore) and strategy.formula is coalpw.score_coalpw_imputed
    assert (strategy.years, strategy.recipient_group, strategy.fill_value, strategy.fill_unit, strategy.fill_method) == (altnrg.years, altnrg.recipient_group, altnrg.fill_value, altnrg.fill_unit, altnrg.fill_method)


def test_a_country_without_coal_is_scored_only_by_imputation_and_scores_one():
    rows = [Observation(code, "AAA", 2010, 100.0, "TJ") for code in TES[1:]]  # every fuel but coal: the cleaner dropped the zeros
    run = compute_indicator(registry.get("COALPW"), rows, ("AAA",))
    assert run.observed_scores == ()
    scores = by_identity(run.imputed_scores)
    assert set(scores) == {("AAA", y) for y in range(2000, 2024)} and all(s.score == 1.0 and is_imputed(s) for s in scores.values())
    coal = next(o for o in scores[("AAA", 2010)].inputs if o.dataset_code == "IEA_TLCOAL")
    assert (coal.value, coal.unit, coal.provenance["imputation_method"]) == (0.0, "PJ", "Zero imputation for missing energy type")


# --- GTRANS -------------------------------------------------------------------------------------


def test_gtrans_scores_kilograms_per_person_against_seven_thousand():
    assert gtrans.score_gtrans(3.5e9, 1e6) == goalpost(3500.0, 7000, 0) == 0.5
    assert gtrans.score_gtrans(8e9, 1e6) == 0.0 and gtrans.score_gtrans(1.0, 1e6) == goalpost(1e-6, 7000, 0)
    assert registry.get("GTRANS").goalposts == (7000, 0) and registry.get("GTRANS").dataset_codes == ("IEA_TCO2EM", "WB_POPULN")


def co2(country, year, value):
    return Observation("IEA_TCO2EM", country, year, value, "Tonnes C02 per inhabitant")


def population(country, year, value):
    return Observation("WB_POPULN", country, year, value, "Population")


def test_gtrans_carries_only_the_co2_input_forward_within_the_window():
    rows = [co2("AAA", y, 7e9) for y in (1995, 2005, 2018)] + [population("AAA", y, 1e6 * (y - 1990)) for y in range(1990, 2026)]
    run = compute_indicator(registry.get("GTRANS"), rows, ())
    assert {(s.country_code, s.year) for s in run.observed_scores} == {("AAA", 1995), ("AAA", 2005), ("AAA", 2018)}
    imputed = by_identity(run.imputed_scores)
    assert set(imputed) == {("AAA", y) for y in range(2019, 2024)}  # forward to 2023 only; not backward, no interpolation, not 2024
    for (_, year), score in imputed.items():
        carried = next(o for o in score.inputs if o.dataset_code == "IEA_TCO2EM")
        assert carried.provenance["anchor_year"] == 2018 and score.score == gtrans.score_gtrans(7e9, 1e6 * (year - 1990))
    unscored = {(u.country_code, u.year) for u in run.unscored}
    assert ("AAA", 2006) in unscored and ("AAA", 2024) in unscored and ("AAA", 1990) in unscored  # interior gap, after the window, before the window


def test_gtrans_series_ending_before_2000_is_not_carried_into_the_window():
    rows = [co2("AAA", 1998, 7e9)] + [population("AAA", y, 1e6) for y in (1998, 2000, 2010)]
    run = compute_indicator(registry.get("GTRANS"), rows, ())
    assert run.imputed_scores == () and {(s.year) for s in run.observed_scores} == {1998}  # the route saw only 2000-2023 rows


def test_forward_input_strategy_is_generic():
    strategy = ExtrapolateInputsForwardThenScore(formula=gtrans.score_gtrans, years=(2000, 2023), datasets=("IEA_TCO2EM",))
    assert isinstance(strategy, ImputationStrategy) and strategy.recipient_group is None and strategy.auxiliary_datasets == ()
    rows = [co2("AAA", 2021, 7e9), population("AAA", 2021, 1e6)]  # population carried nowhere: it is not listed
    run = compute_indicator(registry.get("GTRANS"), rows, ())
    assert run.imputed_scores == () and {(u.year, tuple(o.dataset_code for o in u.inputs)) for u in run.unscored} == {(2022, ("IEA_TCO2EM",)), (2023, ("IEA_TCO2EM",))}


# --- BEEFMK -------------------------------------------------------------------------------------


def test_beefmk_averages_production_per_person_and_consumption_on_fifty_to_zero():
    assert beefmk.score_beefmk(12287.0, 37.04, 336806231) == (goalpost(12287.0 / 336806231, 50, 0) + goalpost(37.04, 50, 0)) / 2
    assert beefmk.score_beefmk(0.0, 0.0, 1e6) == 1.0 and beefmk.score_beefmk(0.0, 50.0, 1e6) == 0.5
    assert beefmk.score_beefmk(12287.0, 50.0, 336806231) < 0.5 < beefmk.score_beefmk(12287.0, 49.99, 336806231)  # BEEFMK-1: production adds at most 0.5
    assert beefmk.PRODUCTION_GOALPOSTS == beefmk.CONSUMPTION_GOALPOSTS == registry.get("BEEFMK").goalposts == (50, 0)


def test_beefmk_strategy():
    strategy = registry.get("BEEFMK").imputation
    assert strategy == ExtrapolateScores(forward_to=2023, backward_to=2000, listed_recipients=("SGP",), reference_years=(2000, 2023))
    assert strategy.recipient_group is None and registry.get("BEEFMK").recipient_group is None


def beef(country, year, production=100.0, consumption=20.0, people=1e7):
    return [Observation("UNFAO_BFPROD", country, year, production, "1000 t"), Observation("UNFAO_BFCONS", country, year, consumption, "kg/capita/year"), Observation("WB_POPULN", country, year, people, "Population")]


def test_beefmk_extrapolates_scores_and_gives_the_listed_country_the_flat_mean():
    rows = beef("AAA", 2010, consumption=10.0) + beef("AAA", 2012, consumption=30.0) + beef("BBB", 2023, consumption=40.0)
    run = compute_indicator(registry.get("BEEFMK"), rows, ("AAA", "BBB", "SGP", "JPN"))
    observed = by_identity(run.observed_scores)
    imputed = by_identity(run.imputed_scores)
    assert {k for k in imputed if k[0] == "AAA"} == {("AAA", y) for y in range(2000, 2010)} | {("AAA", y) for y in range(2013, 2024)}  # 2011 stays a gap
    assert {k for k in imputed if k[0] == "BBB"} == {("BBB", y) for y in range(2000, 2023)}
    mean = sum(s.score for s in observed.values()) / 3
    assert {k for k in imputed if k[0] == "SGP"} == {("SGP", y) for y in range(2000, 2024)} and {imputed[("SGP", y)].score for y in range(2000, 2024)} == {mean}
    assert not any(c == "JPN" for c, _ in imputed)  # a member with no data that is not on the list stays unscored (BEEFMK-3)
    assert all(is_imputed(s) for s in imputed.values()) and set(observed).isdisjoint(imputed)


def test_listed_recipients_validation_and_collision():
    with pytest.raises(ImputationError, match="not both"):
        ExtrapolateScores(forward_to=2023, recipient_group="SSPI67", listed_recipients=("SGP",), reference_years=(2000, 2023))
    with pytest.raises(ImputationError, match="go together"):
        ExtrapolateScores(forward_to=2023, listed_recipients=("SGP",))
    with pytest.raises(ImputationError, match=r"\['SGP'\] now have observed scores"):
        compute_indicator(registry.get("BEEFMK"), beef("AAA", 2010) + beef("SGP", 2010), ())


def test_listed_recipient_without_a_reference_class_gets_nothing():
    run = compute_indicator(registry.get("BEEFMK"), [], ())
    assert run.scores == ()  # legacy `if ref_data:`
