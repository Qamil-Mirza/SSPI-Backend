"""The intended notebook workflow, end to end on the isolated database:

    fixtures -> PostgreSQL -> sspi.run("BIODIV") -> sspi.query(...) -> DataFrame

The user never sees Repository, Session or a transaction.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from sspi import SSPI
from sspi.db import Repository
from sspi.errors import InvalidQueryError, UnknownCodeError
from sspi.facade import DATASET_DTYPES, INDICATOR_DTYPES
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}


def dtypes(df):
    return {c: str(t) for c, t in df.dtypes.items()}


@pytest.fixture
def loaded(db):
    """Fixture datasets ingested; nothing computed yet."""
    catalog = MetadataCatalog.load()
    with db.transaction() as session:
        for dataset in catalog.dataset_dependencies("BIODIV"):
            Repository(session).replace_dataset(dataset.code, normalize_unsdg_dataset(dataset, PAYLOADS[dataset.source.query_code]).observations)
    return db


def test_notebook_workflow(loaded):
    with SSPI(database=loaded) as sspi:
        assert sspi.query(indicators=["BIODIV"]).empty  # nothing computed yet: query is read-only

        result = sspi.run("BIODIV")  # explicit computation
        assert result.written == 1590

        marine = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2018, 2023))
        biodiv = sspi.query(indicators=["BIODIV"], countries=["MYS", "AUT"], years=(2018, 2023))

    assert list(marine.columns) == list(DATASET_DTYPES) and dtypes(marine) == DATASET_DTYPES
    assert marine["year"].tolist() == list(range(2018, 2024)) and set(marine["country_code"]) == {"MYS"}
    assert marine.loc[marine["year"] == 2020, "value"].item() == 19.70109 and set(marine["unit"]) == {"PERCENT"}

    assert list(biodiv.columns) == list(INDICATOR_DTYPES) and dtypes(biodiv) == INDICATOR_DTYPES
    assert biodiv[["country_code", "year"]].values.tolist() == [["AUT", y] for y in range(2018, 2024)] + [["MYS", y] for y in range(2018, 2024)]
    mys_2020 = biodiv[(biodiv["country_code"] == "MYS") & (biodiv["year"] == 2020)].iloc[0]
    aut_2020 = biodiv[(biodiv["country_code"] == "AUT") & (biodiv["year"] == 2020)].iloc[0]
    assert (mys_2020["score"], bool(mys_2020["imputed"]), mys_2020["unit"]) == (0.2972865333333333, False, "Index")
    assert (aut_2020["score"], bool(aut_2020["imputed"])) == (0.5858737782051282, True)


def test_dataset_queries_for_every_biodiv_dependency(loaded):
    with SSPI(database=loaded) as sspi:
        codes = list(sspi.indicator("BIODIV").dataset_codes)
        df = sspi.query(datasets=codes, countries=["MYS", "AUT"], years=(2020, 2020))
        with_prov = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2020, 2020), include_provenance=True)
    assert df[["dataset_code", "country_code"]].values.tolist() == [["UNSDG_FRSHWT", "AUT"], ["UNSDG_FRSHWT", "MYS"], ["UNSDG_MARINE", "MYS"], ["UNSDG_TERRST", "AUT"], ["UNSDG_TERRST", "MYS"]]
    assert with_prov["provenance"][0]["source_series"] == "ER_MRN_MPA"
    assert dtypes(with_prov) == {**DATASET_DTYPES, "provenance": "object"}


def test_score_inputs_on_request(loaded):
    with SSPI(database=loaded) as sspi:
        sspi.run("BIODIV")
        df = sspi.query(indicators=["BIODIV"], countries=["AUT"], years=(2020, 2020), include_inputs=True)
    (inputs,) = df["inputs"].tolist()
    assert {i["dataset_code"]: (i["imputed"], i["imputation_method"]) for i in inputs} == {
        "UNSDG_MARINE": (True, "ImputeReferenceClassAverage"),
        "UNSDG_TERRST": (False, None),
        "UNSDG_FRSHWT": (False, None),
    }


def test_empty_valid_queries_keep_the_schema(loaded):
    with SSPI(database=loaded) as sspi:
        sspi.run("BIODIV")
        no_years = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(1800, 1801))
        no_country = sspi.query(indicators=["BIODIV"], countries=["XKX"])
    assert len(no_years) == 0 and dtypes(no_years) == DATASET_DTYPES
    assert len(no_country) == 0 and dtypes(no_country) == INDICATOR_DTYPES
    assert no_country["imputed"].dtype == np.dtype("bool")


def test_query_is_read_only_and_run_is_the_only_writer(loaded):
    with SSPI(database=loaded) as sspi:
        sspi.query(indicators=["BIODIV"])
        sspi.query(datasets=["UNSDG_MARINE"])
        with loaded.transaction() as session:
            assert Repository(session).get_scores() == []
        before = sspi.query(datasets=["UNSDG_MARINE"])
        sspi.run("BIODIV")
        after = sspi.query(datasets=["UNSDG_MARINE"])
    assert before.equals(after)  # running an indicator never touches observations


def test_errors_arrive_before_any_read(loaded):
    with SSPI(database=loaded) as sspi:
        with pytest.raises(InvalidQueryError):
            sspi.query(datasets=["UNSDG_MARINE"], indicators=["BIODIV"])
        with pytest.raises(UnknownCodeError):
            sspi.query(indicators=["REDLST", "NOPE"])
        with pytest.raises(UnknownCodeError, match="no executable definition"):
            sspi.run("REDLST")
        assert sspi.query(indicators=["REDLST"]).empty  # known to metadata, queryable, just not computed
