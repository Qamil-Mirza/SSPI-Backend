"""The facade's pure DataFrame builders and query validation. No database."""

import numpy as np
import pandas as pd
import pytest

from sspi.errors import InvalidQueryError, UnknownCodeError
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES, observations_frame, scores_frame, validate_query
from sspi.metadata import MetadataCatalog
from sspi.scoring import IndicatorScore, Observation


def obs(dataset="UNSDG_MARINE", country="MYS", year=2020, value=19.70109, unit="PERCENT", **prov):
    return Observation(dataset, country, year, value, unit, prov)


def score(country="MYS", year=2020, value=0.2972865333333333, inputs=(), indicator="BIODIV"):
    return IndicatorScore(indicator, country, year, value, "Index", tuple(inputs))


IMPUTED_MARINE = obs("UNSDG_MARINE", "AUT", 2020, 36.56867346153846, imputed=True, imputation_method="ImputeReferenceClassAverage")


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


# --- dataset frame -----------------------------------------------------------------


def test_dataset_frame_schema_and_dtypes():
    df = observations_frame([obs()])
    assert list(df.columns) == ["dataset_code", "country_code", "year", "value", "unit"]
    assert dtypes(df) == DATASET_DTYPES == {"dataset_code": "string", "country_code": "string", "year": "int64", "value": "float64", "unit": "string"}
    assert df.iloc[0].tolist() == ["UNSDG_MARINE", "MYS", 2020, 19.70109, "PERCENT"]
    assert isinstance(df.index, pd.RangeIndex)


def test_empty_dataset_frame_has_the_same_schema_and_dtypes():
    df = observations_frame([])
    assert len(df) == 0 and list(df.columns) == list(DATASET_DTYPES) and dtypes(df) == DATASET_DTYPES
    assert dtypes(observations_frame([], include_provenance=True)) == {**DATASET_DTYPES, "provenance": "object"}


def test_dataset_frame_keeps_input_order_and_does_not_sort():
    rows = [obs(year=2021), obs(year=2020), obs(dataset="UNSDG_FRSHWT", year=2019)]
    assert observations_frame(rows)["year"].tolist() == [2021, 2020, 2019]


def test_provenance_is_omitted_by_default_and_a_dict_column_on_request():
    rows = [obs(source_series="ER_MRN_MPA", nature="C"), IMPUTED_MARINE]
    assert "provenance" not in observations_frame(rows).columns
    df = observations_frame(rows, include_provenance=True)
    assert list(df.columns) == [*DATASET_DTYPES, "provenance"] and str(df["provenance"].dtype) == "object"
    assert df["provenance"].tolist() == [{"source_series": "ER_MRN_MPA", "nature": "C"}, {"imputed": True, "imputation_method": "ImputeReferenceClassAverage"}]
    assert type(df["provenance"][0]) is dict


# --- indicator frame ----------------------------------------------------------------


def test_indicator_frame_schema_and_dtypes():
    df = scores_frame([score(), score("AUT", value=0.5858737782051282, inputs=[IMPUTED_MARINE])])
    assert list(df.columns) == ["indicator_code", "country_code", "year", "score", "unit", "imputed"]
    assert dtypes(df) == INDICATOR_DTYPES == {"indicator_code": "string", "country_code": "string", "year": "int64", "score": "float64", "unit": "string", "imputed": "bool"}
    assert df.iloc[0].tolist() == ["BIODIV", "MYS", 2020, 0.2972865333333333, "Index", False]
    assert df.iloc[1].tolist() == ["BIODIV", "AUT", 2020, 0.5858737782051282, "Index", True]


def test_empty_indicator_frame_has_the_same_schema_and_dtypes():
    df = scores_frame([])
    assert len(df) == 0 and dtypes(df) == INDICATOR_DTYPES
    assert dtypes(scores_frame([], include_inputs=True)) == {**INDICATOR_DTYPES, "inputs": "object"}


def test_null_score_becomes_nan_in_a_float_column():
    df = scores_frame([score(value=None)])
    assert np.isnan(df["score"][0]) and str(df["score"].dtype) == "float64"


def test_inputs_are_omitted_by_default_and_a_tuple_of_dicts_on_request():
    s = score("AUT", value=0.5858737782051282, inputs=[obs("UNSDG_FRSHWT", "AUT", 2020, 71.29881), IMPUTED_MARINE])
    assert "inputs" not in scores_frame([s]).columns
    df = scores_frame([s], include_inputs=True)
    assert list(df.columns) == [*INDICATOR_DTYPES, "inputs"]
    assert df["inputs"][0] == (
        {"dataset_code": "UNSDG_FRSHWT", "value": 71.29881, "unit": "PERCENT", "imputed": False, "imputation_method": None},
        {"dataset_code": "UNSDG_MARINE", "value": 36.56867346153846, "unit": "PERCENT", "imputed": True, "imputation_method": "ImputeReferenceClassAverage"},
    )


