"""The researcher guide's Tax workflow must work from an empty database: its
ingest list is exactly the datasets the three Tax leaf indicators read, its
dependency table agrees, and it runs and queries all three, the whole
category at leaf level. No database, no network: the example itself is
executed by tests/db/test_tax_end_to_end.py."""

import re
from pathlib import Path

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Tax category (`TAX`)"
INDICATORS = ("CRPTAX", "TAXREV", "TXRDST")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def tax_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Tax section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", tax_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in registry.get(indicator).dataset_codes))


def test_the_example_ingests_exactly_the_three_indicators_dependencies():
    documented = documented_datasets()
    assert set(documented) == set(required_datasets()) and len(documented) == len(set(documented)) == 6
    assert documented[:2] == ("TF_CRPTAX", "WB_TAXREV") and set(documented[2:]) == set(registry.get("TXRDST").dataset_codes)
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_all_three():
    example = tax_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["CRPTAX", "TAXREV", "TXRDST"]' in example and "years=(2010, 2023)" in example and "print(taxes)" in example


def test_the_dependency_table_matches_the_definitions():
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(re.findall(r"`([A-Z0-9_]+_[A-Z0-9_]+)`", row.split("|")[2]))
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_example_covers_every_tax_leaf_indicator_in_the_catalog():
    catalog = MetadataCatalog.load()
    assert {i.code for i in catalog.indicators() if i.category_code == "TAX"} == set(INDICATORS) <= set(registry.codes())
    assert "has three leaf indicators, all executable" in section() and "January 2025" in section()
