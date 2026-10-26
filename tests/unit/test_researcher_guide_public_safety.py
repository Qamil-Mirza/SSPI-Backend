"""The researcher guide's Public Safety workflow must work from an empty
database: its ingest list is exactly the datasets the four leaf indicators
read, its dependency table agrees, it runs and queries the four, and it
states the corrections and gaps a researcher must know. No database, no
network: the example itself is executed by
tests/db/test_public_safety_end_to_end.py."""

import re
from pathlib import Path

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.metadata import MetadataCatalog

GUIDE = (Path(__file__).parents[2] / "docs" / "researcher-guide.md").read_text(encoding="utf-8")
HEADING = "The Public Safety category (`SAF`)"
INDICATORS = ("MURDER", "CYBSEC", "SECAPP", "PRISON")


def section() -> str:
    start = GUIDE.index(HEADING)
    return GUIDE[start : GUIDE.index("A run is a full replacement", start)]


def public_safety_example() -> str:
    """The fenced code block that follows 'from a fresh, empty database:' in the Public Safety section."""
    return re.search(r"from a fresh, empty database:\n\n```python\n(.*?)```", section(), re.S).group(1)


def documented_datasets() -> tuple[str, ...]:
    ingest = re.search(r"sspi\.ingest\(\[(.*?)\]\)", public_safety_example(), re.S).group(1)
    return tuple(re.findall(r'"([A-Z0-9_]+)"', re.sub(r"#.*", "", ingest)))


def required_datasets() -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for indicator in INDICATORS for code in (*registry.get(indicator).dataset_codes, *registry.get(indicator).auxiliary_datasets)))


def test_the_example_ingests_exactly_what_the_four_indicators_read():
    documented = documented_datasets()
    assert documented == required_datasets() == ("WB_MURDER", "ITU_CYBSEC", "FSI_SECAPP", "UNODC_PRIPOP")
    catalog = MetadataCatalog.load()
    assert set(documented) == {code for indicator in INDICATORS for code in catalog.indicator(indicator).dataset_codes}
    assert set(documented) <= set(SUPPORTED_DATASETS)


def test_the_example_is_self_contained_and_runs_and_queries_the_four():
    example = public_safety_example()
    assert example.startswith("from sspi import SSPI\n") and "sspi = SSPI()" in example
    assert re.findall(r'sspi\.run\("([A-Z]+)"\)', example) == list(INDICATORS)
    assert 'indicators=["MURDER", "CYBSEC", "SECAPP", "PRISON"]' in example and 'countries=["MYS", "AUT", "USA"]' in example and "years=(2010, 2023)" in example and "print(results)" in example
    assert "local-data/itu/gci-local-indicator-summary.csv" in section()  # the one source that is not downloaded


def test_the_dependency_table_matches_the_definitions():
    datasets = {d.code for d in MetadataCatalog.load().datasets()}
    for indicator in INDICATORS:
        (row,) = [line for line in section().splitlines() if line.startswith(f"| `{indicator}` |")]
        listed = tuple(code for code in re.findall(r"`([A-Z0-9_]+)`", row.split("|")[2]) if code in datasets)
        assert listed == registry.get(indicator).dataset_codes, indicator


def test_the_section_names_every_public_safety_leaf_and_what_to_know():
    catalog = MetadataCatalog.load()
    leaves = {i.code for i in catalog.indicators() if i.category_code == "SAF"}
    assert leaves == set(INDICATORS) and set(INDICATORS) <= set(registry.codes())
    text = section()
    assert all(f"`{code}`" in text for code in leaves) and "all\nexecutable" in text and "no Public Safety category\nscore is computed" in text
    assert "Canada is not in the transcription" in text and "North Korea" in text
    for entry in ("MURDER-1", "MURDER-2", "PRISON-1", "PRISON-2", "PRISON-3", "PRISON-4", "CYBSEC-1", "CYBSEC-2", "CYBSEC-3", "SECAPP-1", "SECAPP-2", "SECAPP-3", "GOV-3", "GOV-4", "GOV-5"):
        assert entry in text, entry
