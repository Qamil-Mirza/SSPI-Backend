"""ALTNRG formulas, the computed percentage series on the definition, and
``ConstantFillInputsThenScore``: what is zero-filled, for whom, in what
order relative to extrapolation, interpolation and scoring. Pure, no
database."""

import pytest

from sspi.errors import IndicatorDefinitionError
from sspi.imputation import is_imputed
from sspi.indicators import IndicatorDefinition, altnrg, compute_indicator, registry
from sspi.indicators.strategy import ConstantFillInputsThenScore, ImputationStrategy
from sspi.metadata import MetadataCatalog
from sspi.scoring import ComputedSeries, Observation, goalpost

CODES = ("IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL")
DEFINITION = registry.get("ALTNRG")


def obs(code, country, year, value):
    return Observation(code, country, year, float(value), "TJ")


def group(country, year, coal=0, gas=0, nuclear=0, hydro=0, other=0, bio=0, oil=0):
    """Rows for one country-year; a zero argument means no row, as the cleaner drops zeros."""
    return [obs(code, country, year, value) for code, value in zip(CODES, (coal, gas, nuclear, hydro, other, bio, oil)) if value]


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


# --- formulas -----------------------------------------------------------------------------------


def test_percentage_counts_nuclear_hydro_other_renewables_and_half_of_biofuels_over_all_seven():
    # coal 400, gas 100, nuclear 50, hydro 30, other renewables 20, biofuels 100, oil 300: (50 + 30 + 20 + 100 - 50) / 1000 * 100
    assert altnrg.altnrg_percent_value(400, 100, 50, 30, 20, 100, 300) == 15.0
    assert altnrg.score_altnrg_observed(400, 100, 50, 30, 20, 100, 300) == goalpost(15.0, 0, 60) == 0.25
    assert altnrg.score_altnrg_imputed(400, 100, 50, 30, 20, 100, 300) == 0.25
    assert altnrg.altnrg_percent_value(0, 0, 0, 0, 0, 100, 0) == 50.0  # all biofuels: half credit
    assert altnrg.score_altnrg_observed(0, 0, 50, 30, 20, 0, 0) == 1.0  # 100%: clamped at the upper goalpost of 60
    assert altnrg.score_altnrg_observed(500, 500, 0, 0, 0, 0, 0) == 0.0


def test_a_zero_total_scores_zero_in_the_impute_route_and_divides_by_zero_in_the_compute_route():
    assert altnrg.score_altnrg_imputed(0, 0, 0, 0, 0, 0, 0) == 0.0
    with pytest.raises(ZeroDivisionError):
        altnrg.score_altnrg_observed(0, 0, 0, 0, 0, 0, 0)  # unreachable from source data: the cleaner drops zeros


def test_definition_agrees_with_canonical_metadata():
    catalog = MetadataCatalog.load()
    DEFINITION.check_against(catalog)
    assert DEFINITION.dataset_codes == CODES == catalog.indicator("ALTNRG").dataset_codes and DEFINITION.goalposts == (0, 60) and DEFINITION.unit == "Index"
    assert (catalog.indicator("ALTNRG").category_code, catalog.indicator("ALTNRG").pillar_code) == ("NRG", "SUS")
    strategy = DEFINITION.imputation
    assert isinstance(strategy, ImputationStrategy) and isinstance(strategy, ConstantFillInputsThenScore)
    assert (strategy.years, strategy.recipient_group, strategy.fill_value, strategy.fill_unit, strategy.fill_method) == ((2000, 2023), "SSPI67", 0.0, "PJ", "Zero imputation for missing energy type")
    assert strategy.formula is altnrg.score_altnrg_imputed and DEFINITION.score_dependencies == () and DEFINITION.auxiliary_datasets == ()


# --- computed series ----------------------------------------------------------------------------


