"""Access to the real WHO GHO files kept outside the repository, for the
opt-in tests (test_golden_who_real_data.py, and the real-data run of
tests/db/test_healthcare_end_to_end.py).

WHO extracts are not distributed with the repository while redistribution
rights are open (docs/data-governance-review.md, GOV-1). The files live in
the directory named by ``SSPI_WHO_REAL_DATA`` (by convention
``local-data/who``, which git ignores): ``fixtures/<code>_sample.json``, the
GHO row subsets of 2026-10-18; ``golden/*_cases.json``, the legacy output on
them; ``responses/<date>/<code>.json``, the full GHO responses. Every read
checks the file against the committed ``tests/fixtures/who/REAL_DATA.sha256``;
a missing or changed file fails, never skips.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from tests.golden.parity import REPO_ROOT

ENVIRONMENT_VARIABLE = "SSPI_WHO_REAL_DATA"
REAL_DATA = os.environ.get(ENVIRONMENT_VARIABLE)
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "who" / "REAL_DATA.sha256"
MARKS = [pytest.mark.who_real_data, pytest.mark.skipif(not REAL_DATA, reason=f"set {ENVIRONMENT_VARIABLE} to the directory of the real WHO files (local-data/who)")]


def checksums() -> dict[str, str]:
    """Relative path -> SHA-256, from the committed manifest."""
    return {name: digest for digest, name in (line.split("  ", 1) for line in MANIFEST.read_text().splitlines() if line.strip())}


@cache
def real_bytes(relative: str) -> bytes:
    """A real file, refused unless it is byte-for-byte the validated one."""
    expected = checksums()[relative]
    path = Path(REAL_DATA) / relative
    assert path.is_file(), f"{path}: missing ({ENVIRONMENT_VARIABLE}={REAL_DATA})"
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == expected, f"{relative}: SHA-256 differs from {MANIFEST.name}"
    return content


def real_json(relative: str) -> Any:
    return json.loads(real_bytes(relative).decode("utf-8"))
