"""Shared offline sources for the Global Role golden tests: the committed
synthetic SIPRI arms-transfers answer and the committed verbatim UN SDG
samples for indicators 9.5.1 and 9.5.2, served in place of the source
clients."""

import importlib.util
import json
from functools import cache
from pathlib import Path

from sspi.indicators import compute_indicator, registry
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.sipri import MILEX_WORKBOOKS, QUERIES, SIPRIResponse
from sspi.ingestion.workbooks import WorkbookFile
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures"
ARMS = FIXTURES / "sipri" / "armstransfers_synthetic.json"
MILEX = FIXTURES / "sipri" / "milex_synthetic.json"
MILEX_BOOK = FIXTURES / "sipri" / "milex_workbook_synthetic.xlsx"
UNSDG = {"9.5.1": FIXTURES / "unsdg" / "9_5_1_sample.json", "9.5.2": FIXTURES / "unsdg" / "9_5_2_sample.json"}
CATALOG = MetadataCatalog.load()


def builder():
    """``tests/fixtures/sipri/build_synthetic.py``, loaded under its own module name."""
    spec = importlib.util.spec_from_file_location("sipri_build_synthetic", FIXTURES / "sipri" / "build_synthetic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arms_response(content: bytes) -> SIPRIResponse:
    return SIPRIResponse("armstransfers", QUERIES["armstransfers"], content)


class FixtureSources:
    """Stands in for the SIPRI and UN SDG clients; serves the committed fixtures and records each fetch."""

    def __init__(self):
        self.fetches = []

    def fetch(self, key):
        self.fetches.append(key)
        if key in MILEX_WORKBOOKS:
            return WorkbookFile(key, MILEX_WORKBOOKS[key], "synthetic fixture", MILEX_BOOK.read_bytes())
        assert key == "armstransfers"
        return arms_response(ARMS.read_bytes())

    def fetch_indicator(self, indicator):
        self.fetches.append(indicator)
        return json.loads(UNSDG[indicator].read_text())["data"]

    def close(self):
        pass


@cache
def normalized():
    """Dataset code -> NormalizationResult for the four datasets."""
    sources = FixtureSources()
    codes = ["SIPRI_ARMEXP", "SIPRI_MILEXP", "UNSDG_RDPGDP", "UNSDG_NRSRCH"]
    results, fetches = fetch_and_normalize(resolve_datasets(codes, CATALOG), {"SIPRI": sources, "UNSDG": sources}, metadata=CATALOG)
    assert fetches == ("armstransfers", "SIPRI-Milex-data-1949-2025_v1.2", "9.5.1", "9.5.2") == tuple(sources.fetches)
    return {dataset.code: result for dataset, result in results}


@cache
def run(indicator):
    definition = registry.get(indicator)
    observations = [o for code in definition.dataset_codes for o in normalized()[code].observations]
    return compute_indicator(definition, observations)
