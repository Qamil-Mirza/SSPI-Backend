"""Importing the registry and the BIODIV callables touches no database,
network, metadata file or ORM."""

import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent(
    """
    import sys
    opened = []
    def hook(event, args):
        if event == "open":
            opened.append(str(args[0]))
        if event in ("socket.connect", "socket.getaddrinfo"):
            raise RuntimeError(f"network access attempted: {event} {args}")
    sys.addaudithook(hook)
    import sspi.indicators.registry
    import sspi.indicators.biodiv
    forbidden = [m for m in sys.modules if m.split(".")[0] in ("sqlalchemy", "psycopg", "httpx", "yaml", "pandas", "pycountry")
                 or m in ("sspi.db", "sspi.ingestion", "sspi.config")]
    assert not forbidden, forbidden
    data_opens = [p for p in opened if "/sspi/" in p.replace("\\\\", "/") and not p.endswith((".py", ".pyc"))]
    assert not data_opens, data_opens
    print(sspi.indicators.registry.get("BIODIV").code)
    """
)


def test_registry_import_is_pure(tmp_path):
    result = subprocess.run([sys.executable, "-c", SCRIPT], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "BIODIV"


def test_package_import_builds_no_engine_and_reads_no_files(tmp_path):
    script = textwrap.dedent(
        """
        import sys
        opened = []
        sys.addaudithook(lambda e, a: opened.append(str(a[0])) if e == "open" else None)
        import sqlalchemy
        engines = []
        real = sqlalchemy.create_engine
        sqlalchemy.create_engine = lambda *a, **k: engines.append(a) or real(*a, **k)
        import sspi.indicators
        from sspi.indicators import run_indicator, compute_indicator, IndicatorRun, registry
        assert engines == [], engines
        data_opens = [p for p in opened if "/metadata/data/" in p.replace("\\\\", "/")]
        assert not data_opens, data_opens
        print("ok")
        """
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
