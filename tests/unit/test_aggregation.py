"""Unit tests for the pure aggregation kernel (sspi.aggregation).

Parity with legacy is in tests/golden/test_golden_aggregation.py; these pin
the rules one at a time on a three-level toy hierarchy.
"""

import pytest

from sspi.aggregation import LEGACY_COUNTRY_GROUP, LEGACY_YEARS, ScoreCell, aggregate, legacy_mean, legacy_sum, select_indicators
from sspi.errors import AggregationError
from sspi.metadata import ItemMetadata, MetadataCatalog

TREE = (
    ItemMetadata("SSPI", "SSPI", "Root", ("P1", "P2")),
    ItemMetadata("P1", "Pillar", "Pillar 1", ("C1", "C2")),
    ItemMetadata("P2", "Pillar", "Pillar 2", ("C3",)),
    ItemMetadata("C1", "Category", "Category 1", ("A", "B")),
    ItemMetadata("C2", "Category", "Category 2", ("C",)),
    ItemMetadata("C3", "Category", "Category 3", ("D", "E")),
)
COUNTRIES = ("USA", "FRA")
YEARS = (2000, 2001)


def cells(scores, countries=COUNTRIES, years=range(2000, 2002), imputed=()):
    """{indicator: score} for every country and year, unless a score is a {(country, year): score} dict."""
    out = []
    for code, score in scores.items():
        for country in countries:
            for year in years:
                value = score.get((country, year), "absent") if isinstance(score, dict) else score
                if value != "absent":
                    out.append(ScoreCell(code, country, year, value, code in imputed))
    return out


def scores_by(result):
    return {(s.item_code, s.country_code, s.year): s.score for s in result.scores}


# --- arithmetic -------------------------------------------------------------


def test_legacy_sum_is_compensated_for_floats():
    assert legacy_sum([1e16, 1.0, -1e16]) == 1.0  # a plain left-to-right fold gives 0.0


def test_legacy_sum_adds_an_integer_after_a_float_without_compensation():
    """Production (Python 3.13) stored EDU ARE 2019 = ...565; Python 3.14's sum() gives ...564."""
    values = [0.9894805908203125, 0.9918800354003906, 1, 0.49926516129032256]
    assert legacy_sum(values) / 4 == 0.8701564468777565
    assert legacy_sum([float(v) for v in values]) / 4 == 0.8701564468777564


def test_legacy_sum_adds_leading_integers_exactly_and_keeps_an_all_integer_sum_an_int():
    assert legacy_sum([1, 0, 1]) == 2 and isinstance(legacy_sum([1, 0, 1]), int)
    assert legacy_sum([]) == 0
    assert legacy_sum([1, 0.25]) == 1.25


def test_legacy_mean_treats_exact_zero_and_one_indicator_scores_as_legacy_integers():
    values = [0.9894805908203125, 0.9918800354003906, 1.0, 0.49926516129032256]
    assert legacy_mean(values, indicator_scores=True) == 0.8701564468777565
    assert legacy_mean(values) == 0.8701564468777564  # pillars and the root average floats
    assert legacy_mean([1.0, 1.0], indicator_scores=True) == 1.0


# --- which indicators take part ----------------------------------------------


def test_an_indicator_takes_part_only_with_every_country_and_year():
    full = {"A": 0.5, "B": 0.5, "C": 0.5, "D": 0.5}
    gap = {("USA", 2000): 0.5, ("USA", 2001): 0.5, ("FRA", 2001): 0.5}  # FRA 2000 missing
    included, excluded = select_indicators(TREE, cells({**full, "E": gap}), countries=COUNTRIES, years=YEARS)
    assert included == ("A", "B", "C", "D")
    (e,) = excluded
    assert (e.indicator_code, e.missing_cells, e.first_missing) == ("E", 1, ("FRA", 2000))
    assert e.reason == "1 country-years without a score, first FRA 2000"


def test_rows_outside_the_window_or_the_group_do_not_complete_an_indicator():
    rows = cells({"A": 0.5}, countries=("USA",)) + cells({"A": 0.5}, countries=("FRA",), years=[1999, 2002]) + cells({"A": 0.5}, countries=("BRA",))
    included, excluded = select_indicators(TREE, rows, countries=COUNTRIES, years=YEARS)
    assert "A" not in included and excluded[0].missing_cells == 2


def test_a_null_score_still_counts_as_coverage_like_legacy():
    included, _ = select_indicators(TREE, cells({"A": None}), countries=COUNTRIES, years=YEARS)
    assert included == ("A",)


def test_excluded_and_included_follow_methodology_order():
    included, excluded = select_indicators(TREE, cells({"E": 0.1, "A": 0.1}), countries=COUNTRIES, years=YEARS)
    assert included == ("A", "E") and [e.indicator_code for e in excluded] == ["B", "C", "D"]


