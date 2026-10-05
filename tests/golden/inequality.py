"""Shared loading for the Inequality parity tests: the committed WID and
World Bank fixtures presented to the ingestion runner the way their clients
would, and the canonical observations that result. No network."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

FIXTURES = Path(__file__).parents[1] / "fixtures"
WID_DIRECTORY = FIXTURES / "wid"
WB_FIXTURE = FIXTURES / "wb" / "SI.POV.GINI_sample.json"
WID_DATASETS = ("WID_NINCSH_PRETAX_P90P100", "WID_NINCSH_PRETAX_P0P50")
WB_DATASET = "WB_GINIPT"


@cache
def wid_archive() -> dict[str, str]:
    """The committed country files, by archive member name."""
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(WID_DIRECTORY.glob("WID_*.csv"))}


@cache
def wb_rows() -> tuple[dict, ...]:
    return tuple(json.loads(WB_FIXTURE.read_text())[1])


class FixtureClients:
    """Stands in for ``WIDClient`` and ``WorldBankClient``; counts fetches."""

    def __init__(self) -> None:
        self.fetches: list[tuple[str, str]] = []

    def fetch_archive(self, archive: str) -> dict[str, str]:
        self.fetches.append(("WID", archive))
        return wid_archive()

    def fetch_indicator(self, indicator: str) -> list[dict]:
        self.fetches.append(("WB", indicator))
        return list(wb_rows())


@cache
def normalized(codes: tuple[str, ...] = WID_DATASETS + (WB_DATASET,)):
    """``{dataset code: NormalizationResult}`` for the requested datasets, through the ingestion runner."""
    catalog = MetadataCatalog.load()
    results, _ = fetch_and_normalize(resolve_datasets(list(codes), catalog), FixtureClients(), metadata=catalog)
    return {dataset.code: result for dataset, result in results}


def wid_observations() -> tuple[Observation, ...]:
    results = normalized()
    return tuple(o for code in WID_DATASETS for o in results[code].observations)


def wb_observations() -> tuple[Observation, ...]:
    return tuple(normalized()[WB_DATASET].observations)
