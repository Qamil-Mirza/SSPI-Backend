"""Aggregation on PostgreSQL: stored indicator scores -> run_aggregation ->
item_score -> SSPI().query(items=...).

A two-country SSPI67 keeps the fixture small; the methodology is unchanged.
"""

import warnings

import pytest
import yaml

from sspi import SSPI
from sspi.aggregation_runner import run_aggregation
from sspi.db import Repository
from sspi.errors import AggregationError, InvalidQueryError, StaleAggregationWarning, UnknownCodeError
from sspi.facade import ITEM_DTYPES
from sspi.metadata import CountryCatalog
from sspi.scoring import IndicatorScore

YEARS = range(2000, 2024)


@pytest.fixture
def two_countries(tmp_path):
    path = tmp_path / "country_groups.yaml"
    path.write_text(yaml.safe_dump({"groups": [{"code": "SSPI67", "members": ["USA", "FRA"]}]}))
    return CountryCatalog.load(path)


def score(code, country, year, value, imputed=False):
    return IndicatorScore(code, country, year, value, "Index", (), (), {"imputed": True, "imputation_method": "test"} if imputed else {})


def full(code, value, countries=("USA", "FRA"), imputed_at=()):
    return [score(code, c, y, value, (c, y) in imputed_at) for c in countries for y in YEARS]


@pytest.fixture
def scored(db):
    with db.transaction() as session:
        Repository(session).save_scores(
            full("BIODIV", 0.5, imputed_at={("FRA", 2001)})
            + full("REDLST", 1.0)
            + full("NITROG", 0.25)
            + full("WATMAN", 0.75, countries=("USA",))  # incomplete: no FRA
            + [score("BIODIV", "USA", 2024, 0.9), score("BIODIV", "BRA", 2010, 0.1)]  # outside window / group
        )
    return db


def test_run_writes_category_pillar_and_root_scores(scored, two_countries):
    run = run_aggregation(scored, countries=two_countries)
    assert run.included == ("BIODIV", "REDLST", "NITROG")
    assert {e.indicator_code: e.reason for e in run.excluded}["WATMAN"] == "24 country-years without a score, first FRA 2000"
    assert run.by_type == {"SSPI": 48, "Pillar": 48, "Category": 96} and run.scores_written == 192
    assert "3 indicators included: BIODIV, REDLST, NITROG" in run.report()
    with scored.transaction() as session:
        stored = {(s.item_code, s.country_code, s.year): s for s in Repository(session).get_item_scores()}
    assert stored[("ECO", "USA", 2000)].score == 0.75
    assert stored[("LND", "USA", 2000)].score == 0.25 and stored[("LND", "USA", 2000)].children == ("NITROG",)
    assert stored[("SUS", "FRA", 2023)].score == 0.5 and stored[("SSPI", "FRA", 2023)].score == 0.5
    assert stored[("SSPI", "FRA", 2023)].indicators == ("BIODIV", "REDLST", "NITROG")


def test_a_failed_run_leaves_the_previous_scores_untouched(scored, two_countries):
    run_aggregation(scored, countries=two_countries)
    with scored.transaction() as session:
        Repository(session).save_scores([score("NITROG", "FRA", 2010, None)])
    with pytest.raises(AggregationError, match="NULL score for NITROG FRA 2010"):
        run_aggregation(scored, countries=two_countries)
    with scored.transaction() as session:
        assert len(Repository(session).get_item_scores()) == 192


def test_each_run_replaces_the_whole_table(scored, two_countries):
    run_aggregation(scored, countries=two_countries)
    with scored.transaction() as session:
        Repository(session).delete_indicator_scores("BIODIV")
    run_aggregation(scored, countries=two_countries)
    with scored.transaction() as session:
        codes = {s.item_code for s in Repository(session).get_item_scores()}
    assert codes == {"SSPI", "SUS", "ECO", "LND"}


def test_query_items_derives_imputed_from_the_indicator_scores(scored, two_countries):
    sspi = SSPI(scored)
    sspi._countries = two_countries
    sspi.aggregate()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        frame = sspi.query(items=["SSPI", "ECO", "LND"], countries=["FRA"], years=(2000, 2001), include_inputs=True)
    assert {c: str(t) for c, t in frame.dtypes.items()} == {**ITEM_DTYPES, "inputs": "object"}
    rows = {(r.item_code, r.year): r for r in frame.itertuples()}
    assert rows[("ECO", 2001)].imputed and rows[("SSPI", 2001)].imputed and not rows[("LND", 2001)].imputed
    assert not rows[("ECO", 2000)].imputed
    assert rows[("ECO", 2001)].inputs == {"children": ("BIODIV", "REDLST"), "imputed_indicators": ("BIODIV",)}
    assert list(frame["item_code"]) == ["ECO", "ECO", "LND", "LND", "SSPI", "SSPI"]


def test_query_items_warns_when_indicator_scores_changed_after_aggregating(scored, two_countries):
    sspi = SSPI(scored)
    sspi._countries = two_countries
    sspi.aggregate()
    with scored.transaction() as session:
        Repository(session).save_scores([score("REDLST", "USA", 2005, 0.0)])
    with pytest.warns(StaleAggregationWarning, match="run SSPI\\(\\).aggregate\\(\\)"):
        sspi.query(items=["ECO"])


def test_an_empty_item_query_has_the_same_columns(db):
    frame = SSPI(db).query(items=["SSPI"])
    assert frame.empty and {c: str(t) for c, t in frame.dtypes.items()} == ITEM_DTYPES


def test_item_queries_are_validated_before_the_database(db):
    sspi = SSPI(db)
    with pytest.raises(UnknownCodeError):
        sspi.query(items=["BIODIV"])  # an indicator, not an item
    with pytest.raises(InvalidQueryError, match="exactly one of"):
        sspi.query(items=["SSPI"], indicators=["BIODIV"])
    with pytest.raises(InvalidQueryError, match="include_provenance applies to dataset and indicator queries only"):
        sspi.query(items=["SSPI"], include_provenance=True)
