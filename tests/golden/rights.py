"""Shared offline source for the Rights golden tests: the committed synthetic
V-Dem archive, served in place of the V-Dem client, as fetched on
:data:`EVALUATION_DATE` (the date the golden files were generated for)."""

import hashlib
import importlib.util
from datetime import date
from functools import cache
from pathlib import Path

from sspi.indicators import compute_indicator, registry
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.vdem import SourceArchive, VDemArchive
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures"
VDEM_ARCHIVE = FIXTURES / "vdem" / "V-Dem-CY-FullOthers_csv_v13_synthetic.zip"
VDEM_KEY = "V-Dem-CY-FullOthers_csv_v13"
EVALUATION_DATE = date(2026, 10, 26)  # generate_rights_cases.EVALUATION_DATE
INDICATORS = {"RULELW": "VDEM_RULELW", "EDEMOC": "VDEM_EDEMOC"}
CATALOG = MetadataCatalog.load()


def builder():
    """``tests/fixtures/vdem/build_synthetic.py``, loaded under its own module name."""
    spec = importlib.util.spec_from_file_location("vdem_build_synthetic", FIXTURES / "vdem" / "build_synthetic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vdem_archive(content: bytes, evaluation_year: int = EVALUATION_DATE.year, member: str | None = None) -> VDemArchive:
    """The synthetic archive (or a variant's bytes) as the client would return it, unpinned, for one run year."""
    source = SourceArchive("synthetic V-Dem archive (tests)", "https://v-dem.invalid/V-Dem-CY-FullOthers_csv_v13_synthetic.zip", None, member)
    return VDemArchive(VDEM_KEY, source, hashlib.sha256(content).hexdigest(), content, evaluation_year)


class FixtureSources:
    """Stands in for the V-Dem client; serves the committed archive and records each fetch."""

    def __init__(self, evaluation_year: int = EVALUATION_DATE.year):
        self.fetches, self.evaluation_year = [], evaluation_year

    def fetch_archive(self, key):
        self.fetches.append(key)
        assert key == VDEM_KEY
        return vdem_archive(VDEM_ARCHIVE.read_bytes(), self.evaluation_year)

    def close(self):
        pass


@cache
def normalized():
    """Dataset code -> NormalizationResult for the two datasets, one fetch for both."""
    sources = FixtureSources()
    results, fetches = fetch_and_normalize(resolve_datasets(list(INDICATORS.values()), CATALOG), {"VDEM": sources}, metadata=CATALOG)
    assert fetches == (VDEM_KEY,) == tuple(sources.fetches)
    return {dataset.code: result for dataset, result in results}


@cache
def run(indicator):
    definition = registry.get(indicator)
    (code,) = definition.dataset_codes
    return compute_indicator(definition, normalized()[code].observations)
