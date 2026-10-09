"""Parity for EPI_MSWGEN and MSWGEN on the committed 2024 EPI fixture (the
``WPC_ind_na.csv`` of ``epi2024indicators.zip``, the archive the legacy
collector read): the EPI parser must reproduce the output of the cleaner
registered for ``EPI_MSWGEN`` (``parse_epi_csv``) exactly, and the
orchestrated MSWGEN computation the legacy compute route. MSWGEN has no
impute route.

This is historical parity only. The legacy archive is no longer served and
the 2026 edition publishes no WPC series, so ``EPI_MSWGEN`` is in
``UNAVAILABLE_SOURCES`` and cannot be ingested. The legacy goalpost turns
the EPI score's direction around (MSWGEN-1); that is reproduced, not fixed.
"""

import pytest

from sspi.errors import SourceUnavailableError
from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.mswgen import score_mswgen
from sspi.ingestion import SUPPORTED_DATASETS, UNAVAILABLE_SOURCES
from sspi.ingestion.epi import ARCHIVES, normalize_epi_csv, normalize_epi_dataset, series_of
from sspi.ingestion.runner import resolve_datasets
from sspi.metadata import MetadataCatalog
from tests.golden.parity import INDICATOR_CASES, OBSERVATION_CASES, OBSERVATION_IDENTITY, assert_parity, load_cases, observation_record, score_records, source_fixtures, summary

DATASET_CASES = load_cases(OBSERVATION_CASES["EPI_MSWGEN"])
CASES = load_cases(INDICATOR_CASES["MSWGEN"])


@pytest.fixture(scope="module")
def fixture_text():
    (path,) = source_fixtures(DATASET_CASES)
    assert source_fixtures(CASES) == [path]
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def normalized(fixture_text):
    dataset = MetadataCatalog.load().dataset("EPI_MSWGEN")
    return normalize_epi_dataset(dataset, {"WPC_ind_na.csv": fixture_text})


@pytest.fixture(scope="module")
def result(normalized):
    return compute_indicator(registry.get("MSWGEN"), normalized.observations, recipients=())


# --- dataset parity ------------------------------------------------------------------------


def test_golden_file_describes_this_dataset():
    dataset = MetadataCatalog.load().dataset("EPI_MSWGEN")
    assert DATASET_CASES["dataset_code"] == "EPI_MSWGEN" and DATASET_CASES["series_code"] == dataset.source.organization_series_code == "WPC"
    assert DATASET_CASES["archive"] == dataset.source.query_code == "epi2024indicators" and dataset.unit == "Index"
    assert series_of("P5_Indicator/WPC_ind_na.csv") == "WPC"
    assert DATASET_CASES["year_columns"] == [f"WPC.ind.{y}" for y in range(1995, 2025)]


def test_observations_match_legacy_cleaner(normalized):
    new = [observation_record(o) for o in normalized.observations]
    assert_parity("EPI_MSWGEN observations", new, DATASET_CASES["observations"], OBSERVATION_IDENTITY)
    assert summary(new) == summary(DATASET_CASES["observations"])
    assert len(new) == 6210 and len({o.country_code for o in normalized.observations}) == 207 and {o.unit for o in normalized.observations} == {"Index"}


def test_missing_cells_are_exactly_the_cells_legacy_dropped_and_zeros_are_kept(normalized):
    assert normalized.skipped_areas == () == tuple(DATASET_CASES["skipped_areas"])  # no geography remapping, nothing skipped
    assert normalized.missing_values == DATASET_CASES["value_cells"] - len(DATASET_CASES["observations"]) == 390
    assert sum(o.value == 0 for o in normalized.observations) == sum(o["value"] == 0 for o in DATASET_CASES["observations"]) == 53
    assert {"TWN", "HKG", "XKX"} <= {o.country_code for o in normalized.observations}  # as published, no country filter


def test_csv_entry_point_and_archive_entry_point_agree(fixture_text, normalized):
    dataset = MetadataCatalog.load().dataset("EPI_MSWGEN")
    direct = normalize_epi_csv(dataset, fixture_text, edition="epi2024indicators", file_name="WPC_ind_na.csv")
    assert [observation_record(o) for o in direct.observations] == [observation_record(o) for o in normalized.observations]


def test_the_live_source_is_declared_unavailable_not_supported():
    """Historical parity only: no production edition carries WPC, so ingestion refuses before any fetch."""
    assert "EPI_MSWGEN" in UNAVAILABLE_SOURCES and "EPI_MSWGEN" not in SUPPORTED_DATASETS
    assert "epi2024indicators" in ARCHIVES  # the legacy URL stays on record; it now serves HTML
    with pytest.raises(SourceUnavailableError, match=r"EPI_MSWGEN cannot be ingested: .*no WPC series"):
        resolve_datasets(["EPI_MSWGEN"], MetadataCatalog.load())


# --- indicator parity ----------------------------------------------------------------------


def test_golden_file_records_the_legacy_facts():
    registry.get("MSWGEN").check_against(MetadataCatalog.load())
    assert CASES["indicator_code"] == "MSWGEN" and CASES["impute_route_exists"] is False and registry.get("MSWGEN").imputation is None
    assert tuple(registry.get("MSWGEN").goalposts) == (CASES["goalposts"]["lower"], CASES["goalposts"]["upper"]) == (100, 0)
    assert CASES["goalposts"]["read_from"] == "methodology/sus/wst/mswgen/methodology.md"


@pytest.mark.parametrize("case", CASES["goalpost_cases"], ids=[str(c["value"]) for c in CASES["goalpost_cases"]])
def test_score_function_matches_legacy(case):
    assert score_mswgen(case["value"]) == case["score"]


def test_scores_match_the_legacy_compute_route(result):
    assert_parity("MSWGEN scores", score_records(result.observed_scores, imputation=False), CASES["scores"])
    assert len(result.observed_scores) == 6210


def test_classification_and_missingness_match_legacy(result, normalized):
    assert result.imputed_scores == () and not any(is_imputed(s) for s in result.scores)
    assert len(result.unscored) == CASES["incomplete_count"] == 0
    assert {(s.country_code, s.year) for s in result.scores} == {(o.country_code, o.year) for o in normalized.observations}


def test_the_legacy_goalpost_reverses_the_epi_direction(result):
    """MSWGEN-1, preserved: the EPI scores less waste higher; 1 - EPI/100 scores more waste higher."""
    scores = {(s.country_code, s.year): s for s in result.scores}
    usa, pakistan = scores[("USA", 2018)], scores[("PAK", 2018)]
    assert (usa.inputs[0].value, pakistan.inputs[0].value) == (13.3, 64.2)  # EPI: Pakistan far better than the United States
    assert usa.score > pakistan.score and (usa.score, pakistan.score) == (0.867, 0.358)
    assert all(s.score == 1.0 for s in result.scores if s.inputs[0].value == 0)  # the worst EPI score scores a perfect 1.0
