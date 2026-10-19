"""docs/data-governance-review.md: data-governance and licensing items are
recorded there, well formed, and cross-referenced from the methodology review
document, never filed as methodology entries. No database, no network."""

import re
from pathlib import Path

DOCS = Path(__file__).parents[2] / "docs"
GOVERNANCE = (DOCS / "data-governance-review.md").read_text(encoding="utf-8")
CONFLICTS = (DOCS / "methodology-conflicts.md").read_text(encoding="utf-8")
ENTRY = re.compile(r"^## (GOV-\d+) — (.+)$", re.MULTILINE)
CLASSIFICATION = "DATA-GOVERNANCE / LICENSING REVIEW"


def entries() -> dict[str, str]:
    found = {}
    for match in ENTRY.finditer(GOVERNANCE):
        following = re.search(r"^## ", GOVERNANCE[match.end() :], re.MULTILINE)
        found[match.group(1)] = GOVERNANCE[match.start() : match.end() + following.start() if following else len(GOVERNANCE)]
    return found


def test_entries_are_well_formed_and_indexed():
    found = entries()
    assert list(found) == ["GOV-1", "GOV-2"]
    for identifier, text in found.items():
        (status,) = re.findall(r"^Status: (.+)$", text, re.MULTILINE)
        assert status in {"open", "closed"}
        assert f"Classification: {CLASSIFICATION} (not a scoring-methodology decision)" in text
        assert "Resolution evidence:" in text and (status == "closed") is ("Resolution evidence: none yet." not in text)
        assert re.search(rf"^\| {identifier} \| .+ \| {re.escape(CLASSIFICATION)} \| {status} \|$", GOVERNANCE, re.MULTILINE), identifier


def test_every_item_is_cross_referenced_from_the_methodology_review_and_is_not_a_methodology_entry():
    section = CONFLICTS.split("## Reviewed alongside this file: data-governance items", 1)[1].split("\n## ", 1)[0]
    assert CLASSIFICATION in section and re.search(r"not\s+methodology decisions", section)
    for identifier, text in entries().items():
        (status,) = re.findall(r"^Status: (.+)$", text, re.MULTILINE)
        assert re.search(rf"^\| {identifier} \| .+ \| \[`data-governance-review.md`\]\(data-governance-review.md#{identifier.lower()}-.+\) \| {status} \|$", section, re.MULTILINE), identifier
        assert not re.search(rf"^## {identifier} ", CONFLICTS, re.MULTILINE)


def test_gov_1_records_the_five_questions_and_the_owner_decision():
    text = entries()["GOV-1"]
    for question in (
        "Which terms govern the GHO API?",
        "Can WHO source extracts be redistributed in the SSPI repository?",
        "Do ATBRTH's third-party source credits impose additional\n   conditions?",
        "Does DPTCOV require separate UNICEF permission?",
        "What attribution is required?",
    ):
        assert question in text, question
    assert "DECISION: project owner, 2026-10-19" in text and "No synthetic data in\n>   production ingestion or scoring." in text
    assert "### Legal permission is not attribution" in text


def test_gov_2_records_the_seven_questions_the_owner_decision_and_the_licence_evidence():
    text = entries()["GOV-2"]
    for question in (
        "Which terms govern the World Bank-hosted workbook?",
        "Is SSPI's use non-commercial?",
        "May extracts be published as test fixtures?",
        "May the database be redistributed?",
        "Are AQELEC scores adapted material that may not be shared?",
        "What attribution is required?",
        "Should permission be requested?",
    ):
        assert question in text, question
    assert "DECISION: project owner, 2026-10-19" in text and "Do not infer permission to distribute original WEF data." in text
    assert "Attribution-NonCommercial-NoDerivatives 4.0" in text and "a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451" in text
    assert "Status: open" in text
