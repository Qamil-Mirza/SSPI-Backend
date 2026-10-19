"""Access to the original WEF workbook and the related files kept outside the
repository, for the opt-in tests (test_golden_wef_real_data.py).

WEF data is not distributed with the repository while its licence terms are
open (docs/data-governance-review.md, GOV-2). The files live in the
directory named by ``SSPI_WEF_REAL_DATA`` (by convention ``local-data/wef``,
which git ignores): ``WEF-GCIHH.xlsx``, the original workbook;
``responses/EG.ELC.ACCS.ZS.json``, the full World Bank response read with it;
``golden/*_cases.json``, the pinned legacy code's output on them
(``generate_wef_cases.py --real DIR``). Every read checks the file against
the committed ``tests/fixtures/wef/REAL_DATA.sha256``; a missing or changed
file fails, never skips.
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

ENVIRONMENT_VARIABLE = "SSPI_WEF_REAL_DATA"
REAL_DATA = os.environ.get(ENVIRONMENT_VARIABLE)
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "wef" / "REAL_DATA.sha256"
MARKS = [pytest.mark.wef_real_data, pytest.mark.skipif(not REAL_DATA, reason=f"set {ENVIRONMENT_VARIABLE} to the directory of the original WEF workbook (local-data/wef)")]


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
