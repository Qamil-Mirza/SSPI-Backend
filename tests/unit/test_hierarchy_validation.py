"""hierarchy.yaml validation: the file order is the order scores are added in,
so it is checked, as is every indicator's place in the tree."""

import pytest
import yaml

from sspi.errors import MetadataError, UnknownCodeError
from sspi.metadata import MetadataCatalog


def indicator(code, pillar, category):
    return {
        "code": code, "name": code, "pillar_code": pillar, "category_code": category, "policy": None,
        "description": "d", "footnote": None, "dataset_codes": ["DS_A"], "lower_goalpost": None,
        "upper_goalpost": None, "score_function": None,
    }


def item(code, item_type, children):
    return {"code": code, "item_type": item_type, "name": code, "description": None, "short_description": None, "children": children}


GOOD = [
    item("SSPI", "SSPI", ["P1", "P2"]),
    item("P1", "Pillar", ["C1"]),
    item("P2", "Pillar", ["C2"]),
    item("C1", "Category", ["A", "B"]),
    item("C2", "Category", ["C"]),
]


def tree(tmp_path, items=GOOD, indicators=(("A", "P1", "C1"), ("B", "P1", "C1"), ("C", "P2", "C2")), hierarchy=True):
    for code, pillar, category in indicators:
        (tmp_path / "indicators").mkdir(exist_ok=True)
        (tmp_path / "indicators" / f"{code}.yaml").write_text(yaml.safe_dump(indicator(code, pillar, category)))
    (tmp_path / "datasets").mkdir(exist_ok=True)
    (tmp_path / "datasets" / "DS_A.yaml").write_text(yaml.safe_dump({"code": "DS_A", "status": "unresolved", "note": "n"}))
    if hierarchy:
        (tmp_path / "hierarchy.yaml").write_text(yaml.safe_dump({"items": items}, sort_keys=False))
    return tmp_path


def problems(tmp_path, **kwargs):
    with pytest.raises(MetadataError) as info:
        MetadataCatalog.load(tree(tmp_path, **kwargs))
    return str(info.value)


def test_a_valid_hierarchy_loads_in_file_order(tmp_path):
    catalog = MetadataCatalog.load(tree(tmp_path))
    assert [i.code for i in catalog.hierarchy()] == ["SSPI", "P1", "P2", "C1", "C2"]
    assert catalog.item("C1").children == ("A", "B")
    with pytest.raises(UnknownCodeError):
        catalog.item("A")


def test_a_tree_without_hierarchy_loads_but_cannot_be_aggregated(tmp_path):
    catalog = MetadataCatalog.load(tree(tmp_path, hierarchy=False))
    with pytest.raises(MetadataError, match="no hierarchy.yaml"):
        catalog.hierarchy()


def test_categories_out_of_their_pillars_order_are_refused(tmp_path):
    assert "categories must appear in their pillars' children order" in problems(tmp_path, items=[GOOD[0], GOOD[1], GOOD[2], GOOD[4], GOOD[3]])


def test_pillars_out_of_the_roots_order_are_refused(tmp_path):
    assert "pillars must appear in the root's children order" in problems(tmp_path, items=[GOOD[0], GOOD[2], GOOD[1], GOOD[3], GOOD[4]])


def test_the_root_must_come_first(tmp_path):
    assert "the first item, and only the first, must have item_type SSPI" in problems(tmp_path, items=GOOD[1:] + GOOD[:1])


def test_an_indicator_must_sit_where_its_own_file_says(tmp_path):
    message = problems(tmp_path, indicators=(("A", "P1", "C1"), ("B", "P2", "C2"), ("C", "P2", "C2")))
    assert "indicator B sits under P1/C1 here but its own file says P2/C2" in message


def test_unknown_unplaced_and_doubly_placed_indicators_are_all_reported(tmp_path):
    items = [*GOOD[:3], item("C1", "Category", ["A", "B", "Z"]), item("C2", "Category", ["A"])]
    message = problems(tmp_path, items=items)
    assert "category C1 lists unknown indicator Z" in message
    assert "indicator A is listed under both C1 and C2" in message
    assert "indicator C is not listed under any category" in message


def test_malformed_items_are_reported(tmp_path):
    items = [*GOOD[:4], {**GOOD[4], "item_type": "Indicator", "children": [], "weight": 2}]
    message = problems(tmp_path, items=items)
    assert "unknown key items[4].'weight'" in message
    assert "'item_type' must be one of" in message
    assert "'children' must be a non-empty list of distinct codes" in message
