"""Shared loading for the Worker Engagement parity tests: the committed ILO
SDMX-JSON responses presented to the ingestion runner the way ``ILOClient``
would, and the canonical observations that result. No network."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

ILO_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "ilo"
# indicator -> (its dataset, the committed response of the dataset's canonical query)
CASES = {
    "EMPLOY": ("ILO_EMPLOY_TO_POP", "DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json"),
    "COLBAR": ("ILO_COLBAR", "DF_ILR_CBCT_NOC_RT.json"),
}
DATASETS = tuple(dataset for dataset, _ in CASES.values())


@cache
def responses() -> dict[str, dict]:
    """The committed responses, by canonical query code."""
    catalog = MetadataCatalog.load()
    return {catalog.dataset(dataset).source.query_code: json.loads((ILO_DIRECTORY / name).read_text(encoding="utf-8")) for dataset, name in CASES.values()}


class FixtureClient:
    """Stands in for ``ILOClient``; counts fetches."""

    def __init__(self) -> None:
        self.fetches: list[str] = []

    def fetch_query(self, query_code: str) -> dict:
        self.fetches.append(query_code)
        return responses()[query_code]


@cache
def normalized():
    """``{dataset code: NormalizationResult}`` for both datasets, through the ingestion runner."""
    catalog = MetadataCatalog.load()
    results, _ = fetch_and_normalize(resolve_datasets(list(DATASETS), catalog), FixtureClient(), metadata=catalog)
    return {dataset.code: result for dataset, result in results}


def observations(indicator: str) -> tuple[Observation, ...]:
    return tuple(normalized()[CASES[indicator][0]].observations)
