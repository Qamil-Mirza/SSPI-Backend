"""Shared offline source for the Financial Sector golden tests: the committed
World Bank samples served in place of ``WorldBankClient``."""

import json
from functools import cache
from pathlib import Path

from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import MetadataCatalog

WB = Path(__file__).parents[1] / "fixtures" / "wb"
SERIES = {"WB_CREDIT": "FS.AST.PRVT.GD.ZS", "WB_DPOSIT": "GFDD.OI.02", "WB_PUBACC": "FX.OWN.TOTL.ZS"}
CATALOG = MetadataCatalog.load()


@cache
def rows(series):
    return json.loads((WB / f"{series}_sample.json").read_text(encoding="utf-8"))[1]


class FixtureClient:
    """Stands in for ``WorldBankClient``; serves the committed samples and counts fetches."""

    def __init__(self):
        self.fetches = []

    def fetch_indicator(self, indicator):
        self.fetches.append(indicator)
        return rows(indicator)

    def close(self):
        pass


@cache
def normalized():
    """Dataset code -> NormalizationResult for the three datasets, one fetch each."""
    client = FixtureClient()
    results, fetches = fetch_and_normalize(resolve_datasets(list(SERIES), CATALOG), client, metadata=CATALOG)
    assert client.fetches == list(SERIES.values()) and fetches == tuple(SERIES.values())
    return {dataset.code: result for dataset, result in results}
