"""The researcher guide's Rights workflow must work from an empty database:
its ingest list is exactly the datasets the two executable leaf indicators
read, its dependency table agrees, it runs and queries the two, and it
states what a researcher must know, including the three leaves that cannot
run. No database, no network: the example itself is executed by
tests/db/test_rights_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.ingestion.runner import resolve_datasets
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Rights category (`RTS`)"
INDICATORS = ("RULELW", "EDEMOC")
BLOCKED = ("PUBSRV", "UNCONV", "GENDEQ")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def rights_example() -> str:
    """The fenced code block that follows 'From a fresh, empty database:' in the Rights section."""
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", rights_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_two_indicators_read():
    documented = documented_datasets()
    assert documented == required_datasets() == ("VDEM_RULELW", "VDEM_EDEMOC")
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_the_two():
    example = rights_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["RULELW", "EDEMOC"]' in example and 'countries=["MYS", "AUT", "USA"]' in example and "years=(2010, 2023)" in example and "print(results)" in example


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_rights_leaf_and_what_to_know():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "RTS"}
    assert leaves == set(INDICATORS) | set(BLOCKED) and set(INDICATORS) <= set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "no Rights category score is" in text and "version 13" in text and "Two of the five are migrated" in text and "Rights is not complete" in text
    for entry in ("RULELW-1", "RULELW-2", "RULELW-3", "EDEMOC-1", "EDEMOC-2", "EDEMOC-3", "PUBSRV-1", "UNCONV-1", "GENDEQ-1", "GOV-6"):
        assert entry in text, entry


@pytest.mark.parametrize("code", BLOCKED)
def test_the_blocked_leaves_are_unregistered_and_their_datasets_not_ingestible(code):
    with pytest.raises(UnknownCodeError, match=code):
        registry.get(code)
    catalog = MetadataCatalog.load()
    for dataset in catalog.indicator(code).dataset_codes:
        assert dataset not in SUPPORTED_DATASETS
        with pytest.raises(NotIngestibleError):
            resolve_datasets([dataset], catalog)
