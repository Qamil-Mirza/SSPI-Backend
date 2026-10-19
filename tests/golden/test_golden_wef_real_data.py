"""Opt-in: exact parity of the new WEF adapter and AQELEC with the pinned
legacy code on the ORIGINAL WEF workbook and the full World Bank response,
both kept outside the repository (docs/data-governance-review.md, GOV-2).

    SSPI_WEF_REAL_DATA=local-data/wef .venv/bin/python -m pytest -m wef_real_data

The legacy output was generated from the same files by
``generate_wef_cases.py --real local-data/wef``. Every file is checked
against ``tests/fixtures/wef/REAL_DATA.sha256``; a missing or changed file
fails. Exact equality throughout; no tolerance.
"""

import hashlib
import json
from collections import Counter
from functools import cache

from sspi.indicators import compute_indicator, registry
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.ingestion.wef import WORKBOOKS, WEFWorkbook
from sspi.metadata import CountryCatalog, MetadataCatalog
from tests.golden.parity import OBSERVATION_IDENTITY, PINNED_LEGACY_COMMIT, assert_parity, assert_pinned, observation_record, score_records
from tests.golden.wef_real_data import MARKS, checksums, real_bytes, real_json

pytestmark = MARKS
CATALOG = MetadataCatalog.load()
KEY = "WEF-GCIHH_2023-07-17"


class RealSources:
    """The World Bank and WEF clients, answering from the private files."""

    def fetch_indicator(self, indicator):
        assert indicator == "EG.ELC.ACCS.ZS"
        return real_json("responses/EG.ELC.ACCS.ZS.json")[1]

    def fetch_workbook(self, key):
        content = real_bytes("WEF-GCIHH.xlsx")
        return WEFWorkbook(key, WORKBOOKS[key], hashlib.sha256(content).hexdigest(), content)


@cache
def normalized():
    sources = RealSources()
    results, fetches = fetch_and_normalize(resolve_datasets(["WB_AVELEC", "WEF_QUELEC"], CATALOG), {"WB": sources, "WEF": sources}, metadata=CATALOG)
    assert fetches == ("EG.ELC.ACCS.ZS", KEY)
    return {dataset.code: result for dataset, result in results}


@cache
def run():
    results = normalized()
    return compute_indicator(registry.get("AQELEC"), results["WB_AVELEC"].observations + results["WEF_QUELEC"].observations)


def golden(name):
    payload = real_json(f"golden/{name}")
    assert_pinned(payload, name)
    return payload


def digest(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def test_the_private_files_are_the_validated_ones():
    assert set(checksums()) == {"WEF-GCIHH.xlsx", "responses/EG.ELC.ACCS.ZS.json", "golden/aqelec_cases.json", "golden/wb_avelec_cases.json", "golden/wef_quelec_cases.json"}
    for relative in checksums():
        real_bytes(relative)
    assert checksums()["WEF-GCIHH.xlsx"] == WORKBOOKS[KEY].sha256 == golden("wef_quelec_cases.json")["workbook_sha256"]  # the pinned edition, byte for byte
    assert len(real_bytes("WEF-GCIHH.xlsx")) == 3_476_362 == golden("wef_quelec_cases.json")["workbook_bytes"]
    assert golden("aqelec_cases.json")["generated_from"]["commit"] == PINNED_LEGACY_COMMIT


def test_wef_observations_match_the_legacy_collector_and_cleaner_exactly():
    case, result = golden("wef_quelec_cases.json"), normalized()["WEF_QUELEC"]
    records = [observation_record(o) for o in result.observations]
    assert_parity("WEF_QUELEC observations (original workbook)", records, case["observations"], OBSERVATION_IDENTITY)
    assert len(records) == 1524 and result.missing_values == case["empty_source_values"] == 148 and case["units"] == ["1-7 (best)"]
    assert (case["sheet_rows"], case["selected_rows"], case["year_columns"]) == (49396, 152, [str(y) for y in range(2007, 2018)])
    assert {o.year for o in result.observations} == set(range(2007, 2018)) and len({o.country_code for o in result.observations}) == 152
    assert digest(records) == "f53fd04e826764df0aa6ddaa57d063d90cc310f43251d5ab5005c7503f4c5429"


def test_access_observations_match_the_legacy_cleaner_exactly():
    case, result = golden("wb_avelec_cases.json"), normalized()["WB_AVELEC"]
    records = [observation_record(o) for o in result.observations]
    assert_parity("WB_AVELEC observations (full response)", records, case["observations"], OBSERVATION_IDENTITY)
    assert len(records) == 6702 and [list(s) for s in result.skipped_areas] == case["skipped_areas"] and result.missing_values == case["empty_source_values"]


def test_aqelec_scores_and_incomplete_identities_match_the_compute_route_exactly():
    case, result = golden("aqelec_cases.json"), run()
    records = score_records(result.observed_scores, imputation=False)
    assert_parity("AQELEC scores (original workbook)", records, case["observed_scores"])
    assert sorted([u.country_code, u.year] for u in result.unscored) == case["incomplete_identities"]
    assert len(records) == 1513 and len(result.unscored) == 5200 and result.imputed_scores == ()
    assert {s.year for s in result.scores} == set(range(2007, 2018))  # nothing before 2007 or after 2017
    assert digest(records) == "cfd29584dd13808c8336d0499aaade541bf121cb261cace683897d92eb94283e"


def test_sspi67_coverage():
    members = set(CountryCatalog.load().group("SSPI67").members)
    scored = Counter(s.country_code for s in run().scores if s.country_code in members)
    assert sum(scored.values()) == 711 and sorted(members - set(scored)) == ["IRQ"]  # of 66 x 11 = 726 member-years 2007-2017
    assert sorted((c, n) for c, n in scored.items() if n < 11) == [("ECU", 10), ("IRN", 8)]
