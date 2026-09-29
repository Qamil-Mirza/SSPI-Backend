"""SSPI(): lazy, explicit about database ownership, and a thin delegate."""

import subprocess
import sys
import textwrap

import pytest

from sspi import SSPI
from sspi.db import Database
from sspi.errors import DatabaseConfigurationError, UnknownCodeError
from sspi.metadata import CountryCatalog, IndicatorMetadata, MetadataCatalog


def test_root_package_exports_the_facade_lazily(tmp_path):
    script = textwrap.dedent(
        """
        import sys
        opened = []
        sys.addaudithook(lambda e, a: opened.append(str(a[0])) if e == "open" else None)
        import sspi
        import sspi.imputation
        assert "pandas" not in sys.modules and "sspi.facade" not in sys.modules
        import sqlalchemy
        engines = []
        real = sqlalchemy.create_engine
        sqlalchemy.create_engine = lambda *a, **k: engines.append(a) or real(*a, **k)
        from sspi import SSPI
        s = SSPI()
        s.close()
        with SSPI() as t:
            pass
        assert engines == [], engines
        assert not [p for p in opened if "/metadata/data/" in p.replace("\\\\", "/")], opened
        assert not [p for p in opened if p.endswith(".env")], opened
        print("lazy")
        """
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "lazy"


def test_missing_configuration_surfaces_on_the_first_database_call(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sspi = SSPI(env_file=None)
    sspi.indicator("BIODIV")  # metadata works without a database
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        sspi.query(datasets=["UNSDG_MARINE"])
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        sspi.run("BIODIV")


def test_validation_errors_come_before_any_database_access(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sspi = SSPI(env_file=None)
    with pytest.raises(UnknownCodeError):
        sspi.query(datasets=["NOPE"])
    with pytest.raises(UnknownCodeError, match="no executable definition"):
        sspi.run("NITROG")  # known to metadata, not executable


@pytest.mark.parametrize("constructor_arg", [None, "postgresql+psycopg://nobody@localhost:1/none"])
def test_facade_owns_and_disposes_databases_it_creates(constructor_arg, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody@localhost:1/none")
    disposed = []
    monkeypatch.setattr(Database, "dispose", lambda self: disposed.append(self.url))
    with SSPI(database=constructor_arg) as sspi:
        assert sspi.database.url == "postgresql+psycopg://nobody@localhost:1/none"
        assert sspi.owns_database is True
    assert disposed == ["postgresql+psycopg://nobody@localhost:1/none"]
    sspi.close()  # idempotent
    assert len(disposed) == 1


def test_facade_never_disposes_an_injected_database(monkeypatch):
    disposed = []
    monkeypatch.setattr(Database, "dispose", lambda self: disposed.append(self.url))
    injected = Database("postgresql+psycopg://nobody@localhost:1/none")
    with SSPI(database=injected) as sspi:
        assert sspi.database is injected and sspi.owns_database is False
    sspi.close()
    assert disposed == []


def test_rejects_other_database_arguments():
    with pytest.raises(TypeError, match="database"):
        SSPI(database=42)


def test_metadata_conveniences_delegate_to_the_catalogs():
    sspi = SSPI(env_file=None)
    assert isinstance(sspi.indicator("BIODIV"), IndicatorMetadata)
    assert sspi.indicator("BIODIV") is sspi.metadata.indicator("BIODIV")
    assert sspi.dataset("UNSDG_MARINE").source.organization_code == "UNSDG"
    assert sspi.country("MYS").name == "Malaysia"
    assert sspi.country_group("SSPI67").members == CountryCatalog.load().group("SSPI67").members
    assert isinstance(sspi.metadata, MetadataCatalog) and sspi.metadata is sspi.metadata  # loaded once
    assert sspi.executable_indicators() == ("BIODIV", "REDLST")
    assert len(sspi.metadata.indicators()) == 57 and "BIODIV" in {i.code for i in sspi.metadata.indicators()}
    with pytest.raises(UnknownCodeError):
        sspi.indicator("NOPE")


def test_run_delegates_to_run_indicator_with_the_facade_resources(monkeypatch):
    import sspi.facade as facade

    calls = []
    sentinel = object()

    def fake_run_indicator(code, database, *, metadata, countries):
        calls.append((code, database, metadata, countries))
        return sentinel

    monkeypatch.setattr(facade, "run_indicator", fake_run_indicator)
    injected = Database("postgresql+psycopg://nobody@localhost:1/none")
    sspi = SSPI(database=injected)
    assert sspi.run("BIODIV") is sentinel
    (code, database, metadata, countries), = calls
    assert code == "BIODIV" and database is injected and metadata is sspi.metadata and countries is sspi.countries


def test_ingest_validates_before_resolving_any_database(monkeypatch):
    from sspi.errors import NotIngestibleError

    monkeypatch.delenv("DATABASE_URL", raising=False)
    sspi = SSPI(env_file=None)
    with pytest.raises(UnknownCodeError):
        sspi.ingest("NOT_REAL")
    with pytest.raises(NotIngestibleError, match="no ingestion path"):
        sspi.ingest("UNSDG_AIRPOL")
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL"):
        sspi.ingest("UNSDG_MARINE")  # valid request: only now is a database needed


def test_ingest_delegates_to_ingest_datasets_with_the_facade_resources(monkeypatch):
    import sspi.facade as facade

    calls = []
    sentinel = object()

    def fake_ingest_datasets(codes, database, *, metadata, client):
        calls.append((codes, database, metadata, client))
        return sentinel

    monkeypatch.setattr(facade, "ingest_datasets", fake_ingest_datasets)
    injected = Database("postgresql+psycopg://nobody@localhost:1/none")
    sspi = SSPI(database=injected)
    marker = object()
    assert sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST"], client=marker) is sentinel
    ((codes, database, metadata, client),) = calls
    assert codes == ["UNSDG_MARINE", "UNSDG_TERRST"] and database is injected and metadata is sspi.metadata and client is marker
