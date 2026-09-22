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
    assert [c["name"] for c in inspector.get_columns("indicator_score")] == ["indicator_code", "country_code", "year", "score", "unit", "inputs", "written_at"]
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
