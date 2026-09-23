"""Importing the package needs nothing but the filesystem and Python.

Runs in a fresh interpreter started from an empty directory with an empty
environment (no .env in cwd, no DATABASE_URL), with an audit hook that records
every file open and fails on any socket connection, and a wrapped
`sqlalchemy.create_engine` that fails if anything builds an engine at import.
"""

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

    import sqlalchemy
    engines = []
    _real_create_engine = sqlalchemy.create_engine
    sqlalchemy.create_engine = lambda *a, **k: engines.append(a) or _real_create_engine(*a, **k)

    import sspi
    import sspi.scoring
    import sspi.metadata
    import sspi.db
    import sspi.ingestion
    import sspi.ingestion.unsdg
    from sspi.scoring import goalpost
    from sspi.metadata import CountryCatalog, MetadataCatalog

    assert engines == [], f"importing sspi built an engine: {engines}"
    data_opens = [p for p in opened if "/metadata/data/" in p.replace("\\\\", "/")]
    assert not data_opens, f"importing packages read metadata files: {data_opens}"

    catalog = MetadataCatalog.load()
    print(",".join(catalog.indicator("BIODIV").dataset_codes))
    print(catalog.dataset("UNSDG_MARINE").name)
    print(goalpost(5, 0, 10))
    countries = CountryCatalog.load()
    print(len(countries.group("SSPI67").members), countries.country("AUT").name)

    from sspi import SSPI
    facade = SSPI()
    print(facade.indicator("BIODIV").code, facade.owns_database)
    facade.close()
    assert engines == [], "constructing SSPI built an engine"

    from sspi.db import Database
    from sspi.errors import DatabaseConfigurationError
    try:
        Database.from_settings(env_file=None)
    except DatabaseConfigurationError as exc:
        print("config-error:", "DATABASE_URL" in str(exc))
    assert engines == [], "configuration failure built an engine"
    """
)


def test_import_reads_no_metadata_builds_no_engine_and_needs_no_env(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=tmp_path,
        env={},  # no PATH, no DATABASE_URL, no dotenv, nothing
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "UNSDG_MARINE,UNSDG_TERRST,UNSDG_FRSHWT",
        "Marine Areas Protected",
        "0.5",
        "66 Austria",
        "BIODIV True",
        "config-error: True",
    ]
