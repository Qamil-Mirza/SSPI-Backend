"""Differential test: the new scoring kernel must reproduce the OLD
`score_indicator` output exactly on every recorded case.

`scoring_cases.json` was produced by `generate_scoring_cases.py` running the
old implementation (see `generated_from.commit` inside the file). This test
needs nothing but the JSON: no old repository, no MongoDB, no old virtualenv.

Comparison is exact (`==`), not approximate. Both implementations perform the
same floating-point operations in the same order, so any difference is a real
behavioural mismatch and must be reported, not tolerated.
"""

import json
from pathlib import Path

import pytest

from sspi.scoring import ComputedSeries, goalpost, score_indicator
from tests.golden.functions import make_functions
from tests.legacy import documents_from_result, observations_from_documents

FIXTURE = Path(__file__).with_name("scoring_cases.json")
PAYLOAD = json.loads(FIXTURE.read_text())
FUNCTIONS = make_functions(goalpost)


def test_fixture_records_its_provenance():
    meta = PAYLOAD["generated_from"]
    assert meta["repository"] == "sspi-data-webapp"
    assert len(meta["commit"]) == 40
    assert meta["working_tree_dirty"] is False
    assert meta["source_function"].endswith(".score_indicator")


@pytest.mark.parametrize("case", PAYLOAD["cases"], ids=[c["name"] for c in PAYLOAD["cases"]])
def test_new_kernel_matches_old_implementation(case):
    unit = case["unit"]
    unit_arg = FUNCTIONS["unit"][unit["function"]] if isinstance(unit, dict) else unit
    specs = [ComputedSeries(code, u, FUNCTIONS["value"][fn]) for code, u, fn in case["computed_series"]]

    result = score_indicator(
        observations_from_documents(case["observations"]),
        case["indicator_code"],
        score_function=FUNCTIONS["score"][case["score_function"]],
        unit=unit_arg,
        computed_series=specs,
    )
    complete, incomplete = documents_from_result(result)

    assert complete == case["expected"]["complete"]
    assert incomplete == case["expected"]["incomplete"]
