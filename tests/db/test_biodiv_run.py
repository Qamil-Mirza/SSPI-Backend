"""Offline end to end: committed UN fixtures -> normalization -> PostgreSQL ->
run_indicator("BIODIV") -> observed + imputed scores -> PostgreSQL.

The registered imputation is the route production serves (BIODIV-6): the
nine hard-coded countries get, for every component, the mean of the other
countries' rows, so Austria's own terrestrial and freshwater rows are not
used; no other country is given reference values. The runner's generic
replacement behaviour is exercised through the pinned commit's route.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from sspi.db import Repository
from sspi.errors import ImputationError, IndicatorDefinitionError
from sspi.imputation import REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import registry, run_indicator
from sspi.indicators.biodiv import PINNED_IMPUTATION, PRODUCTION_REFERENCE_COUNTRIES
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}
FIXTURE_COUNTRIES = {"ALB", "AUT", "KEN", "MYS", "USA"}


class PinnedRegistry:
    """BIODIV with the pinned commit's impute route (SSPI67 recipients), for the runner's generic behaviour."""

    def get(self, code):
        return dataclasses.replace(registry.get(code), imputation=PINNED_IMPUTATION)


@pytest.fixture
def loaded(db):
    catalog = MetadataCatalog.load()
    with db.transaction() as session:
        repo = Repository(session)
        for dataset in catalog.dataset_dependencies("BIODIV"):
            repo.replace_dataset(dataset.code, normalize_unsdg_dataset(dataset, PAYLOADS[dataset.source.query_code]).observations)
    return db


def row_count(db):
    with db.transaction() as session:
        return session.execute(text("SELECT count(*) FROM indicator_score")).scalar_one()


def test_biodiv_runs_end_to_end_and_persists_both_score_sets(loaded):
    result = run_indicator("BIODIV", loaded)

    assert result.written == len(result.scores) == row_count(loaded)
    observed = {(s.country_code, s.year): s for s in result.observed_scores}
    imputed = {(s.country_code, s.year): s for s in result.imputed_scores}
    assert len(observed) == 78 and sorted({c for c, _ in observed}) == ["KEN", "MYS", "USA"]
    assert sorted({y for _, y in observed}) == list(range(2000, 2026))  # compute route: no year filter
    # production: exactly the nine listed countries, 2000-2023, nobody else (no SSPI67 recipient group)
    assert sorted({c for c, _ in imputed}) == sorted(PRODUCTION_REFERENCE_COUNTRIES) and len(imputed) == 9 * 24
    assert all(sorted(y for c, y in imputed if c == country) == list(range(2000, 2024)) for country in PRODUCTION_REFERENCE_COUNTRIES)
    assert not any(c == "ALB" for c, _ in imputed) and not any(c == "ALB" for c, _ in observed)  # marine only, not listed
    assert sorted({(u.country_code, u.year) for u in result.unscored}) == [("ALB", y) for y in range(2000, 2026)]

    aut = imputed[("AUT", 2020)]
    inputs = {o.dataset_code: o for o in aut.inputs}
    assert {code: o.provenance["imputation_method"] for code, o in inputs.items()} == dict.fromkeys(("UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"), REFERENCE_CLASS_AVERAGE)
    # Austria's own terrestrial and freshwater rows are not used: every component is the other countries' mean
    assert (inputs["UNSDG_MARINE"].value, inputs["UNSDG_TERRST"].value, inputs["UNSDG_FRSHWT"].value) == (36.56867346153846, 37.49614794871795, 32.80963846153846)
    assert aut.score == 0.3562481995726495 and {s.score for s in imputed.values()} == {0.3562481995726495}
    assert observed[("MYS", 2020)].score == 0.2972865333333333

    with loaded.transaction() as session:
        repo = Repository(session)
        stored_observed = repo.get_scores(indicator_codes=["BIODIV"], imputed=False)
        stored_imputed = repo.get_scores(indicator_codes=["BIODIV"], imputed=True)
    assert {(s.country_code, s.year): s for s in stored_observed} == observed
    assert {(s.country_code, s.year): s for s in stored_imputed} == imputed
    assert all(not is_imputed(s) for s in stored_observed) and all(is_imputed(s) for s in stored_imputed)


def test_rerun_converges_without_duplicates(loaded):
    first = run_indicator("BIODIV", loaded)
    second = run_indicator("BIODIV", loaded)
    assert second.written == first.written == row_count(loaded)
    with loaded.transaction() as session:
        assert Repository(session).get_scores(indicator_codes=["BIODIV"]) == sorted(second.scores, key=lambda s: (s.country_code, s.year))


def test_new_source_data_replaces_stale_imputed_rows(loaded):
    """Generic runner behaviour (full refresh removes stale imputed rows), on the pinned commit's route."""
    pinned = PinnedRegistry()
    before = run_indicator("BIODIV", loaded, registry=pinned)
    assert sum(1 for s in before.imputed_scores if s.country_code == "AUT") == 24

    with loaded.transaction() as session:
        repo = Repository(session)
        usa_marine = repo.get_observations(dataset_codes=["UNSDG_MARINE"], countries=["USA"])
        repo.save_observations([Observation("UNSDG_MARINE", "AUT", o.year, o.value, o.unit, {"note": "test rows"}) for o in usa_marine])

    after = run_indicator("BIODIV", loaded, registry=pinned)
    with loaded.transaction() as session:
        aut = Repository(session).get_scores(indicator_codes=["BIODIV"], countries=["AUT"])
    assert [a.year for a in aut] == list(range(2000, 2026)) and not any(is_imputed(a) for a in aut)
    assert len(after.imputed_scores) == len(before.imputed_scores) - 24
    assert after.written == row_count(loaded)


