"""Alembic environment.

URL resolution, in order: an explicit ``sqlalchemy.url`` set on the Config
(what the tests do), otherwise ``sspi.config.load_settings()``, i.e. the
``DATABASE_URL`` environment variable or the project-root ``.env``.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

import sspi.db.models  # noqa: F401  (registers the tables on Base.metadata)
from sspi.config import load_settings
from sspi.db.base import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or load_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
