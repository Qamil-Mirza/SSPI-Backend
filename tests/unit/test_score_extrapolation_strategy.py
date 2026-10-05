"""``ExtrapolateScores`` and its primitives, and the two indicators that use
it (NRGINT, AIRPOL): formulas, goalposts, which years are filled and for
whom. Pure, no database."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import is_imputed
from sspi.indicators import IndicatorDefinition, airpol, compute_indicator, nrgint, registry
from sspi.indicators.strategy import ExtrapolateScores, ImputationStrategy, extrapolate_scores_backward, extrapolate_scores_forward
from sspi.metadata import MetadataCatalog
from sspi.scoring import IndicatorScore, Observation, goalpost


def obs(country, year, value, dataset="UNSDG_AIRPOL", unit="mgr/m^3"):
    return Observation(dataset, country, year, value, unit)


def score(country, year, value, code="X"):
    return IndicatorScore(code, country, year, value, "Index", (obs(country, year, value * 10),), (), {})


def by_identity(scores):
    return {(s.country_code, s.year): s for s in scores}


# --- formulas -----------------------------------------------------------------------------------


def test_formulas_goalposts_and_direction():
    assert nrgint.score_nrgint(3.0) == goalpost(3.0, 15, 0) == 0.8  # lower intensity is better
    assert nrgint.score_nrgint(0) == 1.0 and nrgint.score_nrgint(15) == 0.0 and nrgint.score_nrgint(22.5) == 0.0 and nrgint.score_nrgint(-1) == 1.0
    assert airpol.score_airpol(10.0) == goalpost(10.0, 40, 0) == 0.75  # lower concentration is better
    assert airpol.score_airpol(0) == 1.0 and airpol.score_airpol(40) == 0.0 and airpol.score_airpol(65.2) == 0.0
    assert registry.get("NRGINT").goalposts == (15, 0) and registry.get("AIRPOL").goalposts == (40, 0)
    assert registry.get("NRGINT").dataset_codes == ("UNSDG_NRGINT",) and registry.get("AIRPOL").dataset_codes == ("UNSDG_AIRPOL",)
    assert registry.get("NRGINT").unit == registry.get("AIRPOL").unit == "Index"


def test_definitions_agree_with_canonical_metadata():
    catalog = MetadataCatalog.load()
    for code in ("NRGINT", "AIRPOL"):
        registry.get(code).check_against(catalog)
        assert catalog.indicator(code).category_code == "NRG" and catalog.indicator(code).pillar_code == "SUS"


def test_strategies_declare_what_the_legacy_routes_used():
    energy_intensity, air_pollution = registry.get("NRGINT").imputation, registry.get("AIRPOL").imputation
    assert isinstance(energy_intensity, ImputationStrategy) and isinstance(air_pollution, ImputationStrategy)
    assert energy_intensity == ExtrapolateScores(forward_to=2023)  # forward only, no group
    assert registry.get("NRGINT").recipient_group is None
    assert air_pollution == ExtrapolateScores(forward_to=2023, backward_to=2000, recipient_group="SSPI67", reference_years=(2000, 2023))
    assert registry.get("NRGINT").auxiliary_datasets == registry.get("AIRPOL").auxiliary_datasets == ()
    assert registry.get("NRGINT").score_dependencies == registry.get("AIRPOL").score_dependencies == ()


def test_a_reference_class_needs_both_a_group_and_years():
    with pytest.raises(ImputationError, match="go together"):
        ExtrapolateScores(forward_to=2023, recipient_group="SSPI67")
    with pytest.raises(ImputationError, match="go together"):
        ExtrapolateScores(forward_to=2023, reference_years=(2000, 2023))


# --- primitives ---------------------------------------------------------------------------------


def test_backward_extrapolation_copies_the_earliest_score_and_its_inputs():
    scores = [score("MYS", 2012, 0.5), score("MYS", 2010, 0.4), score("AUT", 2001, 0.9)]
    added = extrapolate_scores_backward(scores, 2000)
    assert [(s.country_code, s.year, s.score) for s in added] == [("MYS", y, 0.4) for y in range(2000, 2010)] + [("AUT", 2000, 0.9)]
    first = added[0]
    assert first.inputs == scores[1].inputs and first.inputs[0].year == 2010  # the anchor year's observation, not a fabricated one
    assert first.provenance == {"imputed": True, "imputation_method": "Backward Extrapolation", "imputation_distance": 10, "source_year": 2010}
    assert extrapolate_scores_backward([score("MYS", 1995, 0.1)], 2000) == ()  # already starts before the target


def test_forward_extrapolation_is_unchanged_and_mirrors_backward():
    scores = [score("MYS", 2020, 0.5), score("MYS", 2021, 0.6)]
    added = extrapolate_scores_forward(scores, 2023)
    assert [(s.year, s.score, s.provenance["imputation_distance"], s.provenance["source_year"]) for s in added] == [(2022, 0.6, 1, 2021), (2023, 0.6, 2, 2021)]
    assert added[0].provenance["imputation_method"] == "Forward Extrapolation" and extrapolate_scores_forward([score("MYS", 2024, 0.5)], 2023) == ()


def test_a_repeated_identity_is_refused():
    with pytest.raises(ImputationError, match="duplicate score identity"):
        extrapolate_scores_backward([score("MYS", 2010, 0.4), score("MYS", 2010, 0.5)], 2000)


# --- the strategy through the runner ------------------------------------------------------------


def test_nrgint_carries_the_latest_score_forward_only():
    rows = [obs("MYS", 2005, 6.0, "UNSDG_NRGINT", "MJ_PER_GDP_CON_PPP_USD"), obs("MYS", 2008, 3.0, "UNSDG_NRGINT", "MJ_PER_GDP_CON_PPP_USD"), obs("AUT", 2024, 1.5, "UNSDG_NRGINT", "MJ_PER_GDP_CON_PPP_USD")]
    result = compute_indicator(registry.get("NRGINT"), rows, ["MYS", "AUT", "USA"])  # recipients are ignored: the strategy asked for no group
    scores = by_identity(result.scores)
    assert sorted(scores) == [("AUT", 2024)] + [("MYS", 2005), ("MYS", 2008)] + [("MYS", y) for y in range(2009, 2024)]
    assert ("MYS", 2006) not in scores and ("MYS", 2004) not in scores  # no interpolation, nothing backward
    assert all(scores[("MYS", y)].score == 0.8 and is_imputed(scores[("MYS", y)]) for y in range(2009, 2024))
    assert not is_imputed(scores[("MYS", 2008)]) and scores[("MYS", 2023)].provenance["imputation_distance"] == 15
    assert not any(s.country_code == "USA" for s in result.scores) and result.unscored == ()


def test_airpol_fills_both_ends_and_gives_uncovered_members_the_mean_of_all_scores():
    rows = [obs("MYS", 2010, 20.0), obs("MYS", 2012, 10.0), obs("XXX", 2015, 30.0)]
    result = compute_indicator(registry.get("AIRPOL"), rows, ["MYS", "AUT"])
    scores = by_identity(result.scores)
    assert [y for (c, y) in sorted(scores) if c == "MYS"] == [y for y in range(2000, 2024) if y != 2011]  # the interior gap is not filled
    assert scores[("MYS", 2000)].score == 0.5 and scores[("MYS", 2023)].score == 0.75
    assert [y for (c, y) in sorted(scores) if c == "XXX"] == list(range(2000, 2024))  # every scored country is extrapolated, member or not
    austria = [scores[("AUT", y)] for y in range(2000, 2024)]
    assert {s.score for s in austria} == {(0.5 + 0.75 + 0.25) / 3}  # observed scores only, of every country, including the non-member
    assert all(s.inputs == () and s.provenance["imputation_method"] == "ImputeReferenceClassAverage" and s.provenance["reference_score_count"] == 3 for s in austria)
    assert len(result.observed_scores) == 3 and len(result.imputed_scores) == (10 + 11) + (15 + 8) + 24


def test_no_observations_means_no_scores_at_all():
    result = compute_indicator(registry.get("AIRPOL"), [], ["MYS", "AUT"])
    assert result.scores == () and result.unscored == ()  # legacy `if ref_data:`: no reference, no reference-class score


def test_observed_and_imputed_identities_never_collide():
    """Recipients are the members with no observed score, so the runner's collision check can never fire for this strategy."""
    rows = [obs(c, y, 12.0) for c in ("MYS", "AUT") for y in range(1998, 2026)]
    result = compute_indicator(registry.get("AIRPOL"), rows, ["MYS", "AUT"])
    assert result.imputed_scores == () and len(result.observed_scores) == 56


def test_the_strategy_is_not_tied_to_an_indicator():
    def score_x(DS_X):  # noqa: N803
        return DS_X / 100

    definition = IndicatorDefinition(code="X", observed_score=score_x, imputation=ExtrapolateScores(forward_to=2003, backward_to=1999))
    result = compute_indicator(definition, [obs("MYS", 2001, 50.0, "DS_X", "u")])
    assert [(s.year, s.score, is_imputed(s)) for s in sorted(result.scores, key=lambda s: s.year)] == [(1999, 0.5, True), (2000, 0.5, True), (2001, 0.5, False), (2002, 0.5, True), (2003, 0.5, True)]