def test_a_listed_country_gaining_complete_data_stops_the_run_and_keeps_the_stored_scores(loaded):
    """BIODIV-6: production would store an observed and an imputed score for the same identity; no precedence is decided."""
    first = run_indicator("BIODIV", loaded)
    with loaded.transaction() as session:
        repo = Repository(session)
        before = repo.get_scores(indicator_codes=["BIODIV"])
        usa_marine = repo.get_observations(dataset_codes=["UNSDG_MARINE"], countries=["USA"])
        repo.save_observations([Observation("UNSDG_MARINE", "AUT", o.year, o.value, o.unit, {"note": "test rows"}) for o in usa_marine])

    with pytest.raises(ImputationError, match=r"BIODIV: 24 observed scores belong to countries .*BIODIV-6.*Nothing was written"):  # 2000-2023 only
        run_indicator("BIODIV", loaded)
    with loaded.transaction() as session:
        assert Repository(session).get_scores(indicator_codes=["BIODIV"]) == before and len(before) == first.written


def test_failed_write_leaves_the_previous_complete_result_intact(loaded, monkeypatch):
    first = run_indicator("BIODIV", loaded)
    with loaded.transaction() as session:
        before = Repository(session).get_scores(indicator_codes=["BIODIV"])

    original = Repository.replace_indicator_scores

    def delete_then_fail(self, code, scores):
        original(self, code, scores)
        raise RuntimeError("simulated failure after the replace")

    monkeypatch.setattr(Repository, "replace_indicator_scores", delete_then_fail)
    with pytest.raises(RuntimeError, match="simulated"):
        run_indicator("BIODIV", loaded)
    monkeypatch.undo()

    with loaded.transaction() as session:
        after = Repository(session).get_scores(indicator_codes=["BIODIV"])
    assert after == before and len(after) == first.written


def test_metadata_registry_mismatch_fails_before_touching_the_database(loaded):
    class FakeIndicator:
        dataset_codes = ("UNSDG_MARINE", "UNSDG_TERRST")

    class FakeCatalog:
        def indicator(self, code):
            return FakeIndicator()

    with pytest.raises(IndicatorDefinitionError, match="UNSDG_FRSHWT"):
        run_indicator("BIODIV", loaded, metadata=FakeCatalog())
    assert row_count(loaded) == 0
