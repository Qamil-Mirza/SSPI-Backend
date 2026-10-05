"""Parity for EPI_NITROG and NITROG on the committed 2024 EPI fixture (the
``SNM_ind_na.csv`` of ``epi2024indicators.zip``, the archive the legacy
collector read): the new EPI parser must reproduce the legacy
``clean_epi_nitrog`` / ``parse_epi_csv`` output exactly, and the orchestrated
NITROG computation the legacy compute route. NITROG has no impute route.

This is historical parity evidence. Production ingestion reads the 2026
edition, which is not compared with the legacy backend (NITROG-1).
"""

import pytest

from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.nitrog import score_nitrog
from sspi.ingestion.epi import normalize_epi_csv, normalize_epi_dataset, series_of
from sspi.metadata import MetadataCatalog
from tests.golden.parity import INDICATOR_CASES, OBSERVATION_CASES, OBSERVATION_IDENTITY, assert_parity, load_cases, observation_record, score_records, source_fixtures, summary

DATASET_CASES = load_cases(OBSERVATION_CASES["EPI_NITROG"])
CASES = load_cases(INDICATOR_CASES["NITROG"])


@pytest.fixture(scope="module")
def fixture_text():
    (path,) = source_fixtures(DATASET_CASES)
    assert source_fixtures(CASES) == [path]
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def normalized(fixture_text):
    dataset = MetadataCatalog.load().dataset("EPI_NITROG")
    return normalize_epi_dataset(dataset, {"P5_Indicator/SNM_ind_na.csv".rsplit("/", 1)[-1]: fixture_text})


@pytest.fixture(scope="module")
def result(normalized):
    return compute_indicator(registry.get("NITROG"), normalized.observations, recipients=())


# --- dataset parity ------------------------------------------------------------------------


def test_golden_file_describes_this_dataset():
    dataset = MetadataCatalog.load().dataset("EPI_NITROG")
    assert DATASET_CASES["dataset_code"] == "EPI_NITROG" and DATASET_CASES["series_code"] == dataset.source.organization_series_code == "SNM"
    assert DATASET_CASES["archive"] == "epi2024indicators" != dataset.source.query_code  # the fixture is the legacy edition; production reads the current one
    assert series_of("P5_Indicator/SNM_ind_na.csv") == "SNM"
    assert DATASET_CASES["year_columns"] == [f"SNM.ind.{y}" for y in range(1995, 2025)]


def test_observations_match_legacy_cleaner(normalized):
    new = [observation_record(o) for o in normalized.observations]
    assert_parity("EPI_NITROG observations", new, DATASET_CASES["observations"], OBSERVATION_IDENTITY)
    assert summary(new) == summary(DATASET_CASES["observations"])
    assert len(new) == 5820 and {o.unit for o in normalized.observations} == {"Index"}


def test_missing_cells_are_exactly_the_cells_legacy_dropped(normalized):
    assert normalized.skipped_areas == () == tuple(DATASET_CASES["skipped_areas"])  # no geography remapping, nothing skipped
    assert normalized.missing_values == DATASET_CASES["value_cells"] - len(DATASET_CASES["observations"]) == 780


def test_csv_entry_point_and_archive_entry_point_agree(fixture_text, normalized):
    dataset = MetadataCatalog.load().dataset("EPI_NITROG")
    direct = normalize_epi_csv(dataset, fixture_text, edition="epi2024indicators", file_name="SNM_ind_na.csv")
    assert [observation_record(o) for o in direct.observations] == [observation_record(o) for o in normalized.observations]
    assert direct.observations[0].provenance["source_edition"] == "epi2024indicators"


# --- indicator parity ----------------------------------------------------------------------


def test_golden_file_records_the_legacy_facts():
    assert CASES["indicator_code"] == "NITROG" and CASES["impute_route_exists"] is False
    assert tuple(registry.get("NITROG").goalposts) == (CASES["goalposts"]["lower"], CASES["goalposts"]["upper"]) == (0, 100)


@pytest.mark.parametrize("case", CASES["goalpost_cases"], ids=[str(c["value"]) for c in CASES["goalpost_cases"]])
def test_score_function_matches_legacy(case):
    assert score_nitrog(case["value"]) == case["score"]


def test_scores_match_the_legacy_compute_route(result):
    assert_parity("NITROG scores", score_records(result.observed_scores, imputation=False), CASES["scores"])
    assert len(result.observed_scores) == 5820
    assert (min(s.score for s in result.scores), max(s.score for s in result.scores)) == (min(s["score"] for s in CASES["scores"]), max(s["score"] for s in CASES["scores"]))


def test_classification_and_missingness_match_legacy(result, normalized):
    assert result.imputed_scores == () and not any(is_imputed(s) for s in result.scores)
    assert len(result.unscored) == CASES["incomplete_count"] == 0
    assert {(s.country_code, s.year) for s in result.scores} == {(o.country_code, o.year) for o in normalized.observations}
