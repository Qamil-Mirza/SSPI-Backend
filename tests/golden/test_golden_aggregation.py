"""Aggregation parity with the pinned legacy backend.

Both goldens come from ``generate_aggregation_cases.py``, which runs the
legacy ``finalize_sspi_dynamic_score_iterator`` unchanged on in-memory
collections:

* ``aggregation_cases.json``: synthetic scenarios, inputs written into the
  golden;
* ``aggregation_on_production_cases.json``: production's own indicator scores
  (snapshot 2026-11-09). Legacy reproduces production's stored category,
  pillar and SSPI scores exactly (``production_differences`` is empty), so
  matching legacy here is matching production.

Scores are compared exactly, including order. Inputs are passed as floats, as
PostgreSQL returns them, although legacy stored clamped scores as ints.
"""

import pytest

from sspi.aggregation import ScoreCell, aggregate
from sspi.errors import AggregationError
from sspi.metadata import MetadataCatalog
from tests.golden.parity import load_cases

SYNTHETIC = load_cases("aggregation_cases.json")
PRODUCTION = load_cases("aggregation_on_production_cases.json")
HIERARCHY = MetadataCatalog.load().hierarchy()


def as_float(score):
    return None if score is None else float(score)


def synthetic_cells(case):
    return [
        ScoreCell(r["IndicatorCode"], r["CountryCode"], r["Year"], as_float(r["Score"]), part == "imputed")
        for part in ("observed", "imputed") for r in case[part]
    ]


def records(scores):
    return [[s.item_code, s.item_type, s.country_code, s.year, s.score] for s in scores]


def test_the_hierarchy_is_the_legacy_tree_in_legacy_order():
    assert [{"code": i.code, "item_type": i.item_type, "children": list(i.children)} for i in HIERARCHY] == SYNTHETIC["legacy_tree"]


@pytest.mark.parametrize("case", [c for c in SYNTHETIC["cases"] if "legacy_error" not in c], ids=lambda c: c["name"])
def test_synthetic_scores_match_legacy_exactly(case):
    result = aggregate(HIERARCHY, synthetic_cells(case), countries=case["group_members"])
    assert list(result.included) == case["complete_indicators"]
    expected = [[a["item_code"], a["item_type"], a["country_code"], a["year"], a["score"]] for a in case["aggregates"]]
    assert records(result.scores) == expected


@pytest.mark.parametrize(
    "name, message",
    [("null_score_in_complete_indicator", "NULL score for NITROG FRA 2010"), ("observed_and_imputed_collision", "two scores for NITROG KEN 2005")],
)
def test_where_legacy_raises_the_backend_raises_too(name, message):
    case = next(c for c in SYNTHETIC["cases"] if c["name"] == name)
    assert case["legacy_error"]["type"] in {"AssertionError", "DataMetadataMismatchError"}
    with pytest.raises(AggregationError, match=message):
        aggregate(HIERARCHY, synthetic_cells(case), countries=case["group_members"])


def test_legacy_left_the_item_table_emptied_or_half_written_when_it_raised():
    """AGG-1: legacy deletes sspi_item_data first; the backend replaces it in one transaction instead."""
    after = {c["name"]: c["item_data_after_error"] for c in SYNTHETIC["cases"] if "legacy_error" in c}
    assert after == {"null_score_in_complete_indicator": 0, "observed_and_imputed_collision": 500}


def test_legacy_stored_the_full_child_list_not_the_children_averaged():
    """AGG-2: legacy's Children field lists every child in the tree; the backend stores the ones averaged."""
    case = next(c for c in SYNTHETIC["cases"] if c["name"] == "partial_coverage")
    lnd = next(a for a in case["aggregates"] if a["item_code"] == "LND")
    result = aggregate(HIERARCHY, synthetic_cells(case), countries=case["group_members"])
    ours = next(s for s in result.scores if s.item_code == "LND")
    assert lnd["children"] == ["NITROG", "WATMAN", "CHMPOL", "DEFRST", "CARBON"]
    assert ours.children == ("NITROG", "CHMPOL")


def test_production_scores_match_legacy_and_production_exactly():
    cells = [
        ScoreCell(code, country, year, float(score), part == "imputed")
        for part in ("observed", "imputed")
        for code, by_country in PRODUCTION[part].items()
        for country, series in by_country.items()
        for year, score in series
    ]
    result = aggregate(HIERARCHY, cells, countries=PRODUCTION["group_members"])
    assert list(result.included) == PRODUCTION["complete_indicators"] and len(result.included) == 33
    assert records(result.scores) == PRODUCTION["aggregates"]["rows"] and len(result.scores) == 30_096
    assert PRODUCTION["production_differences"] == []
