"""Write the synthetic GCI transcription in this directory:

    gci-local-indicator-summary_synthetic.csv   (ITU_CYBSEC, and through it CYBSEC)

Entirely invented, not ITU data: only the layout of the legacy SSPI's hand
transcription of the ITU Global Cybersecurity Index is reproduced (a
``Country`` column, then a score and a rank column per edition, headed
``2014``, ``Globa Rank``, ``2017``, ``Global Rank``, ... with a trailing
empty column; 2014-2018 scores on 0-1 and 2020-2024 scores on 0-100; blank
cells; country names in the forms the transcription uses). Every score is
made up. The country names are real, because the legacy name matcher is
part of what is tested; the scores attached to them mean nothing.

The original transcription is not distributed with the repository while
its licence terms are open (docs/data-governance-review.md, GOV-4); see
README.md.

``build(variant)`` also writes invalid variants, never committed (see
:data:`VARIANTS`): the golden generator and the adapter tests build them in
memory to record what the legacy cleaner and the new adapter do with them.

Run from the repository root:

    .venv/bin/python tests/fixtures/itu/build_synthetic.py

tests/golden/test_golden_cybsec.py checks that the committed file is exactly
what this script writes.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent
FILE_NAME = "gci-local-indicator-summary_synthetic.csv"
HEADER = "Country,2014,Globa Rank,2017,Global Rank,2018,Global Rank,2020,Global Rank,2024,Global Rank,"
VARIANTS = {
    "original_unmatched_names": "rows for the five spellings of the original transcription the legacy matcher leaves unchanged (corrected by the approved table, CYBSEC-1)",
    "unapproved_name": "a row for \"Bolivia (Plurinational State of)\", a name neither the legacy matcher nor the approved table codes",
    "duplicate_country": "a row for \"United States of America\" beside \"United States\": both are USA",
}

# Country, then (score, rank) for 2014, 2017, 2018, 2020, 2024; "" is a blank cell
ROWS: tuple[tuple[str, tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]], ...] = (
    ("United States", ("0.5", "1"), ("0.61", "2"), ("0.712", "3"), ("88.5", "4"), ("97.47", "5")),  # 97.47 / 100 is stored as 0.9747
    ("Austria", ("0.25", "9"), ("0.333", "8"), ("0.444", "7"), ("55.55", "6"), ("66.66", "5")),
    ("Malaysia", ("0.4", "3"), ("", ""), ("0.6", "2"), ("99.86", "1"), ("100", "1")),  # a blank edition; 100 becomes 1.0
    ("Korea (the Republic of)", ("0.45", "2"), ("0.5", "4"), ("0.55", "5"), ("60", "5"), ("70", "4")),  # legacy rule: KOR
    ("Russian Federation", ("0.3", "6"), ("0.35", "7"), ("0.4", "8"), ("45", "9"), ("50", "8")),  # legacy rule: RUS
    ("Türkiye", ("0.2", "10"), ("0.22", "11"), ("0.24", "12"), ("26", "12"), ("28", "13")),  # legacy rule ("kiye"): TUR
    ("Niger", ("0.05", "20"), ("0.06", "21"), ("0.07", "22"), ("8", "22"), ("9", "23")),  # legacy rule: NER
    ("Nigeria", ("0.15", "15"), ("0.16", "16"), ("0.17", "17"), ("18", "17"), ("19", "18")),  # pycountry: NGA
    ("Democratic Republic of the Congo", ("0.01", "30"), ("0.02", "30"), ("0.03", "30"), ("4", "30"), ("5", "30")),  # legacy rule: COD
    ("Viet Nam", ("0.123", "12"), ("0.234", "12"), ("0.123456789012345", "13"), ("33.333333333333", "14"), ("44.4", "14")),  # pycountry: VNM; more than ten decimals
    ("Iceland", ("0", "40"), ("0", "40"), ("0", "40"), ("0", "40"), ("0", "40")),  # published zeros are kept
    ("Ethiopia", ("", ""), ("", ""), ("0.08", "25"), ("", ""), ("12.5", "25")),  # two editions only
    ("Holy See", ("", ""), ("", ""), ("", ""), ("", ""), ("", "")),  # every cell blank
)
EXTRA_ROWS = {
    "original_unmatched_names": (
        ("Cote d'Ivoire", ("0.1", "18"), ("0.2", "18"), ("0.3", "18"), ("40", "18"), ("50", "18")),
        ("Macedonia", ("0.11", "17"), ("0.21", "17"), ("0.31", "17"), ("41.5", "17"), ("51.25", "17")),
        ("Micronesia", ("0.01", "29"), ("0.02", "29"), ("0.03", "29"), ("0", "29"), ("8.5", "29")),
        ("State of Palestine", ("0.12", "16"), ("0.22", "16"), ("0.32", "16"), ("25.5", "16"), ("37.75", "16")),
        ("Vatican", ("", ""), ("0.04", "31"), ("0.02", "31"), ("0", "31"), ("9.5", "31")),
    ),
    "unapproved_name": (("Bolivia (Plurinational State of)", ("0.2", "14"), ("0.3", "14"), ("0.4", "14"), ("50", "14"), ("60", "14")),),
    "duplicate_country": (("United States of America", ("0.5", "1"), ("0.6", "2"), ("0.7", "3"), ("80", "4"), ("90", "5")),),
}


def build(variant: str | None = None) -> bytes:
    """The file's bytes (``variant`` one of :data:`VARIANTS`, or ``None`` for the committed file)."""
    assert variant is None or variant in VARIANTS, variant
    rows = ROWS + (EXTRA_ROWS[variant] if variant else ())
    lines = [HEADER] + [",".join([country, *(cell for pair in editions for cell in pair)]) + "," for country, *editions in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    (HERE / FILE_NAME).write_bytes(build())


if __name__ == "__main__":
    main()
