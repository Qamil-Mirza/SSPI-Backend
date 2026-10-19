"""Write the synthetic GHO fixtures in this directory:

    MDG_0000000025_synthetic.json   (WHO_ATBRTH)
    WHS4_100_synthetic.json         (WHO_DPTCOV)
    HWF_0001_synthetic.json         (WHO_PHYSPC)

Entirely invented, not WHO data: only the GHO OData row layout is
reproduced; every value comes from the simple formulas below, every row's
``Comments`` says it is synthetic, the change date is a fixed placeholder and
the OData context points at ``example.invalid``. Country codes are MYS, AUT
and USA (the researcher guide's query) and ISO 3166 user-assigned codes
(QMA-QMF, and QRA, QWB, QUN for aggregates) for edge cases.

Real WHO data is not distributed with the repository while redistribution
rights are open (docs/data-governance-review.md, GOV-1); see README.md.

Run from the repository root; the output is deterministic:

    .venv/bin/python tests/fixtures/who/build_synthetic.py

tests/golden/test_golden_who.py checks that the committed files are exactly
what this script writes.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
NOTE = "SYNTHETIC TEST ROW - invented for SSPI parity tests; not WHO data"
PLACEHOLDER_DATE = "2000-01-01T00:00:00+00:00"


def build() -> dict[str, str]:
    """File name -> file text."""
    ids = iter(range(1, 10_000))

    def row(code, country, year, value, *, kind="COUNTRY", display=None):
        return {
            "Id": next(ids), "IndicatorCode": code, "SpatialDimType": kind, "SpatialDim": country, "ParentLocationCode": None,
            "TimeDimType": "YEAR", "ParentLocation": None, "Dim1Type": None, "Dim1": None, "TimeDim": year,
            "Dim2Type": None, "Dim2": None, "Dim3Type": None, "Dim3": None, "DataSourceDimType": None, "DataSourceDim": None,
            "Value": "No data" if value is None else (display if display is not None else f"{value:g}"),
            "NumericValue": None if value is None else float(value), "Low": None, "High": None, "Comments": NOTE,
            "Date": PLACEHOLDER_DATE, "TimeDimensionValue": str(year),
            "TimeDimensionBegin": f"{year}-01-01T00:00:00+00:00", "TimeDimensionEnd": f"{year}-12-31T00:00:00+00:00",
        }

    def series(code, country, years, start, step):
        return [row(code, country, y, round(start + step * i, 1)) for i, y in enumerate(years)]

    def aggregates(code, years):
        out = []
        for y in years:
            out += [row(code, "GLOBAL", y, 50 + y % 7, kind="GLOBAL"), row(code, "QRA", y, 40 + y % 5, kind="REGION"),
                    row(code, "QWB", y, 60 + y % 3, kind="WORLDBANKINCOMEGROUP"), row(code, "QUN", y, 30, kind="UNREGION")]
        return out

    # ATBRTH: goalposts 80 -> 100; series fill 2000-2023; five hard-coded recipients, none of them in the data
    c = "MDG_0000000025"
    atbrth = (
        series(c, "MYS", [2001, 2004, 2008, 2012, 2016, 2020], 90.0, 1.5)  # interior gaps, carried back to 2000 and forward from 2020
        + series(c, "AUT", [*range(2000, 2023), 2024], 97.0, 0.1)  # 2023 missing between 2022 and 2024: interpolated; 2024 past the fill target
        + series(c, "USA", list(range(2005, 2023, 3)), 95.0, 0.4)
        + [row(c, "QMA", 2010, 80.0), row(c, "QMA", 2011, 79.9), row(c, "QMA", 2012, 100.0)]  # at the lower goalpost, below it, at the upper
        + [row(c, "QMB", 2015, 0.0)]  # a reported zero, the only value: carried both ways
        + [row(c, "QMC", 2003, 85.0), row(c, "QMC", 2006, None), row(c, "QMC", 2009, 88.0)]  # a "No data" row inside a gap
        + series(c, "QMD", [2000, 2001, 2002], 82.0, 3.0)  # early end: carried 21 years
        + [row(c, "QME", 2021, 96.7, display="97")]  # late start; display value rounded
        + [row(c, "QMF", 2018, None)]  # a country with only "No data"
        + aggregates(c, [2000, 2010, 2020])
    )
    # DPTCOV: goalposts 75 -> 100; no impute route
    c = "WHS4_100"
    dptcov = (
        series(c, "MYS", list(range(2000, 2026)), 90.0, 0.2)
        + series(c, "AUT", list(range(2000, 2026)), 80.0, 0.3)
        + series(c, "USA", list(range(2000, 2026)), 92.0, 0.1)
        + [row(c, "QMA", 2010, 75.0), row(c, "QMA", 2011, 99.0), row(c, "QMA", 2012, 100.0), row(c, "QMA", 2013, 0.0), row(c, "QMA", 2014, 74.9)]
        + series(c, "QMB", [2012, 2014, 2019], 60.0, 7.5)  # late start with gaps: nothing imputed
        + [row(c, "QMC", 2016, None), row(c, "QMC", 2017, 88.8, display="89")]
        + aggregates(c, [2000, 2025])
    )
    # PHYSPC: goalposts 0 -> 70; series fill 2000-2023, interpolation in any year
    c = "HWF_0001"
    physpc = (
        series(c, "MYS", [1990, 1995, 2005, 2010, 2015, 2024], 4.0, 4.0)  # a gap that spans 2000
        + series(c, "AUT", list(range(1990, 2025)), 30.0, 0.8)
        + series(c, "USA", list(range(1993, 2023)), 20.0, 0.25)  # ends 2022: carried to 2023
        + [row(c, "QMA", 2011, 72.0), row(c, "QMA", 2012, 70.0), row(c, "QMA", 2013, 140.0)]  # above, at the upper goalpost, an outlier
        + [row(c, "QMB", 1992, 10.0), row(c, "QMB", 2011, 13.8)]  # an 18-year gap mostly before 2000
        + [row(c, "QMC", 2008, 0.0), row(c, "QMC", 2009, 0.13)]  # a zero and a tiny value
        + [row(c, "QMD", 2018, 24.1)]  # late start: carried back 18 years
        + series(c, "QME", [1995, 2004, 2015], 15.0, -2.0)  # early end
        + [row(c, "QMF", 2020, None)]
        + aggregates(c, [2000, 2024])
    )
    files = {}
    for code, rows in (("MDG_0000000025", atbrth), ("WHS4_100", dptcov), ("HWF_0001", physpc)):
        lines = ",\n".join(json.dumps(r) for r in rows)
        files[f"{code}_synthetic.json"] = f'{{"@odata.context": "https://example.invalid/api/$metadata#{code}", "value": [\n{lines}\n]}}\n'
    return files


def main() -> None:
    for name, text in build().items():
        (HERE / name).write_text(text, encoding="utf-8")
        print(name, len(json.loads(text)["value"]), "rows")


if __name__ == "__main__":
    main()
