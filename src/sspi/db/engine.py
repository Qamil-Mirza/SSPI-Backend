"""Lazy engine and session construction, and the one transaction boundary.

Nothing connects until a session is used. ``Database.transaction()`` is the
single place that begins, commits, and rolls back; repositories never do.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sspi.config import USE_DEFAULT_ENV_FILE, Settings, load_settings


class Database:
    """A PostgreSQL database reachable at ``url``.

    Construct directly with a URL, or via :meth:`from_settings`. The engine is
    created on first use and can be released with :meth:`dispose`.
    """

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self._url = url
        self._echo = echo
        self._engine: Engine | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        env_file: str | Path | None | object = USE_DEFAULT_ENV_FILE,
    ) -> Database:
        """Use ``DATABASE_URL`` from the environment or the project ``.env``.

        Raises ``DatabaseConfigurationError`` if neither provides it.
        """
        if settings is None:
            settings = load_settings(env_file=env_file)
        return cls(settings.database_url)

    @property
    def url(self) -> str:
        return self._url

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = sqlalchemy.create_engine(self._url, pool_pre_ping=True, echo=self._echo)
        return self._engine

    def session(self) -> Session:
        """A plain session. The caller owns commit and rollback; prefer :meth:`transaction`."""
        return Session(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """One transaction: BEGIN on entry, COMMIT on clean exit, ROLLBACK on any exception."""
        with self.session() as session, session.begin():
            yield session

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
