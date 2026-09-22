"""End-to-end `score_indicator` tests, translated from the old
tests/unit/compute/test_score_indicator.py and
tests/unit/utilities/test_score_indicator_comprehensive.py.

Inputs are the old dict fixtures, converted through the test-only adapter in
tests/legacy.py so the fixtures stay byte-for-byte the old ones. Assertions
are on the typed result, or on the old shape via `documents_from_result`
where that reads more naturally.

Where an old test pinned an exception raised by the old coercion/validation
boundary (`TypeError` for a None Value, `ValueError` for junk text,
`InvalidDocumentFormatError` for a missing Unit), the same exception is now
raised by the adapter, not the kernel. Those tests are marked "adapter" in
their docstrings.

Dropped: tests/unit/utilities/test_score_indicator_main.py in full. It
mock-patched every stage and asserted call order; it characterizes wiring,
not behaviour.
"""

import math

import pytest

from sspi.errors import InvalidObservationError
from sspi.scoring import Observation, ScoringResult, UnscoredReason, goalpost, score_indicator, validate_observations
from tests.legacy import documents_from_result, observations_from_documents


@pytest.fixture
def biodiv_docs():
    return [
        {"DatasetCode": "UNSDG_TERRST", "CountryCode": "AUS", "Year": 2018, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_FRSHWT", "CountryCode": "AUS", "Year": 2018, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_MARINE", "CountryCode": "AUS", "Year": 2018, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_TERRST", "CountryCode": "URU", "Year": 2018, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_FRSHWT", "CountryCode": "URU", "Year": 2018, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_MARINE", "CountryCode": "URU", "Year": 2018, "Value": 50},  # no Unit
        {"DatasetCode": "UNSDG_TERRST", "CountryCode": "URU", "Year": 2017, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_FRSHWT", "CountryCode": "URU", "Year": 2017, "Value": 50, "Unit": "Index"},
        {"DatasetCode": "UNSDG_MARINE", "CountryCode": "URU", "Year": 2017, "Value": 50, "Unit": "Index"},
    ]


@pytest.fixture
def extra_docs():
    return [
        {"DatasetCode": "LDAREA", "CountryCode": "AUS", "Year": 2018, "Value": 7692024, "Unit": "km^2"},
        {"DatasetCode": "LDAREA", "CountryCode": "URU", "Year": 2018, "Value": 176215, "Unit": "km^2"},
    ]


@pytest.fixture
def valid_docs():
    return [
        {"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": 100, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "USA", "Year": 2020, "Value": 80, "Unit": "Index"},
        {"DatasetCode": "DATASET_A", "CountryCode": "CAN", "Year": 2020, "Value": 90, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "CAN", "Year": 2020, "Value": 85, "Unit": "Index"},
    ]


def biodiv_score(UNSDG_TERRST, UNSDG_FRSHWT, UNSDG_MARINE):
    return (UNSDG_TERRST + UNSDG_FRSHWT + UNSDG_MARINE) / 3


# --- validation --------------------------------------------------------------


def test_missing_unit_rejected_at_adapter(biodiv_docs):
    """adapter: old compute/test_score_indicator.py::test_validate_datasets_list"""
    observations_from_documents(biodiv_docs[0:5])
    with pytest.raises(InvalidObservationError) as e_info:
        observations_from_documents(biodiv_docs[0:6])
    assert "Unit" in str(e_info.value)


def test_duplicate_observation_identity_rejected():
    observations = observations_from_documents([
        {"DatasetCode": "A", "CountryCode": "USA", "Year": 2020, "Value": 1, "Unit": "u"},
        {"DatasetCode": "A", "CountryCode": "USA", "Year": 2020, "Value": 2, "Unit": "u"},
    ])
    with pytest.raises(InvalidObservationError, match="duplicate"):
        validate_observations(observations)
    with pytest.raises(InvalidObservationError, match="duplicate"):
        score_indicator(observations, "DUPLIC", lambda A: A, "u")


def test_validate_observations_rejects_non_observation():
    with pytest.raises(TypeError):
        validate_observations([{"DatasetCode": "A"}])


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (dict(dataset_code="", country_code="USA", year=2020, value=1.0), "dataset_code"),
        (dict(dataset_code=None, country_code="USA", year=2020, value=1.0), "dataset_code"),
        (dict(dataset_code="A", country_code="", year=2020, value=1.0), "country_code"),
        (dict(dataset_code="A", country_code="USA", year="2020", value=1.0), "year"),
        (dict(dataset_code="A", country_code="USA", year=2020.0, value=1.0), "year"),
        (dict(dataset_code="A", country_code="USA", year=True, value=1.0), "year"),
        (dict(dataset_code="A", country_code="USA", year=2020, value="1"), "value"),
        (dict(dataset_code="A", country_code="USA", year=2020, value=None), "value"),
        (dict(dataset_code="A", country_code="USA", year=2020, value=True), "value"),
        (dict(dataset_code="A", country_code="USA", year=2020, value=float("nan")), "value"),
        (dict(dataset_code="A", country_code="USA", year=2020, value=float("inf")), "value"),
    ],
)
def test_observation_enforces_only_scoring_invariants(kwargs, match):
    with pytest.raises(InvalidObservationError, match=match):
        Observation(unit="u", **kwargs)


