"""The migration gate: nothing is ingestible or executable without committed
legacy parity evidence from the pinned commit and a row in the register.

See docs/indicator-migration.md.
"""

import json
import re

import pytest

from sspi.indicators import registry
from sspi.ingestion import SUPPORTED_DATASETS
from tests.golden.parity import HERE, INDICATOR_CASES, OBSERVATION_CASES, REPO_ROOT, assert_pinned, load_cases, source_fixtures

DOCS = REPO_ROOT / "docs"
CONFLICTS = (DOCS / "methodology-conflicts.md").read_text()
MIGRATION = (DOCS / "indicator-migration.md").read_text()
ENTRY = re.compile(r"^## ([A-Z0-9_]+-\d+) — (.+)$", re.MULTILINE)
STATUSES = {"unresolved", "reviewed", "resolved"}
REQUIRED_SECTIONS = (
    "Current executable behavior",
    "Conflicting evidence:",
    "Implementation decision in the new backend:",
    "Reason:",
    "Potential impact:",
    "Question for methodology review:",
    "Relevant legacy files:",
    "Relevant new-backend files:",
)


def entries() -> dict[str, str]:
    """Conflict ID -> entry text."""
    found = {}
    for match in ENTRY.finditer(CONFLICTS):
        following = re.search(r"^## ", CONFLICTS[match.end() :], re.MULTILINE)  # next entry, or the template section
        found[match.group(1)] = CONFLICTS[match.start() : match.end() + following.start() if following else len(CONFLICTS)]
    return found


def register_row(code: str) -> list[str]:
    rows = [line for line in MIGRATION.splitlines() if line.startswith(f"| {code} |")]
    assert len(rows) == 1, f"{code}: expected exactly one register row in docs/indicator-migration.md, found {len(rows)}"
    return [cell.strip() for cell in rows[0].strip("|").split("|")]


@pytest.mark.parametrize("path", sorted(HERE.glob("*_cases.json")), ids=lambda p: p.name)
def test_every_golden_file_comes_from_the_pinned_legacy_commit(path):
    assert_pinned(json.loads(path.read_text()), path.name)


def test_every_ingestible_dataset_has_observation_parity():
    assert set(SUPPORTED_DATASETS) == set(OBSERVATION_CASES)


def test_every_executable_indicator_has_score_parity():
    assert set(registry.codes()) == set(INDICATOR_CASES)


@pytest.mark.parametrize("code", sorted(OBSERVATION_CASES))
def test_dataset_evidence_is_committed_and_registered(code):
    case = load_cases(OBSERVATION_CASES[code])
    assert case["dataset_code"] == code
    assert all(path.exists() for path in source_fixtures(case))
    row = register_row(code)
    assert OBSERVATION_CASES[code] in row[2] and all(str(path.relative_to(REPO_ROOT)) in row[1] for path in source_fixtures(case))


@pytest.mark.parametrize("code", sorted(INDICATOR_CASES))
def test_indicator_evidence_is_committed_and_registered(code):
    case = load_cases(INDICATOR_CASES[code])
    assert all(path.exists() for path in source_fixtures(case))
    row = register_row(code)
    assert INDICATOR_CASES[code] in row[1]
    assert row[3] == ("yes" if registry.get(code).imputes else "no")
    documented = sorted(i for i in entries() if i.rsplit("-", 1)[0] == code)
    listed = [] if row[4] == "none known" else [c.strip() for c in row[4].split(",")]
    assert listed == documented, f"{code}: register lists {listed}, methodology-conflicts.md documents {documented}"


def test_conflict_entries_are_well_formed():
    found = entries()
    assert found, "no entries parsed from docs/methodology-conflicts.md"
    for identifier, text in found.items():
        status = re.findall(r"^Status: (.+)$", text, re.MULTILINE)
        assert len(status) == 1 and status[0] in STATUSES, f"{identifier}: Status must be one of {sorted(STATUSES)}, got {status}"
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{identifier}: missing section {section!r}"
        index = re.search(rf"^\| {re.escape(identifier)} \| .+ \| (\w+) \|$", CONFLICTS, re.MULTILINE)
        assert index and index.group(1) == status[0], f"{identifier}: index table row missing or its status differs from the entry"


def test_conflict_entries_cite_files_that_exist():
    cited = set(re.findall(r"`((?:src|tests|docs|scripts)/[^`\s(]+)`", CONFLICTS))
    assert cited and not [p for p in cited if not (REPO_ROOT / p).exists()]


def test_nothing_is_marked_resolved_without_cited_evidence():
    for identifier, text in entries().items():
        if "Status: resolved" in text:
            assert "Resolution evidence:" in text, f"{identifier}: resolved entries must carry a 'Resolution evidence:' section"