def test_the_percentage_is_stored_on_observed_scores_only():
    (series,) = DEFINITION.computed_series
    assert (series.dataset_code, series.unit, series.value_function) == ("IEA_ALTNRG_PERCENTAGE", "% of Total Energy Supply from Alternative Sources (Partial Credit for Biowaste)", altnrg.altnrg_percent_value)
    rows = group("USA", 2020, 400, 100, 50, 30, 20, 100, 300) + group("USA", 2022, 400, 100, 50, 30, 20, 100, 300)
    result = compute_indicator(DEFINITION, rows, ["USA"])
    scores = by_identity(result.scores)
    (computed,) = scores[("USA", 2020)].computed
    assert (computed.dataset_code, computed.value) == ("IEA_ALTNRG_PERCENTAGE", 15.0) and scores[("USA", 2020)].score == 0.25
    assert scores[("USA", 2021)].computed == () and is_imputed(scores[("USA", 2021)]) and scores[("USA", 2021)].score == 0.25  # the impute route derives no series


def test_computed_series_must_be_computed_series_and_must_not_reuse_a_dataset_code():
    def score_x(DS_X):  # noqa: N803
        return DS_X

    with pytest.raises(IndicatorDefinitionError, match="computed_series"):
        IndicatorDefinition(code="X", observed_score=score_x, computed_series=("DS_Y",))
    with pytest.raises(IndicatorDefinitionError, match="reuse"):
        IndicatorDefinition(code="X", observed_score=score_x, computed_series=(ComputedSeries("DS_X", "u", score_x),))
    assert all(registry.get(code).computed_series == () for code in registry.codes() if code != "ALTNRG")  # nothing else changed


# --- observed pass ------------------------------------------------------------------------------


def test_a_country_year_missing_any_of_the_seven_is_not_scored_by_the_compute_route():
    rows = group("XXX", 2020, 400, 100, 0, 30, 20, 100, 300)  # no nuclear row
    result = compute_indicator(DEFINITION, rows)  # no recipients: nothing can be zero-filled
    assert result.observed_scores == () and result.imputed_scores == ()
    assert sorted((u.country_code, u.year, len(u.inputs)) for u in result.unscored) == [("XXX", year, 6) for year in range(2000, 2024)]  # carried to 2000-2023, still six of seven everywhere


# --- impute route -------------------------------------------------------------------------------


def test_a_member_with_no_row_in_a_dataset_gets_zero_for_2000_to_2023_labelled_pj():
    rows = [r for year in (2019, 2020, 2021, 2022, 2023, 2024) for r in group("MYS", year, 400, 100, 0, 30, 20, 100, 300)]
    result = compute_indicator(DEFINITION, rows, ["MYS"])
    scores = by_identity(result.scores)
    assert result.observed_scores == () and sorted(y for _, y in scores) == list(range(2000, 2024))  # 2024 has no zero-fill: unscored
    assert [(u.country_code, u.year) for u in result.unscored] == [("MYS", 2024)]
    nuclear = {y: next(o for o in s.inputs if o.dataset_code == "IEA_NCLEAR") for (_, y), s in scores.items()}
    assert all((o.value, o.unit, o.provenance) == (0.0, "PJ", {"imputed": True, "imputation_method": "Zero imputation for missing energy type"}) for o in nuclear.values())
    assert all(s.score == goalpost((30 + 20 + 100 - 50) / 950 * 100, 0, 60) for s in scores.values())
    others = [o for o in scores[("MYS", 2021)].inputs if o.dataset_code != "IEA_NCLEAR"]
    assert len(others) == 6 and not any(o.provenance.get("imputed") for o in others) and {o.unit for o in others} == {"TJ"}