def test_observation_does_not_enforce_domain_rules():
    # Country-code format and year range are ingestion concerns, not kernel ones.
    Observation("lower_case", "eu-28", 1850, 1, "u")
    Observation("A", "USA", 2999, -1e300, "")


def test_observation_value_is_stored_as_float():
    assert Observation("A", "USA", 2020, 5, "u").value == 5.0
    assert isinstance(Observation("A", "USA", 2020, 5, "u").value, float)


# --- old compute/test_score_indicator.py ------------------------------------


def test_score_indicator_biodiv(biodiv_docs):
    with pytest.raises(InvalidObservationError):
        score_indicator(observations_from_documents(biodiv_docs), "BIODIV", biodiv_score, "Index")
    result = score_indicator(observations_from_documents([*biodiv_docs[0:3], *biodiv_docs[6:9]]), "BIODIV", biodiv_score, "Index")
    assert len(result.scored) == 2
    assert (result.scored[0].country_code, result.scored[0].year, result.scored[0].indicator_code) == ("AUS", 2018, "BIODIV")
    assert (result.scored[1].country_code, result.scored[1].year, result.scored[1].indicator_code) == ("URU", 2017, "BIODIV")


def test_score_indicator_with_extra_datasets(biodiv_docs, extra_docs):
    def score_biodiv(UNSDG_TERRST, UNSDG_FRSHWT, UNSDG_MARINE):
        return (UNSDG_TERRST / 100 + UNSDG_FRSHWT / 100 + UNSDG_MARINE / 100) / 3

    result = score_indicator(observations_from_documents([*biodiv_docs[0:3], *biodiv_docs[6:9], *extra_docs]), "BIODIV", score_biodiv, "Index")
    complete, incomplete = documents_from_result(result)
    assert len(complete) == 2
    assert complete[0]["CountryCode"] == "AUS"
    assert complete[0]["Year"] == 2018
    assert complete[0]["IndicatorCode"] == "BIODIV"
    assert complete[0]["Score"] == pytest.approx(0.5, rel=1e-4)
    assert len(complete[0]["Datasets"]) == 4
    assert complete[0]["Datasets"][3]["DatasetCode"] == "LDAREA"
    assert complete[1]["CountryCode"] == "URU"
    assert complete[1]["Year"] == 2017
    assert len(complete[1]["Datasets"]) == 3
    assert incomplete == [
        {"IndicatorCode": "BIODIV", "CountryCode": "URU", "Year": 2018, "Datasets": [
            {"DatasetCode": "LDAREA", "CountryCode": "URU", "Year": 2018, "Value": 176215.0, "Unit": "km^2"}
        ]}
    ]


# --- old test_score_indicator_comprehensive.py ------------------------------


def test_empty_input():
    result = score_indicator([], "TEST_INDICATOR", lambda DATASET_A: DATASET_A / 100, "Score")
    assert result == ScoringResult([], [])


def test_missing_required_dataset_is_unscored():
    docs = [{"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": 100, "Unit": "Index"}]
    result = score_indicator(observations_from_documents(docs), "TEST_INDICATOR", lambda DATASET_A, DATASET_B: (DATASET_A + DATASET_B) / 2, "Score")
    assert result.scored == []
    assert len(result.unscored) == 1
    assert result.unscored[0].reason is UnscoredReason.MISSING_DATASETS
    assert result.unscored[0].details == ("DATASET_B",)


def test_none_value_rejected_at_adapter():
    """adapter: old pinned TypeError from float(None) in convert_data_types."""
    with pytest.raises(TypeError):
        observations_from_documents([{"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": None, "Unit": "Index"}])


def test_nan_value_rejected():
    with pytest.raises(InvalidObservationError):
        observations_from_documents([{"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": float("nan"), "Unit": "Index"}])


def test_non_numeric_text_rejected_at_adapter():
    """adapter: old pinned ValueError from float("not_a_number")."""
    with pytest.raises(ValueError):
        observations_from_documents([{"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": "2020", "Value": "not_a_number", "Unit": "Index"}])


def test_string_unit(valid_docs):
    result = score_indicator(observations_from_documents(valid_docs), "TEST_INDICATOR", lambda DATASET_A, DATASET_B: (DATASET_A + DATASET_B) / 2, "Normalized Score")
    assert len(result.scored) == 2
    assert all(s.unit == "Normalized Score" for s in result.scored)
    assert all(s.indicator_code == "TEST_INDICATOR" for s in result.scored)


