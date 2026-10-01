"""Alembic migration creates exactly the approved tables and agrees with the ORM."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from sspi.db.base import Base
from tests.db.conftest import alembic_config


def test_migrated_schema_matches_orm_metadata(migrated_database):
    with migrated_database.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_only_approved_tables_exist(migrated_database):
    inspector = inspect(migrated_database.engine)
    assert sorted(inspector.get_table_names()) == ["alembic_version", "indicator_score", "observation"]
    assert [c["name"] for c in inspector.get_columns("observation")] == ["dataset_code", "country_code", "year", "value", "unit", "provenance", "written_at"]
    assert [c["name"] for c in inspector.get_columns("indicator_score")] == ["indicator_code", "country_code", "year", "score", "unit", "inputs", "written_at", "imputed", "provenance"]
    assert inspector.get_pk_constraint("observation")["constrained_columns"] == ["dataset_code", "country_code", "year"]
    assert inspector.get_pk_constraint("indicator_score")["constrained_columns"] == ["indicator_code", "country_code", "year"]
    assert inspector.get_indexes("observation") == []
    assert inspector.get_indexes("indicator_score") == []


def test_downgrade_and_upgrade_round_trip(migrated_database, test_database_url):
    cfg = alembic_config(test_database_url)
    command.downgrade(cfg, "base")
    assert sorted(inspect(migrated_database.engine).get_table_names()) == ["alembic_version"]
    command.upgrade(cfg, "head")
    assert sorted(inspect(migrated_database.engine).get_table_names()) == ["alembic_version", "indicator_score", "observation"]


def test_imputed_column_is_boolean_not_null_without_default(migrated_database):
    column = next(c for c in inspect(migrated_database.engine).get_columns("indicator_score") if c["name"] == "imputed")
    assert column["nullable"] is False and column["default"] is None
    assert str(column["type"]).upper() == "BOOLEAN"


def test_migration_0002_backfills_the_flag_from_inputs(migrated_database, test_database_url):
    from sqlalchemy import text

    cfg = alembic_config(test_database_url)
    command.downgrade(cfg, "0001")
    with migrated_database.transaction() as session:
        session.execute(text("TRUNCATE TABLE observation, indicator_score"))
        session.execute(
            text(
                "INSERT INTO indicator_score (indicator_code, country_code, year, score, unit, inputs) VALUES "
                "('BIODIV', 'MYS', 2020, 0.5, 'Index', '{\"observations\": [{\"provenance\": {}}], \"computed\": []}'::jsonb), "
                "('BIODIV', 'AUT', 2020, 0.4, 'Index', '{\"observations\": [{\"provenance\": {\"imputed\": true}}], \"computed\": []}'::jsonb)"
            )
        )
    command.upgrade(cfg, "head")
    with migrated_database.transaction() as session:
        rows = session.execute(text("SELECT country_code, imputed FROM indicator_score ORDER BY country_code")).all()
        session.execute(text("TRUNCATE TABLE indicator_score"))
    assert [tuple(r) for r in rows] == [("AUT", True), ("MYS", False)]


def test_migration_0003_gives_old_rows_an_empty_provenance(migrated_database, test_database_url):
    """Rows written before 0003 were all produced directly by a formula, so {} is their truthful derivation record."""
    from sqlalchemy import text

    cfg = alembic_config(test_database_url)
    command.downgrade(cfg, "0002")
    with migrated_database.transaction() as session:
        session.execute(text("TRUNCATE TABLE observation, indicator_score"))
        session.execute(
            text(
                "INSERT INTO indicator_score (indicator_code, country_code, year, score, unit, inputs, imputed) VALUES "
                "('REDLST', 'MYS', 2020, 0.5, 'Index', '{\"observations\": [{\"dataset_code\": \"UNSDG_REDLST\", \"country_code\": \"MYS\", \"year\": 2020, \"value\": 0.5, \"unit\": \"INDEX\", \"provenance\": {}}], \"computed\": []}'::jsonb, false)"
            )
        )
    command.upgrade(cfg, "head")
    column = next(c for c in inspect(migrated_database.engine).get_columns("indicator_score") if c["name"] == "provenance")
    assert column["nullable"] is False and "{}" in str(column["default"])
    from sspi.db import Repository

    with migrated_database.transaction() as session:
        assert session.execute(text("SELECT provenance FROM indicator_score")).scalar_one() == {}
        (score,) = Repository(session).get_scores(indicator_codes=["REDLST"])  # old-style row reads back, classified observed
        assert dict(score.provenance) == {} and score.score == 0.5
        session.execute(text("TRUNCATE TABLE indicator_score"))
