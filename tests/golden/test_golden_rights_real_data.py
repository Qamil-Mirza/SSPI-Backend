"""Opt-in: the new V-Dem adapter, RULELW and EDEMOC on the ORIGINAL V-Dem v13
archive, kept outside the repository (docs/data-governance-review.md,
GOV-6), against the pinned legacy code's output on the same file.

    SSPI_VDEM_REAL_DATA=local-data/vdem .venv/bin/python -m pytest -m vdem_real_data

The legacy output was generated from the same archive by
``generate_rights_cases.py --real local-data`` with the cleaners' clock
fixed to 2026-10-26: the legacy collect route's iterator, the legacy raw
collection (which split the 396 MB CSV into 24 documents and joined them
again), the registered cleaners and both routes of each indicator. Every
file is checked against the committed ``tests/fixtures/vdem/REAL_DATA.sha256``;
a missing or changed file fails. Exact equality throughout; no tolerance.
"""

from collections import Counter
from functools import cache

import pytest

from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.ingestion.vdem import ARCHIVES, VDemArchive, normalize_vdem_dataset
from sspi.metadata import CountryCatalog, MetadataCatalog
from tests.golden.parity import (
    OBSERVATION_IDENTITY,
    assert_parity,
    observation_record,
    score_level_records,
)
from tests.golden.public_safety_real_data import PrivateTier

VDEM = PrivateTier("SSPI_VDEM_REAL_DATA", "vdem", "the directory of the original V-Dem v13 archive (local-data/vdem)")
CATALOG = MetadataCatalog.load()
KEY = "V-Dem-CY-FullOthers_csv_v13"
INDICATORS = {"RULELW": "VDEM_RULELW", "EDEMOC": "VDEM_EDEMOC"}
pytestmark = [pytest.mark.vdem_real_data, pytest.mark.skipif(not VDEM.directory, reason=f"set {VDEM.environment_variable} to {VDEM.guidance}")]


@cache
def observations(code, evaluation_year=2026):
    content = VDEM.read(f"{KEY}.zip")
    return normalize_vdem_dataset(CATALOG.dataset(code), VDemArchive(KEY, ARCHIVES[KEY], ARCHIVES[KEY].sha256, content, evaluation_year))


@cache
def scores(indicator):
    return compute_indicator(registry.get(indicator), observations(INDICATORS[indicator]).observations)


@pytest.mark.parametrize("indicator", sorted(INDICATORS))
def test_observations_match_the_legacy_collector_and_cleaner_on_the_original_archive(indicator):
    code = INDICATORS[indicator]
    result, golden = observations(code), VDEM.golden(f"vdem_{indicator.lower()}_cases.json")
    assert_parity(f"{code} observations (original archive)", [observation_record(o) for o in result.observations], golden["observations"], OBSERVATION_IDENTITY)
    assert result.missing_values == golden["empty_source_values"] == 0 and len(result.observations) == 5674
    assert golden["raw_documents"] == 24 and golden["raw_fragments"] == list(range(24)) and golden["raw_text_characters"] == 396013959
    assert (min(o.year for o in result.observations), max(o.year for o in result.observations)) == (1991, 2022)
    assert len({o.country_code for o in result.observations}) == 179 and {"XKX", "PSG", "SML", "ZZB"} <= {o.country_code for o in result.observations}


@pytest.mark.parametrize("indicator", sorted(INDICATORS))
def test_the_run_year_removes_nothing_from_v13_after_2022(indicator):
    """v13 ends in 2022: run in any year from 2023 on, the cleaner keeps the same rows."""
    code = INDICATORS[indicator]
    run_2023, run_2026 = observations(code, 2023).observations, observations(code).observations
    assert [observation_record(o) for o in run_2023] == [observation_record(o) for o in run_2026]
    assert {tuple(o.provenance["source_years"]) for o in run_2023} == {(1991, 2022)}  # the window is recorded on each row


@pytest.mark.parametrize("indicator", sorted(INDICATORS))
def test_scores_match_both_legacy_routes_on_the_original_archive(indicator):
    golden, result = VDEM.golden(f"{indicator.lower()}_cases.json"), scores(indicator)
    assert_parity(f"{indicator} observed scores (original archive)", score_level_records(result.observed_scores), golden["observed_scores"])
    assert_parity(f"{indicator} imputed scores (original archive)", score_level_records(result.imputed_scores), golden["imputed_scores"])
    assert (len(result.observed_scores), len(result.imputed_scores)) == (5674, 179) and golden["legacy_output_conflicts"] == {"observed_and_imputed": [], "duplicate_imputed": []}
    assert Counter((s.year, s.inputs[0].provenance["imputation_distance"]) for s in result.imputed_scores) == {(2023, 1): 179}
    assert {s.inputs[0].provenance["anchor_year"] for s in result.imputed_scores} == {2022}  # the approved treatment: source year 2022, value unchanged
    observed = {(s.country_code, s.year): s.score for s in result.observed_scores}
    assert all(s.score == observed[(s.country_code, 2022)] for s in result.imputed_scores)
    storage = golden["legacy_storage"]
    assert storage["compute_then_impute"] == {"sspi_indicator_data": 5853, "sspi_indicator_data_imputed": 179, "sspi_indicator_data_identities_held_twice": 0, "sspi_imputed_data": 0}
    assert storage["then_impute_again"]["sspi_indicator_data_identities_held_twice"] == 179  # RULELW-1 / EDEMOC-1


@pytest.mark.parametrize("indicator", sorted(INDICATORS))
def test_sspi67_coverage_2000_2023_is_complete_with_2023_carried(indicator):
    sspi67 = set(CountryCatalog.load().group("SSPI67").members)
    held = {(s.country_code, s.year): s for s in scores(indicator).scores if s.country_code in sspi67 and 2000 <= s.year <= 2023}
    assert len(sspi67) == 66 and len(held) == 66 * 24
    assert {y for (c, y), s in held.items() if is_imputed(s)} == {2023} and sum(is_imputed(s) for s in held.values()) == 66


def test_illustrative_scores():
    rule = {(s.country_code, s.year): s.score for s in scores("RULELW").scores}
    polyarchy = {(s.country_code, s.year): s.score for s in scores("EDEMOC").scores}
    assert (rule[("MYS", 2022)], rule[("AUT", 2022)], rule[("USA", 2022)]) == (0.646, 0.909, 0.959)
    assert (polyarchy[("MYS", 2022)], polyarchy[("AUT", 2022)], polyarchy[("USA", 2022)]) == (0.438, 0.794, 0.819)
    assert rule[("AUT", 2023)] == rule[("AUT", 2022)] and polyarchy[("USA", 2023)] == polyarchy[("USA", 2022)]
