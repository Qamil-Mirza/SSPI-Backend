"""indicator_score.imputed is derived on write, verified on read, and the
database itself enforces observed-over-imputed precedence on upsert."""

import pytest
from sqlalchemy import text

from sspi.db import Repository
from sspi.errors import ScoreIntegrityError
from sspi.imputation import is_imputed
from sspi.scoring import IndicatorScore, Observation


def obs(code, value=50.0, **prov):
    return Observation(code, "MYS", 2020, value, "PERCENT", prov)


OBSERVED_INPUTS = (obs("UNSDG_MARINE"), obs("UNSDG_TERRST"), obs("UNSDG_FRSHWT"))
IMPUTED_INPUTS = (obs("UNSDG_MARINE", 36.5, imputed=True, imputation_method="ImputeReferenceClassAverage"), obs("UNSDG_TERRST"), obs("UNSDG_FRSHWT"))


def observed(value=0.5, country="MYS"):
    return IndicatorScore("BIODIV", country, 2020, value, "Index", OBSERVED_INPUTS)


def imputed(value=0.4, country="MYS"):
    return IndicatorScore("BIODIV", country, 2020, value, "Index", IMPUTED_INPUTS)


def stored(db):
    with db.transaction() as session:
        rows = session.execute(text("SELECT country_code, score, imputed FROM indicator_score ORDER BY country_code")).all()
    return [tuple(r) for r in rows]


def test_observed_score_persists_with_imputed_false(db):
    with db.transaction() as session:
        Repository(session).save_scores([observed()])
    assert stored(db) == [("MYS", 0.5, False)]
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
    assert loaded == observed() and not is_imputed(loaded)


def test_imputed_score_persists_with_imputed_true(db):
    with db.transaction() as session:
        Repository(session).save_scores([imputed()])
    assert stored(db) == [("MYS", 0.4, True)]
    with db.transaction() as session:
        (loaded,) = Repository(session).get_scores()
    assert loaded == imputed() and is_imputed(loaded)


def test_observed_replaces_existing_imputed(db):
    with db.transaction() as session:
        Repository(session).save_scores([imputed()])
    with db.transaction() as session:
        assert Repository(session).save_scores([observed()]) == 1
    assert stored(db) == [("MYS", 0.5, False)]


def test_imputed_cannot_overwrite_existing_observed(db):
    with db.transaction() as session:
        Repository(session).save_scores([observed()])
    with db.transaction() as session:
        assert Repository(session).save_scores([imputed(), imputed(country="AUT")]) == 1  # only AUT written
    assert stored(db) == [("AUT", 0.4, True), ("MYS", 0.5, False)]


def test_observed_replaces_observed_and_imputed_replaces_imputed(db):
    with db.transaction() as session:
        Repository(session).save_scores([observed(0.5), imputed(0.4, country="AUT")])
    with db.transaction() as session:
        assert Repository(session).save_scores([observed(0.6), imputed(0.3, country="AUT")]) == 2
    assert stored(db) == [("AUT", 0.3, True), ("MYS", 0.6, False)]


def test_replace_indicator_scores_derives_the_flag_for_every_row(db):
    with db.transaction() as session:
        Repository(session).replace_indicator_scores("BIODIV", [observed(), imputed(country="AUT")])
    assert stored(db) == [("AUT", 0.4, True), ("MYS", 0.5, False)]


def test_get_scores_can_filter_on_the_flag(db):
    with db.transaction() as session:
        Repository(session).save_scores([observed(), imputed(country="AUT")])
    with db.transaction() as session:
        repo = Repository(session)
        assert [s.country_code for s in repo.get_scores(imputed=True)] == ["AUT"]
        assert [s.country_code for s in repo.get_scores(imputed=False)] == ["MYS"]
        assert [s.country_code for s in repo.get_scores()] == ["AUT", "MYS"]


def test_stored_flag_disagreeing_with_inputs_is_a_data_integrity_error_on_read(db):
    with db.transaction() as session:
        Repository(session).save_scores([observed(), imputed(country="AUT")])
    with db.transaction() as session:
        session.execute(text("UPDATE indicator_score SET imputed = true WHERE country_code = 'MYS'"))
    with pytest.raises(ScoreIntegrityError, match="BIODIV/MYS/2020") as info:
        with db.transaction() as session:
            Repository(session).get_scores()
    assert "stored imputed=True" in str(info.value) and "inputs" in str(info.value)


def test_callers_cannot_supply_the_flag():
    assert not hasattr(IndicatorScore("BIODIV", "MYS", 2020, 0.5, "Index", ()), "imputed")
