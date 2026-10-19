"""The researcher guide's Infrastructure workflow must work from an empty
database: its ingest list is exactly the datasets the three executable leaf
indicators read, its dependency table agrees, it runs and queries the two,
and it says plainly that INTRNT and TRNETW cannot be run and that
AQELEC ends in 2017. No database, no network: the
example itself is executed by tests/db/test_infrastructure_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Infrastructure category (`INF`)"
INDICATORS = ("AQELEC", "SANSRV", "DRKWAT")
BLOCKED = ("INTRNT", "TRNETW")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def infrastructure_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Infrastructure section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", infrastructure_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_three_indicators_read():
    documented = documented_datasets()
    assert documented == required_datasets() == ("WB_AVELEC", "WEF_QUELEC", "WB_SANSRV", "WB_DRKWAT")
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_the_three():
    example = infrastructure_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["AQELEC", "SANSRV", "DRKWAT"]' in example and 'countries=["MYS", "AUT", "USA"]' in example and "years=(2010, 2023)" in example and "result = sspi.query(" in example and "print(result)" in example
    assert not any(code in example for code in BLOCKED)  # never published as runnable


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_infrastructure_leaf_and_says_which_are_blocked():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "INF"}
    assert leaves == {*INDICATORS, *BLOCKED} and set(INDICATORS) <= set(registry.codes()) and not set(BLOCKED) & set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "Three are executable" in text and "cannot be run" in text
    assert "no Infrastructure\ncategory score is computed" in text and all(c in text for c in ("AQELEC-1", "INTRNT-1", "TRNETW-1", "GOV-2")) and "no AQELEC score after 2017" in text


def test_the_blocked_indicators_and_their_datasets_raise_clear_errors():
    catalog = MetadataCatalog.load()
    blocked_datasets = {code for indicator in BLOCKED for code in catalog.indicator(indicator).dataset_codes}
    assert blocked_datasets == {"UNSDG_AVINTR", "CABLE_QUINTR", "WB_RAILNT", "CIA_ROADNT"}
    assert not blocked_datasets & (set(SUPPORTED_DATASETS) | set(UNAVAILABLE_SOURCES))
    sspi = SSPI("postgresql+psycopg://nobody@localhost:1/none")  # never connected: both refuse before any database use
    for code in sorted(blocked_datasets):
        with pytest.raises(NotIngestibleError):
            sspi.ingest([code])
    for code in BLOCKED:
        with pytest.raises(UnknownCodeError):
            sspi.run(code)
