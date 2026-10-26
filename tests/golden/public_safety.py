"""Shared offline sources for the Public Safety golden tests: the committed
World Bank sample, the synthetic UNODC workbook, the synthetic GCI
transcription and the synthetic FSI workbooks, served in place of the four
source clients."""

import hashlib
import importlib.util
import json
from functools import cache
from pathlib import Path

from sspi.indicators import compute_indicator, registry
from sspi.ingestion.fsi import FSIEditions, FSIWorkbook, SourceWorkbook as FSISourceWorkbook
from sspi.ingestion.localfiles import LOCAL_FILES, LocalFile
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.unodc import WORKBOOKS, UNODCWorkbook
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures"
WB_SAMPLE = FIXTURES / "wb" / "VC.IHR.PSRC.P5_sample.json"
UNODC_WORKBOOK = FIXTURES / "unodc" / "data_cts_prisons_and_prisoners_synthetic.xlsx"
ITU_TRANSCRIPTION = FIXTURES / "itu" / "gci-local-indicator-summary_synthetic.csv"
UNODC_KEY = "data_cts_prisons_and_prisoners_2026-09-30"
ITU_KEY = "gci-local-indicator-summary"
FSI_KEY = "fsi-excel_2006-2023"
FSI_EDITIONS = (2018, 2021, 2023)
CATALOG = MetadataCatalog.load()


def builder(organization):
    """``tests/fixtures/<organization>/build_synthetic.py``, loaded under its own module name."""
    spec = importlib.util.spec_from_file_location(f"{organization}_build_synthetic", FIXTURES / organization / "build_synthetic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unodc_workbook(content: bytes) -> UNODCWorkbook:
    return UNODCWorkbook(UNODC_KEY, WORKBOOKS[UNODC_KEY], hashlib.sha256(content).hexdigest(), content)


def itu_file(content: bytes) -> LocalFile:
    return LocalFile(ITU_KEY, LOCAL_FILES[ITU_KEY], str(ITU_TRANSCRIPTION), hashlib.sha256(content).hexdigest(), content)


def fsi_workbook_path(edition: int) -> Path:
    return FIXTURES / "fsi" / f"fsi-{edition}_synthetic.xlsx"


def fsi_editions(contents: dict[int, bytes] | None = None) -> FSIEditions:
    """The synthetic editions as one edition set (``contents`` replaces some editions' bytes, for variants)."""
    workbooks = []
    for edition in FSI_EDITIONS:
        content = (contents or {}).get(edition) or fsi_workbook_path(edition).read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        workbooks.append(FSIWorkbook(FSISourceWorkbook(edition, f"https://fsi.invalid/fsi-{edition}_synthetic.xlsx", sha256), sha256, content))
    return FSIEditions(FSI_KEY, tuple(workbooks))


class FixtureSources:
    """Stands in for the World Bank, UNODC and local-file clients; serves the committed fixtures and records each fetch."""

    def __init__(self):
        self.fetches = []

    def fetch_indicator(self, indicator):
        self.fetches.append(indicator)
        assert indicator == "VC.IHR.PSRC.P5"
        return json.loads(WB_SAMPLE.read_text(encoding="utf-8"))[1]

    def fetch_workbook(self, key):
        self.fetches.append(key)
        return unodc_workbook(UNODC_WORKBOOK.read_bytes())

    def fetch_file(self, key):
        self.fetches.append(key)
        return itu_file(ITU_TRANSCRIPTION.read_bytes())

    def fetch_editions(self, key):
        self.fetches.append(key)
        return fsi_editions()

    def close(self):
        pass


@cache
def normalized():
    """Dataset code -> NormalizationResult for the four datasets, one fetch each."""
    sources = FixtureSources()
    codes = ["WB_MURDER", "ITU_CYBSEC", "FSI_SECAPP", "UNODC_PRIPOP"]
    results, fetches = fetch_and_normalize(resolve_datasets(codes, CATALOG), {"WB": sources, "ITU": sources, "FSI": sources, "UNODC": sources}, metadata=CATALOG)
    assert fetches == ("VC.IHR.PSRC.P5", ITU_KEY, FSI_KEY, UNODC_KEY) == tuple(sources.fetches)
    return {dataset.code: result for dataset, result in results}


@cache
def run(indicator):
    definition = registry.get(indicator)
    (code,) = definition.dataset_codes
    return compute_indicator(definition, normalized()[code].observations)
