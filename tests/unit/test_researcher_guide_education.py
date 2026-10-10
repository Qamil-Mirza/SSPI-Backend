"""The researcher guide's Education workflow must work from an empty
database: its ingest list is exactly the datasets the four Education leaf
indicators read, its dependency table agrees, and it runs and queries all
four, the whole category. No database, no network: the example itself is
executed by tests/db/test_education_end_to_end.py."""

import re
from pathlib import Path

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Education category (`EDU`)"
INDICATORS = ("ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def education_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Education section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", education_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in registry.get(indicator).dataset_codes))


def test_the_example_ingests_exactly_the_four_indicators_dependencies():
    documented = documented_datasets()
    assert documented == ("UIS_ENRPRI", "UIS_ENRSEC", "WB_PUPTCH", "UIS_YRSEDU") == required_datasets()
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_all_four():
    example = education_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU"]' in example and "years=(2010, 2023)" in example and "print(education)" in example


def test_the_dependency_table_matches_the_definitions():
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(re.findall(r"`([A-Z0-9_]+_[A-Z0-9_]+)`", row.split("|")[2]))
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_example_covers_every_education_leaf_indicator_in_the_catalog():
    catalog = MetadataCatalog.load()
    assert {i.code for i in catalog.indicators() if i.category_code == "EDU"} == set(INDICATORS) <= set(registry.codes())
    assert "has four leaf indicators, all executable" in section()
