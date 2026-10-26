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
    assert list(found) == ["GOV-1", "GOV-2", "GOV-3", "GOV-4", "GOV-5", "GOV-6"]
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


def test_gov_3_escalates_the_un_terms_and_records_the_pinned_release():
    text = entries()["GOV-3"]
    assert "escalates a confirmed restriction" in text and "personal, non-commercial use, without any right to\n  resell or redistribute them or to compile or create derivative works" in text
    assert "27f6a3bbc89769a9acef0675335b9ca4dca7ec3776db9499127256d39b7e14e6" in text and "Status: open" in text
    assert "Is the SSPI's use permitted?" in text and "May PRISON scores, or `UNODC_PRIPOP` values, be published?" in text


def test_gov_4_records_the_itu_licence_and_the_transcription():
    text = entries()["GOV-4"]
    assert "CC BY-NC-SA 3.0 IGO" in text and "f438b04d231799d6957ac81d02ad9db65dcc75a34b77bfc15654f52e5ae739b9" in text and "Status: open" in text
    assert "Is the transcription an adaptation" in text


def test_gov_5_records_that_no_fsi_terms_were_found():
    text = entries()["GOV-5"]
    assert "Status: open" in text and "HTTP 404" in text and "fsi_real_data" in text
    assert "May SECAPP scores, or `FSI_SECAPP` values, be published?" in text


def test_gov_6_records_the_vdem_licence_question_and_the_pinned_archive():
    text = entries()["GOV-6"]
    assert "Status: open" in text and "CC BY-SA 4.0" in text and "V-Dem-CY-FullOthers_csv_v13.zip" in text and "vdem_real_data" in text
    assert "Are RULELW and EDEMOC scores adaptations under ShareAlike?" in text and "none of them states a licence" in text
