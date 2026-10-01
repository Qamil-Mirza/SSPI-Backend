"""Compute-route parity evidence for WATMAN, ahead of its registration.

WATMAN is not an executable indicator yet: its legacy impute route needs the
imputation-strategy interface, which is pending approval. The compute route
is simple and its evidence is already committed (``watman_cases.json``), so
this test pins that the kernel and the formula reproduce it from the derived
UNSDG_CWUEFF and the dimension-filtered UNSDG_WTSTRS. When WATMAN is
registered, this file should be folded into its full parity test.
"""

import json

import pytest

from sspi.indicators import IndicatorDefinition, compute_indicator
from sspi.ingestion.runner import fetch_and_normalize, resolve_datasets
from sspi.metadata import MetadataCatalog
from sspi.scoring import goalpost
from tests.golden.parity import assert_parity, load_cases, score_records, source_fixtures

CASES = load_cases("watman_cases.json")


def score_watman_compute_route(UNSDG_CWUEFF, UNSDG_WTSTRS):  # noqa: N803 - the legacy compute_watman.score_watman, verbatim
    return (goalpost(UNSDG_CWUEFF, -20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2


COMPUTE_ROUTE_ONLY = IndicatorDefinition("WATMAN", score_watman_compute_route, None, imputation_years=None, recipient_group=None)


class _Client:
    def __init__(self, rows_by_query):
        self.rows_by_query = rows_by_query

    def fetch_indicator(self, code):
        return self.rows_by_query[code]


@pytest.fixture(scope="module")
def result():
    catalog = MetadataCatalog.load()
    rows = {json.loads(p.read_text())["indicator"]: json.loads(p.read_text())["data"] for p in source_fixtures(CASES)}
    results, _ = fetch_and_normalize(resolve_datasets(["UNSDG_CWUEFF", "UNSDG_WTSTRS"], catalog), _Client(rows), metadata=catalog)
    return compute_indicator(COMPUTE_ROUTE_ONLY, [o for _, r in results for o in r.observations], recipients=())


def test_golden_file_records_the_legacy_facts():
    assert CASES["indicator_code"] == "WATMAN" and CASES["impute_route_exists"] is True
    assert CASES["goalposts"] == {"UNSDG_CWUEFF": [-20, 50], "UNSDG_WTSTRS": [100, 0]}


def test_compute_route_scores_match_legacy(result):
    assert_parity("WATMAN compute-route scores", score_records(result.observed_scores, imputation=False), CASES["scores"])
    assert len(result.observed_scores) == 108
    assert sorted({(u.country_code, u.year) for u in result.unscored}) == [tuple(i) for i in CASES["incomplete_identities"]]
    assert sorted({y for _, y in CASES["incomplete_identities"]}) == list(range(2000, 2024))  # 2000-2005 has WTSTRS but no CWUEFF for every country
