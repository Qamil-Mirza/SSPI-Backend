"""Access to the original Public Safety sources kept outside the repository,
for the opt-in tests (test_golden_public_safety_real_data.py).

None is distributed with the repository while its terms are open
(docs/data-governance-review.md): the UNODC workbook (GOV-3), the SSPI's
transcription of the ITU Global Cybersecurity Index (GOV-4) and the Fragile
States Index workbooks (GOV-5). Each tier
lives in the directory named by its environment variable (by convention
under ``local-data/``, which git ignores) and holds the original source and
``golden/*_cases.json``, the pinned legacy code's output on it
(``generate_public_safety_cases.py --real local-data``). Every read checks
the file against the tier's committed ``REAL_DATA.sha256``; a missing or
changed file fails, never skips.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from tests.golden.parity import REPO_ROOT, assert_pinned


@dataclass(frozen=True)
class PrivateTier:
    environment_variable: str
    organization: str  # tests/fixtures/<organization>/REAL_DATA.sha256
    guidance: str

    @property
    def directory(self) -> str | None:
        return os.environ.get(self.environment_variable)

    def checksums(self) -> dict[str, str]:
        """Relative path -> SHA-256, from the committed manifest."""
        manifest = REPO_ROOT / "tests" / "fixtures" / self.organization / "REAL_DATA.sha256"
        return {name: digest for digest, name in (line.split("  ", 1) for line in manifest.read_text().splitlines() if line.strip())}

    def read(self, relative: str) -> bytes:
        return _read(self, relative)

    def golden(self, name: str) -> dict[str, Any]:
        payload = json.loads(self.read(f"golden/{name}").decode("utf-8"))
        assert_pinned(payload, name)
        return payload


@cache
def _read(tier: PrivateTier, relative: str) -> bytes:
    """A real file, refused unless it is byte-for-byte the validated one."""
    expected = tier.checksums()[relative]
    path = Path(tier.directory) / relative
    assert path.is_file(), f"{path}: missing ({tier.environment_variable}={tier.directory})"
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == expected, f"{relative}: SHA-256 differs from tests/fixtures/{tier.organization}/REAL_DATA.sha256"
    return content


UNODC = PrivateTier("SSPI_UNODC_REAL_DATA", "unodc", "the directory of the original UNODC workbook (local-data/unodc)")
ITU = PrivateTier("SSPI_ITU_REAL_DATA", "itu", "the directory of the original GCI transcription (local-data/itu)")
FSI = PrivateTier("SSPI_FSI_REAL_DATA", "fsi", "the directory of the 18 original FSI workbooks (local-data/fsi)")