def test_callable_unit(valid_docs):
    def unit_function(DATASET_A, DATASET_B):
        return "High Score" if DATASET_A > DATASET_B else "Low Score"

    result = score_indicator(observations_from_documents(valid_docs), "TEST_INDICATOR", lambda DATASET_A, DATASET_B: (DATASET_A + DATASET_B) / 2, unit_function)
    assert len(result.scored) == 2
    assert all(s.unit == "High Score" for s in result.scored)


def test_complex_score_function_exact(valid_docs):
    def complex_score(DATASET_A, DATASET_B):
        return min(100, max(0, DATASET_A * 0.6 + DATASET_B * 0.4))

    result = score_indicator(observations_from_documents(valid_docs), "COMPLEX_INDICATOR", complex_score, "Weighted Index")
    assert len(result.scored) == 2
    assert all(0 <= s.score <= 100 for s in result.scored)
    usa = next(s for s in result.scored if s.country_code == "USA")
    assert usa.score == 100 * 0.6 + 80 * 0.4


def test_division_by_zero_propagates():
    docs = [
        {"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": 100, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "USA", "Year": 2020, "Value": 0, "Unit": "Index"},
    ]
    with pytest.raises(ZeroDivisionError):
        score_indicator(observations_from_documents(docs), "DIV_INDICATOR", lambda DATASET_A, DATASET_B: DATASET_A / DATASET_B, "Ratio")


def test_score_function_returning_none_is_scored():
    docs = [
        {"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": 30, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "USA", "Year": 2020, "Value": 80, "Unit": "Index"},
    ]
    result = score_indicator(observations_from_documents(docs), "NONE_INDICATOR", lambda DATASET_A, DATASET_B: None if DATASET_A < 50 else DATASET_A + DATASET_B, "Sum")
    assert len(result.scored) == 1
    assert result.scored[0].score is None


def test_multiple_years_same_country(valid_docs):
    docs = valid_docs + [
        {"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2021, "Value": 105, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "USA", "Year": 2021, "Value": 85, "Unit": "Index"},
    ]
    result = score_indicator(observations_from_documents(docs), "MULTI_YEAR", lambda DATASET_A, DATASET_B: (DATASET_A + DATASET_B) / 2, "Average")
    assert len(result.scored) == 3
    usa = [s for s in result.scored if s.country_code == "USA"]
    assert {s.year for s in usa} == {2020, 2021}


def test_argument_mismatch_is_unscored():
    docs = [{"DatasetCode": "WRONG_DATASET", "CountryCode": "USA", "Year": 2020, "Value": 100, "Unit": "Index"}]
    result = score_indicator(observations_from_documents(docs), "MISMATCH_INDICATOR", lambda DATASET_A, DATASET_B: DATASET_A + DATASET_B, "Sum")
    assert result.scored == []
    assert len(result.unscored) == 1
    assert result.unscored[0].details == ("DATASET_A", "DATASET_B")


def test_large_dataset():
    docs = []
    for country in ["USA", "CAN", "GBR", "FRA", "DEU"]:
        for year in range(2018, 2023):
            docs += [
                {"DatasetCode": "DATASET_A", "CountryCode": country, "Year": year, "Value": 50 + hash(f"{country}_{year}") % 50, "Unit": "Index"},
                {"DatasetCode": "DATASET_B", "CountryCode": country, "Year": year, "Value": 30 + hash(f"{country}_{year}_B") % 40, "Unit": "Index"},
            ]
    result = score_indicator(observations_from_documents(docs), "LARGE_INDICATOR", lambda DATASET_A, DATASET_B: (DATASET_A + DATASET_B) / 2, "Average")
    assert len(result.scored) == 25
    assert result.unscored == []
    assert all(s.indicator_code == "LARGE_INDICATOR" for s in result.scored)


def test_extreme_numeric_values():
    docs = [
        {"DatasetCode": "DATASET_A", "CountryCode": "USA", "Year": 2020, "Value": 1e10, "Unit": "Index"},
        {"DatasetCode": "DATASET_B", "CountryCode": "USA", "Year": 2020, "Value": 1e-10, "Unit": "Index"},
    ]
    result = score_indicator(observations_from_documents(docs), "EXTREME_INDICATOR", lambda DATASET_A, DATASET_B: DATASET_A + DATASET_B, "Sum")
    assert len(result.scored) == 1
    assert math.isfinite(result.scored[0].score)
    assert result.scored[0].score > 0


def test_goalpost_score_function_inverted_bounds():
    docs = [{"DatasetCode": "EPI_MSWGEN", "CountryCode": c, "Year": 2020, "Value": v, "Unit": "kg"} for c, v in [("USA", 120), ("NOR", 25)]]
    result = score_indicator(observations_from_documents(docs), "MSWGEN", lambda EPI_MSWGEN: goalpost(EPI_MSWGEN, 100, 0), "Index")
    assert [s.score for s in result.scored] == [0.0, 0.75]
