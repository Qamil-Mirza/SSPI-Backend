# Fragile States Index workbook fixtures

**`fsi-2018_synthetic.xlsx`, `fsi-2021_synthetic.xlsx` and
`fsi-2023_synthetic.xlsx` are synthetic. Their scores are invented, not the
Fund for Peace's.**

Production ingestion of `FSI_SECAPP` reads the 18 original annual workbooks
(2006–2023) linked from `https://fragilestatesindex.org/excel/`, each pinned
by URL and SHA-256 (`sspi.ingestion.fsi`), and scores SECAPP from component
C1, Security Apparatus. No licence or terms of use for the FSI data have
been found, so the originals are not distributed with the repository; see
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-5.

## Synthetic workbooks (committed)

- **Written by a script**, `build_synthetic.py`, deterministically (fixed
  workbook properties and zip entry times);
  `tests/golden/test_golden_secapp.py` checks that the committed files are
  exactly its output.
- **The three FSI layouts**: 2018 (a sheet named after the year, `Year` as a
  1 January date, the indicators in C-E-P-S-X order, a "Change from Previous
  Year" column), 2021 (`Year` as an integer) and 2023 (sheet `Sheet1`, the S
  indicators first). Every row has `Country`, `Year`, `Rank`, `Total` and
  twelve indicators; only `C1: Security Apparatus` is read.
- **Real country names, invented scores.** The names exercise every rule of
  the country matching: the legacy matcher's rules ("Israel and West Bank",
  "Congo Democratic Republic", "Congo Republic", "Guinea Bissau", "Kosovo"),
  pycountry names ("Kyrgyz Republic", "Côte d'Ivoire", "North Macedonia"),
  names padded with spaces ("Sri Lanka ", "Serbia  ") and the five spellings
  the approved repair maps ("Cote d'Ivoire", "Macedonia", "Micronesia",
  "Palestine", "North Korea", which the legacy matcher sends to KOR beside
  "South Korea"). Values include 10.0, 0.3 and a full-precision
  9.932962647670891; Palestine is listed from 2021 only.
- **Invalid variants**, built in memory, never committed: a name nothing
  codes, a repeated country, an empty C1 cell, and a `Year` that is not the
  edition's. The adapter refuses each; legacy refused the first three and
  would have stored the last under its stated year.

`tests/golden/generate_public_safety_cases.py secapp` ran, at the pinned
commit, the registered cleaner on these workbooks as the March 2025
collector stored them (its failure), the same cleaner with only the
approved repair, and `compute_secapp`; the new backend reproduces that
output exactly (`tests/golden/test_golden_secapp.py`).

## Original workbooks (kept outside the repository)

By convention they live in `local-data/fsi/`, which `.gitignore` excludes:
the 18 workbooks as served on 2026-10-25 (file names as on the site) and
`golden/fsi_secapp_cases.json`, `golden/secapp_cases.json`, the pinned legacy
code's output on them (`generate_public_safety_cases.py --real local-data
secapp`). `REAL_DATA.sha256` in this directory pins every one of those files
and contains no FSI data. To run the opt-in tier:

```
SSPI_FSI_REAL_DATA=local-data/fsi .venv/bin/python -m pytest -m fsi_real_data
```