def test_zero_fill_is_per_dataset_and_only_for_countries_with_no_row_at_all_in_it():
    """A series that exists is never zero-filled: it is carried from its nearest value instead, so a
    nuclear fleet that closed in 2009 is carried forward to 2023 and a series that starts in 2010 is carried back."""
    rows = [r for year in range(2000, 2024) for r in group("LTU", year, 400, 100, 50 if year <= 2009 else 0, 30, 20 if year >= 2010 else 0, 100, 300)]
    result = compute_indicator(DEFINITION, rows, ["LTU"])
    scores = by_identity(result.scores)
    assert len(scores) == 24 and all(is_imputed(s) for s in scores.values()) and result.unscored == ()
    late = {o.dataset_code: o for o in scores[("LTU", 2020)].inputs}
    assert (late["IEA_NCLEAR"].value, late["IEA_NCLEAR"].provenance["imputation_method"], late["IEA_NCLEAR"].provenance["anchor_year"]) == (50.0, "Forward Extrapolation", 2009)
    early = {o.dataset_code: o for o in scores[("LTU", 2003)].inputs}
    assert (early["IEA_GEOPWR"].value, early["IEA_GEOPWR"].provenance["imputation_method"], early["IEA_GEOPWR"].provenance["imputation_distance"]) == (20.0, "Backward Extrapolation", 7)
    assert not any(o.unit == "PJ" for s in scores.values() for o in s.inputs)


def test_interior_gaps_are_interpolated_in_any_year_and_everything_else_is_filled_from_observed_rows():
    rows = group("JPN", 1995, 400, 100, 60, 30, 20, 100, 300) + group("JPN", 1996, 400, 100, 0, 30, 20, 100, 300) + group("JPN", 1997, 400, 100, 40, 30, 20, 100, 300)
    result = compute_indicator(DEFINITION, rows, ["JPN"])
    scores = by_identity(result.scores)
    assert [y for (_, y), s in sorted(scores.items()) if not is_imputed(s)] == [1995, 1997]
    gap = next(o for o in scores[("JPN", 1996)].inputs if o.dataset_code == "IEA_NCLEAR")
    assert (gap.value, gap.provenance["imputation_method"]) == (50.0, "Linear Interpolation")  # 1996 is outside 2000-2023 and still filled
    assert sorted(y for _, y in scores) == [1995, 1996, 1997] + list(range(1998, 2024))  # carried forward to 2023 from 1997
    assert scores[("JPN", 2023)].score == scores[("JPN", 1997)].score


def test_a_non_member_is_extrapolated_but_never_zero_filled():
    rows = [r for year in range(2000, 2024) for r in group("BOL", year, 400, 100, 0, 30, 20, 100, 300)]
    result = compute_indicator(DEFINITION, rows, ["MYS"])
    assert not any(s.country_code == "BOL" for s in result.scores) and len([u for u in result.unscored if u.country_code == "BOL"]) == 24
    malaysia = [s for s in result.scores if s.country_code == "MYS"]
    assert len(malaysia) == 24 and {s.score for s in malaysia} == {0.0}  # a member absent from all seven datasets: all zeros, total zero, score 0.0
    assert all(len(s.inputs) == 7 and {o.unit for o in s.inputs} == {"PJ"} for s in malaysia)


def test_observed_and_imputed_identities_never_collide_and_the_strategy_is_generic():
    rows = [r for year in range(2000, 2024) for r in group("USA", year, 400, 100, 50, 30, 20, 100, 300)]
    result = compute_indicator(DEFINITION, rows, ["USA"])
    assert len(result.observed_scores) == 24 and result.imputed_scores == () and result.unscored == ()

    def score_sum(DS_A, DS_B):  # noqa: N803
        return (DS_A + DS_B) / 10

    definition = IndicatorDefinition(code="X", observed_score=score_sum, imputation=ConstantFillInputsThenScore(score_sum, (2001, 2002), "G", fill_value=1.0, fill_unit="u", fill_method="constant"))
    result = compute_indicator(definition, [Observation("DS_A", "MYS", 2001, 4.0, "u")], ["MYS"])
    assert [(s.year, s.score) for s in sorted(result.scores, key=lambda s: s.year)] == [(2001, 0.5), (2002, 0.5)] and all(is_imputed(s) for s in result.scores)
