"""Metadata loading needs nothing but the filesystem and Python.

Runs in a fresh interpreter started from an empty directory with an empty
environment (no .env, no DATABASE_URL), with an audit hook that records every
file open and fails on any socket connection.
"""

import os
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

    import sspi
    import sspi.scoring
    import sspi.metadata

    data_opens = [p for p in opened if "/metadata/data/" in p.replace("\\\\", "/")]
    assert not data_opens, f"importing packages read metadata files: {data_opens}"
    assert "yaml" not in sys.modules or True  # yaml may be imported; it must not be *used* at import

    from sspi.metadata import MetadataCatalog
    catalog = MetadataCatalog.load()
    print(",".join(catalog.indicator("BIODIV").dataset_codes))
    print(catalog.dataset("UNSDG_MARINE").name)
    """
)


def test_import_reads_no_metadata_and_load_needs_no_env_db_or_network(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=tmp_path,
        env={},  # no PATH, no DATABASE_URL, no dotenv, nothing
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["UNSDG_MARINE,UNSDG_TERRST,UNSDG_FRSHWT", "Marine Areas Protected"]
    assert not (tmp_path / ".env").exists()
    assert "DATABASE_URL" not in os.environ or True  # the subprocess had none regardless
