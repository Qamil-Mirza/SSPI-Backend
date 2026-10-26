"""Write the synthetic UNODC workbook in this directory:

    data_cts_prisons_and_prisoners_synthetic.xlsx   (UNODC_PRIPOP, and through it PRISON)

Entirely invented, not UNODC data: only the layout of the UNODC data portal
workbook "Prisons and prisoners" is reproduced (two sheets; on the first,
two title rows above the header ``Iso3_code`` ... ``Source``; one row per
value; years as numbers and as text; integer and decimal values; the United
Kingdom's three jurisdictions and Iraq's two reporting units as separate
codes). Every value comes from the simple formulas below. The title row,
the second sheet and the workbook properties say it is synthetic.

The original workbook is not distributed with the repository while its
terms of use are open (docs/data-governance-review.md, GOV-3); see
README.md.

``build(variant)`` also writes invalid variants, never committed: the golden
generator and the adapter tests build them in memory to record what the
legacy cleaner and the new adapter do with them (see :data:`VARIANTS`).

Run from the repository root; the output is byte-for-byte deterministic
for a given Python and zlib (fixed workbook properties, fixed zip entry
times); ``cells`` compares content across environments:

    .venv/bin/python tests/fixtures/unodc/build_synthetic.py

tests/golden/test_golden_prison.py checks that the committed file is exactly
what this script writes.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
FILE_NAME = "data_cts_prisons_and_prisoners_synthetic.xlsx"
NOTE = "SYNTHETIC TEST WORKBOOK - invented for SSPI parity tests; not UNODC data"
HEADER = ("Iso3_code", "Country", "Region", "Subregion", "Indicator", "Dimension", "Category", "Sex", "Age", "Year", "Unit of measurement", "VALUE", "Source")
RATE = "Rate per 100,000 population"
TOTAL = ("Persons held", "Total", "Total", "Total", "Total")  # Indicator, Dimension, Category, Sex, Age: the kept series
VARIANTS = {
    "duplicate_row": "a second total rate for Malaysia in 2015",
    "national_gbr_row": "a national GBR rate in 2010, a year the three jurisdictions also report",
    "lowercase_code": "a total rate under the code 'qmf'",
    "code_with_digit": "a total rate under the code 'QM1'",
    "text_value": "a total rate written as text, '<5'",
}
FIXED_TIME = datetime(2000, 1, 1)


def series(start: float, step: float, first: int, last: int, skip=()) -> dict[int, float]:
    return {y: round(start + step * (y - first), 3) for y in range(first, last + 1) if y not in skip}


# code, name, region, subregion, {year: total rate}; None is an empty VALUE cell
AREAS: tuple[tuple[str, str, str, str, dict[int, float | int | None]], ...] = (
    ("MYS", "Malaysia", "Asia", "South-eastern Asia", {**series(150.0, 2.5, 2003, 2022, skip=(2010, 2011)), 2015: 171.123456789012345}),  # a gap, a full-precision value
    ("AUT", "Austria", "Europe", "Western Europe", {**series(105.0, -0.75, 2000, 2024), 2012: 98}),  # observed 2024 beyond the window, an integer cell
    ("USA", "United States of America", "Americas", "Northern America", {**series(700.0, -8.0, 2000, 2021), 2003: 540}),  # above the lower goalpost; exactly 540 in 2003
    ("GBR_E_W", "United Kingdom (England and Wales)", "Europe", "Northern Europe", series(140.0, 0.5, 2005, 2022)),
    ("GBR_S", "United Kingdom (Scotland)", "Europe", "Northern Europe", series(130.0, 1.0, 2005, 2021)),  # stops a year before England and Wales
    ("GBR_NI", "United Kingdom (Northern Ireland)", "Europe", "Northern Europe", series(80.0, 0.25, 2005, 2020)),  # stops two years before
    ("IRQ_C", "Iraq (Central Iraq)", "Asia", "Western Asia", series(120.0, 3.0, 2008, 2016)),  # not combined: skipped
    ("IRQ_KRI", "Iraq (Kurdistan Region of Iraq)", "Asia", "Western Asia", series(90.0, 1.0, 2008, 2016)),
    ("QMA", "Synthetic economy A", "Africa", "Synthetic subregion", {2015: 260.5}),  # one year, carried both ways
    ("QMB", "Synthetic economy B", "Oceania", "Synthetic subregion", {2010: 0, 2011: 0.0, 2012: 12.5}),  # reported zeros are kept
    ("QMC", "Synthetic economy C", "Americas", "Synthetic subregion", {**series(35.0, 0.5, 2000, 2023, skip=range(2006, 2011)), 2023: 40}),  # below and at the upper goalpost, a five-year gap
    ("QMD", "Synthetic economy D", "Africa", "Synthetic subregion", series(480.0, 15.0, 2018, 2023)),  # starts late; 540 in 2022, 555 in 2023
    ("QME", "Synthetic economy E", "Asia", "Synthetic subregion", {2012: None, 2013: None}),  # empty values only
)
TEXT_YEARS = frozenset({2016, 2017})  # written as text cells, as in some UNODC releases


def rows(variant: str | None = None) -> list[tuple]:
    """The first sheet's data rows, in order."""
    out: list[tuple] = []

    def add(code, name, region, subregion, indicator, dimension, category, sex, age, year, unit, value, source="CTS"):
        out.append((code, name, region, subregion, indicator, dimension, category, sex, age, str(year) if year in TEXT_YEARS else year, unit, value, source))

    for code, name, region, subregion, values in AREAS:
        for year, value in values.items():
            add(code, name, region, subregion, *TOTAL, year, RATE, value, "CTS" if year % 2 else "WPB-ICPR/CTS/External")
            if value is not None:  # the rows the filters drop
                add(code, name, region, subregion, *TOTAL, year, "Counts", round(value * 300))
                add(code, name, region, subregion, "Persons held", "by status", "Sentenced", "Total", "Total", year, RATE, round(value * 0.7, 3))
                add(code, name, region, subregion, "Persons held", "Total", "Total", "Male", "Total", year, RATE, round(value * 1.9, 3))
                add(code, name, region, subregion, "Persons held", "Total", "Total", "Total", "Adult", year, RATE, round(value * 0.95, 3))
                add(code, name, region, subregion, "Persons entering prison", "Total", "Total", "Total", "Total", year, RATE, round(value * 1.4, 3))
    if variant == "duplicate_row":
        add("MYS", "Malaysia", "Asia", "South-eastern Asia", *TOTAL, 2015, RATE, 172.0)
    elif variant == "national_gbr_row":
        add("GBR", "United Kingdom", "Europe", "Northern Europe", *TOTAL, 2010, RATE, 150.0)
    elif variant == "lowercase_code":
        add("qmf", "Synthetic economy F", "Asia", "Synthetic subregion", *TOTAL, 2010, RATE, 200.0)
    elif variant == "code_with_digit":
        add("QM1", "Synthetic economy 1", "Asia", "Synthetic subregion", *TOTAL, 2010, RATE, 200.0)
    elif variant == "text_value":
        add("QMF", "Synthetic economy F", "Asia", "Synthetic subregion", *TOTAL, 2010, RATE, "<5")
    return out


