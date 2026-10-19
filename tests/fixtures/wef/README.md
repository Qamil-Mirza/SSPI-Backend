# WEF workbook test fixtures

**`WEF-GCIHH_synthetic.xlsx` is synthetic. It is not WEF data.**

Production ingestion of `WEF_QUELEC` reads the original World Economic
Forum Global Competitiveness Index Historical Dataset workbook
(`sspi.ingestion.wef`, pinned by SHA-256) and scores AQELEC from it.
Synthetic data is used only as test input.

The original workbook is not distributed with the repository while its
licence terms are open. The WEF terms and the workbook's own legal text both
say CC BY-NC-ND 4.0. That is a data-governance item, not a methodology
question: see
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-2.

## Synthetic workbook (committed)

- **Written by a script.** `build_synthetic.py` writes it deterministically
  (`.venv/bin/python tests/fixtures/wef/build_synthetic.py`): fixed workbook
  properties and fixed zip entry times. `tests/golden/test_golden_wef.py`
  checks that the committed file is exactly its output.
- **Only the layout is copied.** It reproduces:
  - the sheet names `Data`, `Indicator Metadata` and `Dataset Metadata`,
    in that order;
  - the `Data` header (`Economy ISO3`, `Economy Name`, `Indicator ID`,
    `Indicator`, `Attribute 1`-`3`, `Partner`, `2007`-`2017` as text);
  - `Value` and `Rank` rows, and `-` placeholders;
  - integer and decimal cells, and blank cells.

  Every value is invented by simple formulas.
- **Labelled.** The metadata sheets and the workbook title say "SYNTHETIC
  TEST WORKBOOK - invented for SSPI parity tests; not WEF data".
- **What it covers:**
  - Malaysia, Austria and the United States (the researcher guide's query);
  - Chad (a value of exactly 1, ending in 2012);
  - `QMA` (an ISO 3166 user-assigned code, so no World Bank access data);
  - `QRA` (an aggregate-like code, kept as the legacy cleaner kept it);
  - `QMB` (every year blank);
  - a gap, a full-precision value, integer cells (4 and 7), late starts;
  - the rank rows and a second indicator (`WEF.GCIHH.EOSQ065`) that the
    filters drop.
- **Invalid variants.** `build(variant)` writes four invalid variants that
  are never committed: a repeated row, a lowercase code, a code with a digit
  and a text value. The legacy clean collection refused each of them, and so
  does the new adapter.

`tests/golden/generate_wef_cases.py` ran the pinned legacy collector,
cleaners and `compute_aqelec` on this workbook and on
`tests/fixtures/wb/EG.ELC.ACCS.ZS_sample.json`. The new backend reproduces
that output exactly (`tests/golden/test_golden_wef.py`). The migration gate
is unchanged: a committed fixture, golden files from the pinned commit,
exact parity and a register row.

## Original workbook (kept outside the repository)

By convention it lives in `local-data/wef/`, which `.gitignore` excludes:

| Path | Content |
|---|---|
| `WEF-GCIHH.xlsx` | the original workbook as served on 2026-10-19 from `https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx` (3,476,362 bytes, Last-Modified 2024-02-16; dataset last updated 2023-07-17; 2007-2017, 152 economies) |
| `responses/EG.ELC.ACCS.ZS.json` | the full World Bank response for access to electricity, 2026-10-19 (17,556 rows) |
| `golden/wef_quelec_cases.json`, `golden/wb_avelec_cases.json`, `golden/aqelec_cases.json` | the pinned legacy code's output on them (`generate_wef_cases.py --real local-data/wef`) |

`REAL_DATA.sha256` in this directory is committed. It pins every one of
those files and contains no WEF data. To run the opt-in tier:

```
SSPI_WEF_REAL_DATA=local-data/wef .venv/bin/python -m pytest -m wef_real_data
```

Every file is checked against the manifest before use. A missing or
changed file fails the test; it does not skip.
`tests/golden/test_golden_wef.py` also fails if any of these files appears
under `tests/`. To verify by hand:
`(cd local-data/wef && shasum -a 256 -c ../../tests/fixtures/wef/REAL_DATA.sha256)`.

## Source, owner and attribution

The data is the World Economic Forum's: Executive Opinion Survey answers
published in *The Global Competitiveness Report* and collected in the
WEF Global Competitiveness Index Historical Dataset. The World Bank hosts
the workbook. Which terms govern its use, sharing and derived scores, and
what attribution is required, are open in GOV-2.
