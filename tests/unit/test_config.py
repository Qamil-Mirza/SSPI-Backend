"""Database configuration is deterministic: environment first, then the
project-root .env. Never the process working directory."""

import pytest

from sspi.config import DEFAULT_ENV_FILE, PROJECT_ROOT, load_settings
from sspi.errors import DatabaseConfigurationError


def test_default_env_file_is_project_root_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql+psycopg://cwd/should_be_ignored\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert DEFAULT_ENV_FILE == PROJECT_ROOT / ".env"
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    if DEFAULT_ENV_FILE.exists():
        assert load_settings().database_url != "postgresql+psycopg://cwd/should_be_ignored"
    else:
        with pytest.raises(DatabaseConfigurationError):
            load_settings()


def test_environment_variable_wins_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://file/db\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert load_settings(env_file=env_file).database_url == "postgresql+psycopg://env/db"


def test_env_file_used_when_environment_is_unset(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://file/db\nSOME_OTHER_KEY=ignored\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert load_settings(env_file=env_file).database_url == "postgresql+psycopg://file/db"


def test_missing_configuration_raises_clear_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        load_settings(env_file=None)


def test_database_from_settings_does_not_connect(monkeypatch):
    from sspi.db import Database

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere")
    db = Database.from_settings(env_file=None)
    assert db.url.endswith("/nowhere")
    engine = db.engine  # lazy object construction only, no connection attempt
    assert engine.url.database == "nowhere"
    db.dispose()