# --- pruning and averaging ---------------------------------------------------


def test_scores_are_unweighted_means_of_the_children_that_take_part():
    result = aggregate(TREE, cells({"A": 0.2, "B": 0.4, "C": 0.9, "D": 0.6, "E": 0.0}), countries=COUNTRIES, years=YEARS)
    s = scores_by(result)
    assert s[("C1", "USA", 2000)] == legacy_mean([0.2, 0.4], indicator_scores=True)
    assert s[("C3", "USA", 2000)] == 0.3
    assert s[("P1", "USA", 2000)] == legacy_mean([s[("C1", "USA", 2000)], 0.9])
    assert s[("SSPI", "USA", 2000)] == legacy_mean([s[("P1", "USA", 2000)], s[("P2", "USA", 2000)]])


def test_empty_categories_and_pillars_are_dropped_and_parents_average_what_is_left():
    result = aggregate(TREE, cells({"A": 0.2, "D": 0.6}), countries=COUNTRIES, years=YEARS)  # B, C, E incomplete
    codes = {s.item_code for s in result.scores}
    assert codes == {"SSPI", "P1", "P2", "C1", "C3"}
    s = scores_by(result)
    assert s[("C1", "FRA", 2001)] == 0.2 and s[("P1", "FRA", 2001)] == 0.2
    assert s[("SSPI", "FRA", 2001)] == legacy_mean([0.2, 0.6])
    c1 = next(x for x in result.scores if x.item_code == "C1")
    root = next(x for x in result.scores if x.item_code == "SSPI")
    assert c1.children == ("A",) and c1.indicators == ("A",)
    assert root.children == ("P1", "P2") and root.indicators == ("A", "D")


def test_scores_are_ordered_by_country_then_year_then_root_pillars_categories():
    result = aggregate(TREE, cells({"A": 0.2, "C": 0.3, "D": 0.6}), countries=COUNTRIES, years=YEARS)
    order = [(s.country_code, s.year, s.item_code) for s in result.scores]
    assert order[:6] == [("FRA", 2000, c) for c in ("SSPI", "P1", "P2", "C1", "C2", "C3")]
    assert order[-1] == ("USA", 2001, "C3") and len(order) == 2 * 2 * 6


def test_nothing_complete_means_nothing_scored():
    result = aggregate(TREE, cells({"A": 0.2}, countries=("USA",)), countries=COUNTRIES, years=YEARS)
    assert result.scores == () and result.included == ()


def test_unknown_indicator_codes_and_rows_outside_the_window_are_ignored():
    rows = cells({"A": 0.2, "ZZZ": 0.9}) + [ScoreCell("A", "USA", 2024, 0.99), ScoreCell("A", "BRA", 2000, 0.99)]
    s = scores_by(aggregate(TREE, rows, countries=COUNTRIES, years=YEARS))
    assert set(s.values()) == {0.2}


def test_a_null_score_of_an_included_indicator_stops_the_run():
    rows = cells({"A": {("USA", 2000): None, ("USA", 2001): 0.1, ("FRA", 2000): 0.1, ("FRA", 2001): 0.1}})
    with pytest.raises(AggregationError, match="NULL score for A USA 2000"):
        aggregate(TREE, rows, countries=COUNTRIES, years=YEARS)


def test_two_scores_for_one_identity_stop_the_run():
    rows = cells({"A": 0.1}) + [ScoreCell("A", "FRA", 2001, 0.2, True)]
    with pytest.raises(AggregationError, match="two scores for A FRA 2001"):
        aggregate(TREE, rows, countries=COUNTRIES, years=YEARS)


def test_a_null_score_outside_the_included_indicators_is_harmless():
    rows = cells({"A": 0.1}) + [ScoreCell("B", "USA", 2000, None)]
    assert len(aggregate(TREE, rows, countries=COUNTRIES, years=YEARS).scores) == 3 * 2 * 2  # SSPI, P1, C1


# --- defaults ------------------------------------------------------------------


def test_defaults_are_the_legacy_window_and_group_used_by_imputation():
    from sspi.indicators import registry

    assert LEGACY_YEARS == registry.LEGACY_IMPUTATION_YEARS == (2000, 2023)
    assert LEGACY_COUNTRY_GROUP == registry.LEGACY_RECIPIENT_GROUP == "SSPI67"


def test_the_bundled_hierarchy_places_every_indicator_once():
    catalog = MetadataCatalog.load()
    placed = [c for item in catalog.hierarchy() if item.item_type == "Category" for c in item.children]
    assert sorted(placed) == sorted(i.code for i in catalog.indicators()) and len(placed) == 57
    assert [i.item_type for i in catalog.hierarchy()].count("Category") == 16