# --- validation -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def metadata():
    return MetadataCatalog.load()


def test_exactly_one_of_datasets_or_indicators(metadata):
    with pytest.raises(InvalidQueryError, match="exactly one"):
        validate_query(metadata, datasets=["UNSDG_MARINE"], indicators=["BIODIV"])
    with pytest.raises(InvalidQueryError, match="exactly one"):
        validate_query(metadata)


def test_valid_dataset_and_indicator_queries_normalize_to_tuples(metadata):
    spec = validate_query(metadata, datasets=["UNSDG_MARINE", "UNSDG_TERRST"], countries=["MYS", "USA"], years=(2010, 2023))
    assert (spec.datasets, spec.indicators, spec.countries, spec.years) == (("UNSDG_MARINE", "UNSDG_TERRST"), None, ("MYS", "USA"), (2010, 2023))
    spec = validate_query(metadata, indicators=["BIODIV"])
    assert (spec.datasets, spec.indicators, spec.countries, spec.years) == (None, ("BIODIV",), None, None)


@pytest.mark.parametrize("kwargs", [{"datasets": ["UNSDG_NOPE"]}, {"indicators": ["NOPE"]}, {"datasets": ["UNSDG_MARINE", "unsdg_marine"]}])
def test_unknown_dataset_or_indicator_codes_fail_via_the_catalog(metadata, kwargs):
    with pytest.raises(UnknownCodeError):
        validate_query(metadata, **kwargs)


@pytest.mark.parametrize("kwargs", [{"datasets": []}, {"indicators": []}, {"datasets": ["UNSDG_MARINE"], "countries": []}])
def test_empty_code_lists_fail_fast_rather_than_meaning_everything(metadata, kwargs):
    with pytest.raises(InvalidQueryError, match="selects nothing"):
        validate_query(metadata, **kwargs)


@pytest.mark.parametrize("kwargs", [{"datasets": "UNSDG_MARINE"}, {"indicators": "BIODIV"}, {"datasets": ["UNSDG_MARINE"], "countries": "MYS"}])
def test_a_bare_string_is_not_a_list_of_codes(metadata, kwargs):
    with pytest.raises(InvalidQueryError, match="list"):
        validate_query(metadata, **kwargs)


@pytest.mark.parametrize("country", ["mys", "Malaysia", "MY", "MYSX", ""])
def test_country_codes_are_validated_for_format_only(metadata, country):
    with pytest.raises(InvalidQueryError, match="ISO"):
        validate_query(metadata, datasets=["UNSDG_MARINE"], countries=[country])
    # well-formed but not in any catalog (Kosovo) is accepted: the persistence universe is broader than the catalog
    assert validate_query(metadata, datasets=["UNSDG_MARINE"], countries=["XKX"]).countries == ("XKX",)


@pytest.mark.parametrize("years", [(2023, 2010), (2010,), 2010, ("2010", "2023"), (2010.0, 2023), (True, 2023)])
def test_years_must_be_an_inclusive_integer_pair(metadata, years):
    with pytest.raises(InvalidQueryError, match="years"):
        validate_query(metadata, datasets=["UNSDG_MARINE"], years=years)


def test_option_flags_must_match_the_query_kind(metadata):
    with pytest.raises(InvalidQueryError, match="include_inputs"):
        validate_query(metadata, datasets=["UNSDG_MARINE"], include_inputs=True)
    spec = validate_query(metadata, indicators=["BIODIV"], include_provenance=True, include_inputs=True)  # both apply to scores
    assert spec.include_provenance and spec.include_inputs


def test_scores_frame_can_carry_the_score_level_provenance():
    from sspi.scoring import IndicatorScore, Observation

    observed = IndicatorScore("DEFRST", "MYS", 2020, 0.5, "Index", (Observation("UNFAO_FRSTLV", "MYS", 2020, 1.0, "1000 ha"),))
    extrapolated = IndicatorScore("DEFRST", "MYS", 2023, 0.5, "Index", observed.inputs, (), {"imputed": True, "imputation_method": "ExtrapolateForward", "source_year": 2020, "imputation_distance": 3})
    df = scores_frame([observed, extrapolated], include_inputs=True, include_provenance=True)
    assert list(df.columns) == [*INDICATOR_DTYPES, "inputs", "provenance"]
    assert list(df["imputed"]) == [False, True]  # score-level provenance classifies the second row
    assert df["provenance"][0] == {} and df["provenance"][1]["source_year"] == 2020
    assert df["inputs"][1][0]["imputed"] is False  # the copied input is itself observed
    assert dtypes(scores_frame([], include_provenance=True)) == {**INDICATOR_DTYPES, "provenance": "object"}
