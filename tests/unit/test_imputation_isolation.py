"""The imputation module is pure: importing it pulls in no persistence,
ingestion, metadata, HTTP or ORM code, and it reads nothing from disk."""

import subprocess
import sys
import textwrap

SCRIPT = textwrap.dedent(
    """
    import sys
    opened = []
    sys.addaudithook(lambda event, args: opened.append(str(args[0])) if event == "open" else None)
    import sspi.imputation
    forbidden = [m for m in sys.modules if m.split(".")[0] in ("sqlalchemy", "psycopg", "httpx", "pycountry", "yaml", "pandas")
                 or m in ("sspi.db", "sspi.ingestion", "sspi.metadata", "sspi.config")]
    assert not forbidden, forbidden
    data_opens = [p for p in opened if "/sspi/" in p.replace("\\\\", "/") and not p.endswith((".py", ".pyc"))]
    assert not data_opens, data_opens
    print("pure")
    """
)


def test_import_is_pure(tmp_path):
    result = subprocess.run([sys.executable, "-c", SCRIPT], cwd=tmp_path, env={}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "pure"


def test_module_source_imports_nothing_persistent():
    from pathlib import Path

    import sspi.imputation as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for name in ("sspi.db", "Repository", "Database", "sqlalchemy", "sspi.ingestion", "sspi.metadata", "CountryCatalog"):
        assert name not in source, name
