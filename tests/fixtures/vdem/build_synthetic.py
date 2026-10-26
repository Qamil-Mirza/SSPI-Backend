"""Write the synthetic V-Dem archive in this directory:

    V-Dem-CY-FullOthers_csv_v13_synthetic.zip   (VDEM_RULELW and VDEM_EDEMOC, and through them RULELW and EDEMOC)

Entirely invented, not V-Dem data: only the layout of the V-Dem
Country-Year Full+Others CSV archive is reproduced (a ZIP holding one CSV
and other, non-CSV members; the identifying columns ``country_name``,
``country_text_id``, ``country_id``, ``year``, ``historical_date``,
``project``; the point estimates ``v2x_polyarchy`` and ``v2x_rule`` with
their ``*_codelow``, ``*_codehigh`` and ``*_sd`` companions; empty cells for
missing values). Every value is made up. Country names and V-Dem's own
country identifiers are real, because what the cleaner does with them is
part of what is tested; the values attached to them mean nothing. Every
row's ``project`` cell says so.

The original archive is not distributed with the repository
(docs/data-governance-review.md, GOV-6); see README.md.

``build(variant)`` also writes invalid variants, never committed (see
:data:`VARIANTS`): the golden generator and the adapter tests build them in
memory to record what the legacy collector, cleaner and clean collection,
and the new adapter, do with them.

Run from the repository root:

    .venv/bin/python tests/fixtures/vdem/build_synthetic.py

tests/golden/test_golden_rulelw.py checks that the committed file is exactly
what this script writes.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
FILE_NAME = "V-Dem-CY-FullOthers_csv_v13_synthetic.zip"
MEMBER = "V-Dem-CY-Full+Others-v13_synthetic.csv"
OTHER_MEMBERS = {"codebook_synthetic.txt": "SYNTHETIC archive for the SSPI backend tests: no V-Dem codebook.\n"}
NOTE = "SYNTHETIC: invented values, not V-Dem data"
DATE_TIME = (2023, 2, 22, 8, 8, 0)  # the date of the original CSV member, fixed so the archive is reproducible
HEADER = (
    "country_name", "country_text_id", "country_id", "year", "historical_date", "project",
    "v2x_polyarchy", "v2x_polyarchy_codelow", "v2x_polyarchy_codehigh", "v2x_polyarchy_sd",
    "v2x_libdem", "v2x_rule", "v2x_rule_codelow", "v2x_rule_codehigh", "v2x_rule_sd",
)
VARIANTS = {
    "duplicate_row": "a second United States 2010 row with other values",
    "lowercase_code": "Austria coded \"aut\" instead of \"AUT\"",
    "text_value": "a v2x_rule and a v2x_polyarchy cell holding the text \"unknown\"",
    "missing_column": "no v2x_rule and no v2x_polyarchy column",
    "not_utf8": "the CSV encoded in Latin-1, with a name outside ASCII",
}


def _series(first, last, start, step, *, missing=()):
    """Invented values, three decimals, ``None`` (an empty cell) for the years in ``missing``."""
    return {year: (None if year in missing else round(start + step * (year - first), 3)) for year in range(first, last + 1)}


# (country_name, country_text_id, country_id, {year: v2x_rule}, {year: v2x_polyarchy})
COUNTRIES = (
    # every year 1989-2026: 1989 and 1990 are before the window, 2026 is the year of the golden run (excluded),
    # 2023-2025 are later than V-Dem v13 reaches (the cleaner's bound is the clock, not the edition)
    ("United States of America", "USA", 20, _series(1989, 2026, 0.95, -0.001), _series(1989, 2026, 0.85, -0.001)),
    # ends in 2015: carried forward eight years; exactly 1 and exactly 0 (both goalposts)
    ("Austria", "AUT", 144, {**_series(1990, 2015, 0.9, 0.002), 1999: 1.0, 2000: 0}, {**_series(1990, 2015, 0.8, 0.003), 2001: 1}),
    # starts in 1995, ends in 2022 (one year carried); an empty v2x_rule run 2000-2002 that is not filled
    ("Malaysia", "MYS", 177, _series(1995, 2022, 0.4, 0.008, missing=(2000, 2001, 2002)), _series(1995, 2022, 0.25, 0.006)),
    # V-Dem's own identifiers, not ISO 3166-1, kept as published
    ("Kosovo", "XKX", 43, _series(2008, 2022, 0.5, 0.004), _series(2008, 2022, 0.55, 0.003)),
    ("Palestine/Gaza", "PSG", 138, _series(2007, 2010, 0.2, 0.01), _series(2007, 2010, 0.1, 0.0)),
    # beyond the goalposts (V-Dem never publishes this; the score clamps)
    ("Norway", "NOR", 186, {2010: 1.2, 2011: 0.995}, {2010: 1.05, 2011: -0.01}),
    ("Afghanistan", "AFG", 36, {2001: -0.05, 2002: 0.1}, {2001: 0.0, 2002: 0.12}),
    # more than ten decimals: to_json writes ten, the cleaner read those
    ("Vietnam", "VNM", 34, {2015: 0.123456789012345, 2016: 0.987654321098765}, {2015: 0.333333333333333, 2016: 0.1}),
    # every value empty: no observation, nothing carried
    ("Zanzibar", "ZZB", 236, _series(1991, 2022, 0, 0, missing=range(1991, 2023)), _series(1991, 2022, 0, 0, missing=range(1991, 2023))),
    # before the window only: nothing read, nothing counted missing
    ("German Democratic Republic", "DDR", 137, _series(1985, 1990, 0.1, 0.01), _series(1985, 1990, 0.05, 0.01)),
    # only after 2023: observed, nothing carried
    ("South Sudan", "SSD", 32, {2024: 0.15, 2025: 0.16}, {2024: 0.2, 2025: None}),
    # 1990 and 1991: the year the window starts
    ("Ghana", "GHA", 7, {1990: 0.3, 1991: 0.31}, {1990: 0.2, 1991: 0.21}),
)


def _cell(value):
    return "" if value is None else repr(value) if isinstance(value, float) else str(value)


def rows(variant=None):
    """The CSV rows, header first, in the archive's country-then-year order."""
    out = [list(HEADER)]
    for name, code, country_id, rule, polyarchy in COUNTRIES:
        if variant == "lowercase_code" and code == "AUT":
            code = "aut"
        for year in sorted(set(rule) | set(polyarchy)):
            r, p = rule.get(year), polyarchy.get(year)
            low = lambda v: None if v is None else round(v - 0.05, 3)  # noqa: E731 - bounds that differ from the estimate
            high = lambda v: None if v is None else round(v + 0.05, 3)  # noqa: E731
            out.append([name, code, str(country_id), str(year), f"{year}-12-31", NOTE, _cell(p), _cell(low(p)), _cell(high(p)), "0.04", "0.5", _cell(r), _cell(low(r)), _cell(high(r)), "0.03"])
            if variant == "duplicate_row" and code == "USA" and year == 2010:
                out.append([name, code, str(country_id), str(year), f"{year}-12-31", NOTE, "0.5", "", "", "", "", "0.5", "", "", ""])
    if variant == "text_value":
        out[1][HEADER.index("v2x_rule")] = "unknown"
        out[1][HEADER.index("v2x_polyarchy")] = "unknown"
    if variant == "missing_column":
        keep = [i for i, column in enumerate(HEADER) if column not in ("v2x_rule", "v2x_polyarchy")]
        out = [[row[i] for i in keep] for row in out]
    if variant == "not_utf8":
        out.append(["Côte d'Ivoire", "CIV", 64, "2010", "2010-12-31", NOTE, "0.4", "", "", "", "", "0.4", "", "", ""])
    return out


def csv_text(variant=None):
    buffer = io.StringIO()
    for row in rows(variant):
        buffer.write(",".join(f'"{c}"' if "," in str(c) or "/" in str(c) else str(c) for c in row) + "\n")
    return buffer.getvalue()


def build(variant=None) -> bytes:
    """The archive's bytes: deterministic (fixed member dates, fixed order, DEFLATE)."""
    if variant is not None and variant not in VARIANTS:
        raise KeyError(variant)
    text = csv_text(variant)
    content = text.encode("latin-1" if variant == "not_utf8" else "utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in ((MEMBER, content), *((n, t.encode("utf-8")) for n, t in OTHER_MEMBERS.items())):
            info = zipfile.ZipInfo(name, DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buffer.getvalue()


def members(content: bytes) -> dict[str, bytes]:
    """Every member's bytes: what the committed archive is compared on in the legacy environment."""
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return {name: z.read(name) for name in z.namelist()}


if __name__ == "__main__":
    (HERE / FILE_NAME).write_bytes(build())
    print(f"wrote {HERE / FILE_NAME}")
