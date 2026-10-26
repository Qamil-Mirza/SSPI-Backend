"""The researcher guide's Global Role workflow must work from an empty
database: its ingest list is exactly the datasets the two registered leaf
indicators read, its dependency table agrees, it runs and queries them, and
it states what a researcher must know, including that ARMEXP has observed
scores only and that MILEXP and FORAID cannot run. No database, no
network: the example itself is executed by tests/db/test_global_role_end_to_end.py."""

import re
from pathlib import Path

import pytest

from sspi.errors import NotIngestibleError, UnknownCodeError
from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.ingestion.runner import resolve_datasets
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Global Role category (`GLB`)"
INDICATORS = ("ARMEXP", "RDFUND")
BLOCKED = ("MILEXP", "FORAID")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def example() -> str:
    return re.search(r"From a fresh, empty database:\n\n```python\n(.*?)```", section(), re.DOTALL).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", example(), re.DOTALL).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_two_indicators_read():
    assert documented_datasets() == required_datasets() == ("SIPRI_ARMEXP", "UNSDG_RDPGDP", "UNSDG_NRSRCH")
    catalog = MetadataCatalog.load()
    assert set(documented_datasets()) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes} and set(documented_datasets()) <= set(SUPPORTED_DATASETS)


def test_the_example_runs_and_queries_the_two_and_warns_about_armexp():
    text = example()
    assert text.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in text
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', text) == ["RDFUND", "ARMEXP"] and "observed scores only" in text
    assert 'indicators=["ARMEXP", "RDFUND"]' in text and 'countries=["MYS", "AUT", "USA"]' in text and "years=(2010, 2023)" in text and "print(results)" in text


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_global_role_leaf_and_what_to_know():
    leaves = {i.code for i in MetadataCatalog.load().indicators() if i.category_code == "GLB"}
    assert leaves == set(INDICATORS) | set(BLOCKED)
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "no Global Role category score is" in text and "Global Role is not complete" in text
    for entry in ("ARMEXP-1", "ARMEXP-2", "ARMEXP-3", "RDFUND-1", "RDFUND-2", "RDFUND-3", "MILEXP-1", "MILEXP-3", "FORAID-1", "FORAID-3", "GOV-7"):
        assert entry in text, entry


@pytest.mark.parametrize("code", BLOCKED)
def test_the_blocked_leaves_are_unregistered_and_their_own_datasets_not_ingestible(code):
    with pytest.raises(UnknownCodeError, match=code):
        registry.get(code)
    catalog = MetadataCatalog.load()
    for dataset in catalog.indicator(code).dataset_codes:
        if dataset == "WB_POPULN":  # ingestible for BEEFMK and GTRANS
            continue
        with pytest.raises(NotIngestibleError):
            resolve_datasets([dataset], catalog)
