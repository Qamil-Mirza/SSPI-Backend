"""The researcher guide's Worker Wellbeing workflow must work from an empty
database: its ingest list is exactly the datasets the two executable leaf
indicators read, its dependency table agrees, it runs and queries both, and
it says plainly that MATERN and SENIOR cannot be run. No database, no
network: the example itself is executed by
tests/db/test_worker_wellbeing_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi import SSPI
from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Worker Wellbeing category (`WWB`)"
INDICATORS = ("UNEMPB", "FATINJ")
BLOCKED = ("MATERN", "SENIOR")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def wellbeing_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Worker Wellbeing section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", wellbeing_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in registry.get(indicator).dataset_codes))


def test_the_example_ingests_exactly_the_two_indicators_dependencies():
    documented = documented_datasets()
    assert documented == required_datasets() == ("UNSDG_BENFTS_UNEMP", "ILO_FATINJ")
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_both():
    example = wellbeing_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["UNEMPB", "FATINJ"]' in example and "years=(2010, 2023)" in example and "print(wellbeing)" in example
    assert not any(code in example for code in BLOCKED)  # never published as runnable


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)  # not the source's own series codes
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_wellbeing_leaf_and_says_which_are_blocked():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "WWB"}
    assert leaves == {*INDICATORS, *BLOCKED} and set(INDICATORS) <= set(registry.codes()) and not set(BLOCKED) & set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "Two are executable" in text and "cannot be run" in text
    assert "no Worker\nWellbeing category score is computed" in text and "`UNEMPL`" in text  # the old code is explained, not aliased


def test_the_blocked_indicators_and_their_datasets_raise_clear_errors():
    catalog = MetadataCatalog.load()
    blocked_datasets = {code for indicator in BLOCKED for code in catalog.indicator(indicator).dataset_codes}
    assert blocked_datasets == {"OECD_MATERN", "OECD_POVNRT", "OECD_YRSRTM", "OECD_YRSRTW"}
    assert not blocked_datasets & (set(SUPPORTED_DATASETS) | set(UNAVAILABLE_SOURCES))
    sspi = SSPI("postgresql+psycopg://nobody@localhost:1/none")  # never connected: both refuse before any database use
    for code in sorted(blocked_datasets):
        with pytest.raises(NotIngestibleError, match="no ingestion path yet"):
            sspi.ingest([code])
    for code in BLOCKED:
        with pytest.raises(UnknownCodeError):
            sspi.run(code)