def build(variant: str | None = None) -> bytes:
    """The workbook's bytes (``variant`` one of :data:`VARIANTS`, or ``None`` for the committed file)."""
    from openpyxl import Workbook

    assert variant is None or variant in VARIANTS, variant
    workbook = Workbook()
    data = workbook.active
    data.title = "data_cts_prisons_and_prisoners"
    data.append(("SYNTHETIC", NOTE))
    data.append(("01/01/2000",))
    data.append(HEADER)
    for row in rows(variant):
        data.append(row)
    estimates = workbook.create_sheet("data_cts_prisoners_regional_est")
    estimates.append(("SYNTHETIC", NOTE))
    estimates.append(("01/01/2000",))
    estimates.append(("geo", "year", "indicator", "series", "sex", "value", "obs_status", "source"))
    estimates.append(("Synthetic region", "2010", "Persons held in prison", "Number of persons held in prison", "Total", 1234.5, "Estimated value", NOTE))
    workbook.properties.creator = "SSPI test suite"
    workbook.properties.title = NOTE
    workbook.properties.created = FIXED_TIME
    workbook.properties.modified = FIXED_TIME
    raw = io.BytesIO()
    workbook.save(raw)
    # openpyxl stamps the zip entries and the modification property with the current time: rewrite both
    fixed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as source, zipfile.ZipFile(fixed, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                content = re.sub(rb"<dcterms:modified([^>]*)>[^<]*</dcterms:modified>", rb"<dcterms:modified\1>2000-01-01T00:00:00Z</dcterms:modified>", content)
            target.writestr(zipfile.ZipInfo(item.filename, date_time=FIXED_TIME.timetuple()[:6]), content, compress_type=zipfile.ZIP_DEFLATED)
    return fixed.getvalue()


def cells(content: bytes) -> dict[str, list[tuple]]:
    """Every sheet's cell values: equal for two workbooks with the same content, whatever zlib compressed them."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content), read_only=True)
    try:
        return {sheet.title: list(sheet.iter_rows(values_only=True)) for sheet in workbook.worksheets}
    finally:
        workbook.close()


def main() -> None:
    (HERE / FILE_NAME).write_bytes(build())


if __name__ == "__main__":
    main()
