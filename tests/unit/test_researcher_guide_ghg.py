"""The researcher guide's Greenhouse Gases workflow must work from an empty
database: its ingest list is exactly the datasets the three indicators read,
its dependency table agrees, and it runs and queries all three. No database,
no network: the example itself is executed by tests/db/test_ghg_end_to_end.py."""

import re
from pathlib import Path

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
INDICATORS = ("BEEFMK", "COALPW", "GTRANS")


def ghg_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Greenhouse Gases section."""
    section = GUIDE[GUIDE.index("The Greenhouse Gases category (`GHG`)") :]
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section, re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", ghg_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in registry.get(indicator).dataset_codes))


def test_the_example_ingests_exactly_the_three_indicators_dependencies():
    documented = documented_datasets()
    assert len(documented) == len(set(documented)) == 11
    assert documented == required_datasets()
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_all_three():
    example = ghg_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["BEEFMK", "COALPW", "GTRANS"]' in example and "print(ghg)" in example


def test_the_dependency_table_matches_the_definitions():
    section = GUIDE[GUIDE.index("The Greenhouse Gases category (`GHG`)") : GUIDE.index("From a fresh, empty database:")]
    for indicator in INDICATORS:
        (row,) = [line for line in section.splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(re.findall(r"`([A-Z0-9_]+_[A-Z0-9_]+)`", row.split("|")[2]))
        assert listed == registry.get(indicator).dataset_codes, indicator
