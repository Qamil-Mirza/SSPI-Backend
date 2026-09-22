"""Transaction ownership lives in Database.transaction(); the repository never commits."""

import pytest
from sqlalchemy import text

from sspi.db import Database, Repository
from sspi.scoring import IndicatorScore, Observation


def test_exception_inside_transaction_rolls_everything_back(db):
    with pytest.raises(RuntimeError, match="boom"):
        with db.transaction() as session:
            repo = Repository(session)
            repo.save_observations([Observation("DS", "USA", 2020, 1.0, "u")])
            repo.save_scores([IndicatorScore("IND", "USA", 2020, 0.5, "Index", ())])
            raise RuntimeError("boom")
    with db.transaction() as session:
        repo = Repository(session)
        assert repo.get_observations() == []
        assert repo.get_scores() == []


def test_repository_does_not_commit_on_its_own(db):
    session = db.session()
    try:
        Repository(session).save_observations([Observation("DS", "USA", 2020, 1.0, "u")])
        with db.transaction() as other:
            assert other.execute(text("SELECT count(*) FROM observation")).scalar_one() == 0
        session.rollback()
    finally:
        session.close()
    with db.transaction() as session:
        assert Repository(session).get_observations() == []


def test_transaction_commits_on_clean_exit(db):
    with db.transaction() as session:
        Repository(session).save_observations([Observation("DS", "USA", 2020, 1.0, "u")])
    with db.transaction() as session:
        assert len(Repository(session).get_observations()) == 1


def test_reads_and_writes_share_one_transaction(db):
    with db.transaction() as session:
        repo = Repository(session)
        repo.save_observations([Observation("DS", "USA", 2020, 1.0, "u")])
        assert len(repo.get_observations()) == 1  # visible inside the same transaction


def test_database_object_is_reusable_and_disposable(test_database_url):
    database = Database(test_database_url)
    with database.transaction() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    database.dispose()
    with database.transaction() as session:  # engine is rebuilt lazily after dispose
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    database.dispose()
