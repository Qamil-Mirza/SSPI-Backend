"""Shared loading for the Energy parity tests: the committed UN SDG pivot
rows for NRGINT and AIRPOL, the committed IEA ``TESbySource`` rows for
ALTNRG, and the canonical observations that result. No network."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from sspi.ingestion.iea import normalize_iea_dataset
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

UNSDG_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "unsdg"
# indicator -> (its dataset, the SDG indicator queried, the committed sample of that query)
CASES = {
    "NRGINT": ("UNSDG_NRGINT", "7.3.1", "7_3_1_sample.json"),
    "AIRPOL": ("UNSDG_AIRPOL", "11.6.2", "11_6_2_sample.json"),
}
DATASETS = tuple(dataset for dataset, _, _ in CASES.values())


@cache
def rows(indicator: str) -> tuple[dict, ...]:
    """The committed pivot rows of the indicator's SDG query, in source order."""
    return tuple(json.loads((UNSDG_DIRECTORY / CASES[indicator][2]).read_text(encoding="utf-8"))["data"])


@cache
def normalized(indicator: str):
    return normalize_unsdg_dataset(MetadataCatalog.load().dataset(CASES[indicator][0]), rows(indicator))


def observations(indicator: str):
    return tuple(normalized(indicator).observations)


IEA_FIXTURE = Path(__file__).parents[1] / "fixtures" / "iea" / "TESbySource_sample.json"
ALTNRG_DATASETS = ("IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP", "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL")


@cache
def iea_rows() -> tuple[dict, ...]:
    """The committed rows of IEA indicator ``TESbySource``, in source order."""
    return tuple(json.loads(IEA_FIXTURE.read_text(encoding="utf-8")))


@cache
def iea_normalized() -> dict:
    """``{dataset code: NormalizationResult}`` for the seven ALTNRG datasets."""
    catalog = MetadataCatalog.load()
    return {code: normalize_iea_dataset(catalog.dataset(code), iea_rows()) for code in ALTNRG_DATASETS}


def altnrg_observations():
    return tuple(o for code in ALTNRG_DATASETS for o in iea_normalized()[code].observations)
