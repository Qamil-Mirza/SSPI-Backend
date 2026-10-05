"""DEFRST: formula, compute-route filter, the score-level imputation strategy
and its primitives, the refusal on recipients that already have observed
scores. No database, no network."""

import pytest

from sspi.errors import ImputationError, IndicatorDefinitionError
from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.defrst import DEFINITION, IMPUTATION_YEARS, REFERENCE_CLASS_RECIPIENTS, DefrstImputation, keep_for_scoring, score_defrst
from sspi.indicators.strategy import extrapolate_scores_forward, reference_class_average_scores
from sspi.metadata import MetadataCatalog
from sspi.scoring import IndicatorScore, Observation


def level(country, year, value):
    return Observation("UNFAO_FRSTLV", country, year, value, "1000 ha")


def average(country, year, value):
    return Observation("UNFAO_FRSTAV", country, year, value, "hectares (1990s Average)")


def series(country, levels, baseline):
    """Level rows for the given years plus the legacy 1990-2022 average rows."""
    return [level(country, y, v) for y, v in levels.items()] + [average(country, y, baseline) for y in range(1990, 2023)]


# --- formula and filter ---------------------------------------------------------------------


@pytest.mark.parametrize("lv, av, expected", [(120.0, 100.0, 2 / 3), (100.0, 100.0, 1 / 3), (80.0, 100.0, 0.0), (140.0, 100.0, 1.0), (5.0, 0.0, 0)])
def test_formula_is_percent_change_goalposted_with_zero_guard(lv, av, expected):
    assert score_defrst(lv, av) == expected


def test_zero_average_returns_integer_zero_as_legacy():
    assert score_defrst(5.0, 0.0) == 0 and type(score_defrst(5.0, 0.0)) is int


def test_compute_filter_keeps_level_rows_from_2000_and_every_average_row():
    assert not keep_for_scoring(level("AAA", 1999, 1.0)) and keep_for_scoring(level("AAA", 2000, 1.0))
    assert keep_for_scoring(average("AAA", 1990, 1.0))


def test_definition_is_registered_and_consistent_with_metadata():
    assert registry.get("DEFRST") is DEFINITION
    assert DEFINITION.dataset_codes == ("UNFAO_FRSTLV", "UNFAO_FRSTAV") and DEFINITION.goalposts == (-20, 40)
    assert isinstance(DEFINITION.imputation, DefrstImputation) and DEFINITION.auxiliary_datasets == () and DEFINITION.recipient_group is None
    DEFINITION.check_against(MetadataCatalog.load())


def test_observation_filter_must_be_callable():
    from dataclasses import replace

    with pytest.raises(IndicatorDefinitionError, match="observation_filter"):
        replace(DEFINITION, observation_filter=3)


# --- observed pass ------------------------------------------------------------------------


def test_level_rows_before_2000_and_after_2022_never_score():
    rows = series("AAA", {1999: 100.0, 2000: 110.0, 2022: 120.0, 2023: 130.0}, 100.0)
    run = compute_indicator(DEFINITION, rows)
    assert {(s.year, s.score) for s in run.observed_scores} == {(2000, score_defrst(110.0, 100.0)), (2022, score_defrst(120.0, 100.0))}
    unscored = {(u.country_code, u.year): u for u in run.unscored}
    assert unscored[("AAA", 1999)].details == ("UNFAO_FRSTLV",) and all(o.dataset_code == "UNFAO_FRSTAV" for o in unscored[("AAA", 1999)].inputs)  # the level row was filtered out
    assert ("AAA", 2023) not in unscored  # filled by the forward extrapolation
    assert set(unscored) == {("AAA", y) for y in range(1990, 2000)} | {("AAA", y) for y in range(2001, 2022)}  # average rows without a level


# --- score-level primitives --------------------------------------------------------------------


def score(country, year, value, provenance=None):
    return IndicatorScore("DEFRST", country, year, value, "Index", (level(country, year, 1.0), average(country, year, 1.0)), (), provenance or {})


def test_forward_extrapolation_copies_the_latest_score_with_its_inputs():
    added = extrapolate_scores_forward([score("AAA", 2020, 0.4), score("AAA", 2019, 0.3), score("BBB", 2023, 0.9)], 2023)
    assert [(s.country_code, s.year, s.score) for s in added] == [("AAA", 2021, 0.4), ("AAA", 2022, 0.4), ("AAA", 2023, 0.4)]
    for s in added:
        assert s.provenance["imputed"] is True and s.provenance["imputation_method"] == "Forward Extrapolation"
        assert s.provenance["source_year"] == 2020 and s.provenance["imputation_distance"] == s.year - 2020
        assert all(o.year == 2020 for o in s.inputs) and is_imputed(s)


