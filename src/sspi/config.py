"""Runtime configuration.

Nothing here runs at import time. ``load_settings`` is called only by code
that needs a database. Resolution order is deterministic and independent of
the process working directory:

1. environment variables (``DATABASE_URL``),
2. the project-root ``.env`` for local development (``DEFAULT_ENV_FILE``),
   or an explicit ``env_file`` passed by the caller; ``None`` disables dotenv.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from sspi.errors import DatabaseConfigurationError

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

USE_DEFAULT_ENV_FILE: Final = object()
"""Sentinel: use ``DEFAULT_ENV_FILE`` (distinct from ``None``, which means no dotenv)."""


class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings(env_file: str | Path | None | object = USE_DEFAULT_ENV_FILE) -> Settings:
    """Build ``Settings`` now, raising ``DatabaseConfigurationError`` if incomplete."""
    kwargs = {} if env_file is USE_DEFAULT_ENV_FILE else {"_env_file": env_file}
    try:
        return Settings(**kwargs)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured. Set the DATABASE_URL environment variable "
            f"or add it to {DEFAULT_ENV_FILE}."
        ) from exc
