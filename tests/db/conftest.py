"""Isolated PostgreSQL fixtures.

Set ``SSPI_TEST_DATABASE_URL`` to a SQLAlchemy URL for a PostgreSQL *server*
whose role may CREATE DATABASE, for example::

    SSPI_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/postgres

A throwaway database named ``sspi_test_<random>`` is created for the session,
migrated with Alembic, and dropped afterwards. No pre-existing database is
touched. Without the variable every test in this directory is skipped.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from sspi.db import Database

REPO_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(str(item.fspath)).is_relative_to(Path(__file__).parent):
            item.add_marker(pytest.mark.postgres)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    server_url = os.environ.get("SSPI_TEST_DATABASE_URL")
    if not server_url:
        pytest.skip("SSPI_TEST_DATABASE_URL not set; PostgreSQL integration tests skipped")
    name = f"sspi_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(server_url).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :n AND pid <> pg_backend_pid()"),
                {"n": name},
            )
            conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> Database:
    command.upgrade(alembic_config(test_database_url), "head")
    database = Database(test_database_url)
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def db(migrated_database: Database) -> Database:
    """The migrated database with both tables emptied."""
    with migrated_database.transaction() as session:
        session.execute(text("TRUNCATE TABLE observation, indicator_score"))
    return migrated_database
