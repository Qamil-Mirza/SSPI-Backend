"""The researcher guide's Healthcare workflow must work from an empty
database: its ingest list is exactly the datasets the four executable leaf
indicators read (their datasets and CSTUNT's auxiliary predictor), its
dependency table agrees, it runs and queries the four, and it says plainly
that FAMPLN cannot be run. No database, no network: the example itself is
executed by tests/db/test_healthcare_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Healthcare category (`HLC`)"
INDICATORS = ("CSTUNT", "ATBRTH", "DPTCOV", "PHYSPC")
BLOCKED = ("FAMPLN",)


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def healthcare_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Healthcare section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", healthcare_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    """Every dataset a run reads: the definition's datasets, then its strategy's auxiliary datasets."""
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_four_indicators_read():
    documented = documented_datasets()
    assert documented == required_datasets() == ("UNSDG_CSTUNT", "WB_GDP_PERCAP_CURPRICE_USD", "WHO_ATBRTH", "WHO_DPTCOV", "WHO_PHYSPC")
    for indicator in ("ATBRTH", "DPTCOV", "PHYSPC"):
        assert catalog_dependencies(indicator) == registry.get(indicator).dataset_codes
    assert catalog_dependencies("CSTUNT") == ("UNSDG_CSTUNT",)  # the predictor is an impute-route input, not a catalog dependency
    assert set(documented) <= set(SUPPORTED_DATASETS)


def catalog_dependencies(indicator):
    return MetadataCatalog.load().indicator(indicator).dataset_codes


def test_the_example_is_self_contained_and_runs_and_queries_the_four():
    example = healthcare_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["CSTUNT", "ATBRTH", "DPTCOV", "PHYSPC"]' in example and 'countries=["MYS", "AUT", "USA"]' in example and "years=(2010, 2023)" in example and "print(healthcare)" in example
    assert not any(code in example for code in BLOCKED)  # never published as runnable


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)  # not the source's own series codes
        definition = registry.get(indicator)
        assert listed == (*definition.dataset_codes, *definition.auxiliary_datasets), indicator


def test_the_section_names_every_healthcare_leaf_and_says_which_are_blocked():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "HLC"}
    assert leaves == {*INDICATORS, *BLOCKED} and set(INDICATORS) <= set(registry.codes()) and not set(BLOCKED) & set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "Four are executable" in text and "cannot be run" in text
    assert "no Healthcare\ncategory score is computed" in text and "FAMPLN-1" in text


def test_the_blocked_indicator_and_its_dataset_raise_clear_errors():
    catalog = MetadataCatalog.load()
    blocked_datasets = {code for indicator in BLOCKED for code in catalog.indicator(indicator).dataset_codes}
    assert blocked_datasets == {"WHO_FAMPLN"}  # an approved source; the block is the methodology decision (FAMPLN-1)
    assert {catalog.dataset(code).source.organization_code for code in blocked_datasets} == {"WHO"}
    assert not blocked_datasets & (set(SUPPORTED_DATASETS) | set(UNAVAILABLE_SOURCES))
    sspi = SSPI("postgresql+psycopg://nobody@localhost:1/none")  # never connected: both refuse before any database use
    for code in sorted(blocked_datasets):
        with pytest.raises(NotIngestibleError, match="no ingestion path yet"):
            sspi.ingest([code])
    for code in BLOCKED:
        with pytest.raises(UnknownCodeError):
            sspi.run(code)
