"""Offline end to end: committed UN fixtures -> normalization -> PostgreSQL ->
run_indicator("BIODIV") -> observed + imputed scores -> PostgreSQL.

Recipients are the real SSPI67 group. Austria's rows are the executable legacy
behaviour for a landlocked country (marine filled from the reference class),
a documented conflict with the retired static metadata, preserved as is.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from sspi.db import Repository
from sspi.errors import IndicatorDefinitionError
from sspi.imputation import REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import run_indicator
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import CountryCatalog, MetadataCatalog
from sspi.scoring import Observation

FIXTURES = Path(__file__).parents[1] / "fixtures" / "unsdg"
PAYLOADS = {
    "14.5.1": json.loads((FIXTURES / "14_5_1_sample.json").read_text())["data"],
    "15.1.2": json.loads((FIXTURES / "15_1_2_sample.json").read_text())["data"],
}
FIXTURE_COUNTRIES = {"ALB", "AUT", "KEN", "MYS", "USA"}


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
    members = CountryCatalog.load().group("SSPI67").members
    absent_members = sorted(set(members) - FIXTURE_COUNTRIES)

    result = run_indicator("BIODIV", loaded)

    assert result.written == len(result.scores) == row_count(loaded)
    observed = {(s.country_code, s.year): s for s in result.observed_scores}
    imputed = {(s.country_code, s.year): s for s in result.imputed_scores}
    assert len(observed) == 78 and sorted({c for c, _ in observed}) == ["KEN", "MYS", "USA"]
    assert sorted({y for _, y in observed}) == list(range(2000, 2026))  # compute route: no year filter
    assert len(imputed) == 24 * (1 + len(absent_members))  # Austria + every SSPI67 member with no fixture rows
    assert sorted(y for c, y in imputed if c == "AUT") == list(range(2000, 2024))
    assert not any(c == "ALB" for c, _ in imputed) and not any(c == "ALB" for c, _ in observed)  # not SSPI67, marine only
    assert sorted({(u.country_code, u.year) for u in result.unscored}) == [("ALB", y) for y in range(2000, 2026)] + [("AUT", 2024), ("AUT", 2025)]

    aut = imputed[("AUT", 2020)]
    marine = next(o for o in aut.inputs if o.dataset_code == "UNSDG_MARINE")
    assert (marine.value, marine.provenance["imputation_method"], aut.score) == (36.56867346153846, REFERENCE_CLASS_AVERAGE, 0.5858737782051282)
    for member in absent_members:
        assert all(o.provenance["imputation_method"] == REFERENCE_CLASS_AVERAGE for o in imputed[(member, 2020)].inputs)
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
    before = run_indicator("BIODIV", loaded)
    assert sum(1 for s in before.imputed_scores if s.country_code == "AUT") == 24

    with loaded.transaction() as session:
        repo = Repository(session)
        usa_marine = repo.get_observations(dataset_codes=["UNSDG_MARINE"], countries=["USA"])
        repo.save_observations([Observation("UNSDG_MARINE", "AUT", o.year, o.value, o.unit, {"note": "test rows"}) for o in usa_marine])

    after = run_indicator("BIODIV", loaded)
    with loaded.transaction() as session:
        aut = Repository(session).get_scores(indicator_codes=["BIODIV"], countries=["AUT"])
    assert [a.year for a in aut] == list(range(2000, 2026)) and not any(is_imputed(a) for a in aut)
    assert len(after.imputed_scores) == len(before.imputed_scores) - 24
    assert after.written == row_count(loaded)


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
