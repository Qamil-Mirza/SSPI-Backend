"""The researcher guide's Financial Sector workflow must work from an empty
database: its ingest list is exactly the datasets the two executable leaf
indicators read, its dependency table agrees, it runs and queries the two,
and it says plainly that FSTABL cannot be run. No database, no network: the
example itself is executed by tests/db/test_financial_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Financial Sector category (`FIN`)"
INDICATORS = ("FDEPTH", "PUBACC")
BLOCKED = ("FSTABL",)


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def financial_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Financial Sector section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", financial_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_two_indicators_read():
    documented = documented_datasets()
    assert documented == required_datasets() == ("WB_CREDIT", "WB_DPOSIT", "WB_PUBACC")
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_the_two():
    example = financial_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["FDEPTH", "PUBACC"]' in example and 'countries=["MYS", "AUT", "USA"]' in example and "years=(2010, 2023)" in example and "print(results)" in example
    assert not any(code in example for code in BLOCKED)  # never published as runnable


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_financial_leaf_and_says_which_is_blocked():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "FIN"}
    assert leaves == {*INDICATORS, *BLOCKED} and set(INDICATORS) <= set(registry.codes()) and not set(BLOCKED) & set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "Two are executable" in text and "cannot be run" in text
    assert "no Financial Sector\ncategory score is computed" in text and "FSTABL-1" in text and "FDEPTH-1" in text


def test_the_blocked_indicator_and_its_dataset_raise_clear_errors():
    catalog = MetadataCatalog.load()
    blocked_datasets = {code for indicator in BLOCKED for code in catalog.indicator(indicator).dataset_codes}
    assert blocked_datasets == {"IMF_FSTABL"} and type(catalog.dataset("IMF_FSTABL")).__name__ == "UnresolvedDataset"  # no legacy definition at all
    assert not blocked_datasets & (set(SUPPORTED_DATASETS) | set(UNAVAILABLE_SOURCES))
    sspi = SSPI("postgresql+psycopg://nobody@localhost:1/none")  # never connected: both refuse before any database use
    with pytest.raises(NotIngestibleError, match="no complete definition"):
        sspi.ingest(["IMF_FSTABL"])
    with pytest.raises(UnknownCodeError):
        sspi.run("FSTABL")
