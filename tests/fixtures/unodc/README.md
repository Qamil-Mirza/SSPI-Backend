# UNODC workbook test fixtures

**`data_cts_prisons_and_prisoners_synthetic.xlsx` is synthetic. It is not
UNODC data.**

Production ingestion of `UNODC_PRIPOP` reads the original UNODC data portal
workbook "Prisons and prisoners" (`sspi.ingestion.unodc`, pinned by SHA-256)
and scores PRISON from it. Synthetic data is used only as test input.

The original workbook is not distributed with the repository: the portal
links to the United Nations copyright notice, and the UN website terms grant
only personal, non-commercial use without redistribution or derivative
works. That is a data-governance item, not a methodology question: see
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-3.

## Synthetic workbook (committed)

- **Written by a script.** `build_synthetic.py` writes it deterministically
  (`.venv/bin/python tests/fixtures/unodc/build_synthetic.py`): fixed
  workbook properties and fixed zip entry times.
  `tests/golden/test_golden_prison.py` checks that the committed file is
  exactly its output.
- **Only the layout is copied:** the two sheets
  (`data_cts_prisons_and_prisoners`, `data_cts_prisoners_regional_est`), two
  title rows above the header (`Iso3_code`, `Country`, `Region`,
  `Subregion`, `Indicator`, `Dimension`, `Category`, `Sex`, `Age`, `Year`,
  `Unit of measurement`, `VALUE`, `Source`), one row per value, years as
  numbers and as text, integer and decimal values, blank values. Every value
  is invented by simple formulas.
- **Labelled.** The title rows of both sheets and the workbook title say
  "SYNTHETIC TEST WORKBOOK - invented for SSPI parity tests; not UNODC
  data"; the areas other than Malaysia, Austria, the United States, the UK
  jurisdictions and Iraq's units use user-assigned codes (`QMA`-`QME`).
- **What it covers:** the series the cleaner keeps (persons held, total,
  rate per 100,000) and five kinds of row it drops (counts, by status, male,
  adults, persons entering); the UK jurisdictions with all three reporting
  in 2005-2020, two in 2021 and one in 2022 (PRISON-1); Iraq's two units
  (dropped, PRISON-4); one single year (`QMA`); reported zeros (`QMB`);
  values at and beyond both goalposts (the United States 700 and exactly
  540, `QMD` 540 and 555, `QMC` 35 and exactly 40); a two-year and a
  five-year gap; empty values only (`QME`); an observed 2024; no China (the
  reference-class recipient, PRISON-2).
- **Invalid variants.** `build(variant)` writes five invalid variants that
  are never committed: a repeated country-year, a national GBR row beside
  the jurisdictions, a lowercase code, a code with a digit and a text value.
  Legacy stored nothing for each, and the new adapter refuses each.

`tests/golden/generate_public_safety_cases.py prison` ran the pinned legacy
collector, cleaner, `compute_prison` and `impute_prison` on this workbook.
The new backend reproduces that output exactly
(`tests/golden/test_golden_prison.py`).

## Original workbook (kept outside the repository)

By convention it lives in `local-data/unodc/`, which `.gitignore` excludes:

| Path | Content |
|---|---|
| `data_cts_prisons_and_prisoners_2026-09-30.xlsx` | the original workbook as served on 2026-10-25 from `https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_prisons_and_prisoners.xlsx` (5,943,584 bytes, Last-Modified 2026-09-30, release dated 30/09/2026) |
| `golden/unodc_pripop_cases.json`, `golden/prison_cases.json` | the pinned legacy code's output on it (`generate_public_safety_cases.py --real local-data`) |

`REAL_DATA.sha256` in this directory is committed. It pins every one of
those files and contains no UNODC data. To run the opt-in tier:

```
SSPI_UNODC_REAL_DATA=local-data/unodc .venv/bin/python -m pytest -m unodc_real_data
```

Every file is checked against the manifest before use; a missing or changed
file fails the test, it does not skip. `tests/golden/test_golden_prison.py`
also fails if any of these files appears under `tests/`.