def test_forward_extrapolation_refuses_duplicate_identities():
    with pytest.raises(ImputationError, match="duplicate"):
        extrapolate_scores_forward([score("AAA", 2020, 0.4), score("AAA", 2020, 0.5)], 2023)


def test_reference_class_average_of_scores():
    reference = [score("AAA", 2000, 0.2), score("BBB", 2001, 0.4), score("BBB", 2024, 0.9)]  # all years count, range or not
    added = reference_class_average_scores("CCC", "DEFRST", 2000, 2002, reference)
    assert [(s.year, s.score) for s in added] == [(2000, 0.5), (2001, 0.5), (2002, 0.5)]
    assert added[0].inputs == () and added[0].provenance == {"imputed": True, "imputation_method": "ImputeReferenceClassAverage", "reference_score_count": 3, "requested_years": [2000, 2002]}
    with pytest.raises(ImputationError, match="empty"):
        reference_class_average_scores("CCC", "DEFRST", 2000, 2002, [])
    with pytest.raises(ImputationError, match="units"):
        reference_class_average_scores("CCC", "DEFRST", 2000, 2002, [score("AAA", 2000, 0.2), IndicatorScore("DEFRST", "BBB", 2000, 0.2, "Other", ())])


# --- strategy -------------------------------------------------------------------------------


def test_strategy_extrapolates_every_country_and_gives_recipients_the_mean_of_the_others():
    rows = series("AAA", {2000: 100.0, 2021: 110.0}, 100.0) + series("ZZZ", {2000: 100.0, 2022: 130.0}, 100.0)
    rows += [level("BEL", y, 50.0) for y in range(2000, 2025)]  # level rows but no 1990s mean: unscored, as in current FAO data
    run = compute_indicator(DEFINITION, rows)
    observed = {(s.country_code, s.year): s.score for s in run.observed_scores}
    assert set(observed) == {("AAA", 2000), ("AAA", 2021), ("ZZZ", 2000), ("ZZZ", 2022)}
    imputed = {(s.country_code, s.year): s for s in run.imputed_scores}
    assert {k for k in imputed if k[0] == "AAA"} == {("AAA", 2022), ("AAA", 2023)} and imputed[("AAA", 2023)].provenance["imputation_distance"] == 2
    assert {k for k in imputed if k[0] == "ZZZ"} == {("ZZZ", 2023)}
    mean = sum(observed.values()) / 4
    for country in REFERENCE_CLASS_RECIPIENTS:
        years = sorted(y for c, y in imputed if c == country)
        assert years == list(range(*IMPUTATION_YEARS)) + [IMPUTATION_YEARS[1]]
        assert {imputed[(country, y)].score for y in years} == {mean} and imputed[(country, 2000)].provenance["reference_score_count"] == 4
    assert ("BEL", 2024) in {(u.country_code, u.year) for u in run.unscored} and ("BEL", 2000) not in {(u.country_code, u.year) for u in run.unscored}
    assert all(is_imputed(s) for s in run.imputed_scores)


def test_strategy_with_no_reference_scores_only_extrapolates():
    rows = series("BEL", {2000: 100.0}, 100.0)  # only a recipient has scores: legacy `if ref_data:` guard
    with pytest.raises(ImputationError, match="DEFRST-1"):
        compute_indicator(DEFINITION, rows)  # ...but a recipient with observed scores is the undecided case first


def test_recipient_with_observed_scores_is_refused_naming_the_conflict():
    """Pending methodology decision (DEFRST-1): no precedence rule exists, so the strategy stops rather than skipping or keeping
    the imputation. The WATMAN-3 canonical-first policy is NOT generalized here."""
    rows = series("AAA", {2000: 100.0}, 100.0) + series("ARE", {2000: 100.0, 2001: 100.0}, 100.0)
    with pytest.raises(ImputationError, match=r"\['ARE'\].*DEFRST-1") as info:
        compute_indicator(DEFINITION, rows)
    message = str(info.value)
    assert "source data has changed" in message and "hard-coded" in message and "No precedence" in message and "Methodology review is required" in message
    # neither direction is implemented: with ARE's rows removed the legacy result is reproduced, with them present nothing is produced
    assert len(compute_indicator(DEFINITION, series("AAA", {2000: 100.0}, 100.0)).imputed_scores) == 23 + 72  # 2001-2023 extrapolated + 3 x 24 reference


def test_strategy_result_classifies_and_never_collides():
    rows = series("AAA", {2000: 100.0, 2010: 105.0}, 100.0)
    run = compute_indicator(DEFINITION, rows)
    assert {(s.country_code, s.year) for s in run.observed_scores}.isdisjoint({(s.country_code, s.year) for s in run.imputed_scores})
    assert all(not o.provenance.get("imputed") for s in run.imputed_scores for o in s.inputs)  # no fabricated observations
