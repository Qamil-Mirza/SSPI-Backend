"""Shared loading for the Greenhouse Gases parity tests: the committed FAOSTAT
Food Balances rows (BEEFMK), IEA ``CO2BySector`` rows (GTRANS), World Bank
population rows (both), and the canonical observations that result. COALPW
reads the ALTNRG datasets (``tests.golden.energy``). No network."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from sspi.ingestion.fao import normalize_fao_dataset, read_bulk_csv
from sspi.ingestion.iea import normalize_iea_dataset
from sspi.ingestion.worldbank import normalize_worldbank_dataset
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures"
FBS_FIXTURE = FIXTURES / "fao" / "FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv"
CO2_FIXTURE = FIXTURES / "iea" / "CO2BySector_sample.json"
POPULATION_FIXTURE = FIXTURES / "wb" / "SP.POP.TOTL_sample.json"
DATASETS = ("UNFAO_BFPROD", "UNFAO_BFCONS", "WB_POPULN", "IEA_TCO2EM")


@cache
def fbs_rows() -> tuple[dict, ...]:
    return tuple(read_bulk_csv(FBS_FIXTURE.read_text(encoding="utf-8"), "FBS"))


@cache
def co2_rows() -> tuple[dict, ...]:
    return tuple(json.loads(CO2_FIXTURE.read_text(encoding="utf-8")))


@cache
def population_payload() -> list:
    return json.loads(POPULATION_FIXTURE.read_text(encoding="utf-8"))


@cache
def normalized() -> dict:
    """``{dataset code: NormalizationResult}`` for the four Greenhouse Gases source datasets."""
    catalog = MetadataCatalog.load()
    return {
        "UNFAO_BFPROD": normalize_fao_dataset(catalog.dataset("UNFAO_BFPROD"), fbs_rows()),
        "UNFAO_BFCONS": normalize_fao_dataset(catalog.dataset("UNFAO_BFCONS"), fbs_rows()),
        "WB_POPULN": normalize_worldbank_dataset(catalog.dataset("WB_POPULN"), population_payload()[1]),
        "IEA_TCO2EM": normalize_iea_dataset(catalog.dataset("IEA_TCO2EM"), co2_rows()),
    }


def observations(*codes: str):
    return tuple(o for code in codes for o in normalized()[code].observations)


def beefmk_observations():
    return observations("UNFAO_BFPROD", "UNFAO_BFCONS", "WB_POPULN")


def gtrans_observations():
    return observations("IEA_TCO2EM", "WB_POPULN")
