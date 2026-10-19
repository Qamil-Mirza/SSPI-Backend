# WHO Global Health Observatory test fixtures

**The JSON files in this directory are synthetic. They are not WHO data.**

Production ingestion of `WHO_ATBRTH`, `WHO_DPTCOV` and `WHO_PHYSPC` always
reads the real WHO GHO OData API (`sspi.ingestion.who`), stores what WHO
publishes in PostgreSQL, and scores those values. Synthetic data is used
only as test input.

WHO extracts are not distributed with the repository while the
redistribution question is open. That is a data-governance and licensing
review item, not a methodology question: see
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-1.

## Synthetic fixtures (committed)

| File | Dataset / indicator | Rows | Kept by the legacy cleaner |
|---|---|---|---|
| `MDG_0000000025_synthetic.json` | `WHO_ATBRTH` / ATBRTH | 60 | 46 observations, 8 countries |
| `WHS4_100_synthetic.json` | `WHO_DPTCOV` / DPTCOV | 96 | 87 observations, 6 countries |
| `HWF_0001_synthetic.json` | `WHO_PHYSPC` / PHYSPC | 91 | 82 observations, 8 countries |

How they were made:

- **Written by a script.** `build_synthetic.py` writes them
  deterministically (`.venv/bin/python tests/fixtures/who/build_synthetic.py`).
  `tests/golden/test_golden_who.py` checks that the committed files are
  exactly its output.
- **Only the layout is copied.** The GHO OData response shape (the
  `{"@odata.context", "value": [rows]}` envelope and the row fields) is
  reproduced. Every value is invented by simple formulas; nothing is copied
  from WHO data or perturbed from it.
- **Labelled on every row.** `Comments` reads "SYNTHETIC TEST ROW - invented
  for SSPI parity tests; not WHO data". The change date is a fixed
  placeholder, and the OData context points at `example.invalid`.
- **Country codes.** MYS, AUT and USA are used for the researcher guide's
  query. Edge cases use ISO 3166 user-assigned codes: QMA to QMF for
  countries, and QRA, QWB and QUN for aggregates.

They cover:
- aggregates of every kind (GLOBAL, REGION, WORLDBANKINCOMEGROUP, UNREGION);
- `"No data"` rows, both inside a gap and as a country's only row;
- reported zeros;
- both goalposts, values beyond them, and an outlier;
- gaps, single values, late starts and early ends, and a gap before 2000;
- a rounded display value;
- non-ISO codes, which are kept as the legacy cleaner kept them;
- the five hard-coded ATBRTH recipients being absent.

`tests/golden/generate_who_cases.py` ran the pinned legacy cleaners and
routes on these files, and the new backend reproduces that output exactly
(`tests/golden/test_golden_who.py`). The migration gate is unchanged: a
committed fixture, golden files from the pinned commit, exact parity and a
register row.

## Real WHO data (kept outside the repository)

The real-data parity evidence is kept intact, for local and opt-in
validation, in a directory outside version control. By convention that is
`local-data/who/`, which `.gitignore` excludes. Its layout:

| Path | Content |
|---|---|
| `fixtures/MDG_0000000025_sample.json` | 200 verbatim rows of the 2026-10-18 response (12 countries, GLOBAL, EUR) |
| `fixtures/WHS4_100_sample.json` | 275 verbatim rows (8 countries, GLOBAL, EUR, WB_HI) |
| `fixtures/HWF_0001_sample.json` | 205 verbatim rows (10 countries, GLOBAL, AFR, WB_LI) |
| `golden/who_{atbrth,dptcov,physpc}_cases.json`, `golden/{atbrth,dptcov,physpc}_cases.json` | the pinned legacy code's output on those subsets (generated 2026-10-18; their `fixture` field records the subsets' former path `tests/fixtures/who/<code>_sample.json`) |
| `responses/2026-10-18/<code>.json` | the full GHO responses the subsets were cut from, as served |
| `responses/2026-10-19/<code>.json` | the rows of the 2026-10-19 live validation fetch, re-serialized |

`REAL_DATA.sha256` in this directory is committed. It pins every one of
those files by SHA-256 and contains no WHO data. To run the real-data
tests:

```
SSPI_WHO_REAL_DATA=local-data/who .venv/bin/python -m pytest -m who_real_data
SSPI_WHO_REAL_DATA=local-data/who SSPI_TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/db/test_healthcare_end_to_end.py
```

Every file is checked against the manifest before use. A missing or
changed file fails the test; it does not skip.
`tests/golden/test_golden_who.py` also fails if any of these files appears
anywhere under `tests/`. To verify by hand:
`(cd local-data/who && shasum -a 256 -c ../../tests/fixtures/who/REAL_DATA.sha256)`.

Validation records for the real data:

- **Subsets.** Each subset's rows are byte-for-byte JSON-equal to rows of
  the full response, in API order, with the same `@odata.context`. Only the
  selection of rows was reduced. Full responses: `MDG_0000000025` has 2,749
  rows (SHA-256 `083cc278…c3c77e`), `WHS4_100` has 5,337 rows
  (`390f5608…a45241c`) and `HWF_0001` has 3,693 rows (`06870678…faac496e`).
  The full values are in `REAL_DATA.sha256`.
- **Live check, 2026-10-19.** The live responses were row-for-row identical
  to those of 2026-10-18. On the full responses, the pinned legacy cleaners
  and routes and the new backend produced identical scores. These are the
  SHA-256 digests of the sorted (country, year, score, unit, imputed)
  records:

  | Indicator | Digest | Observed | Imputed |
  |---|---|---|---|
  | ATBRTH | `d68d77adaa9b1866ce41a7cd795ec04d6396dfda0e01d14887fbaa623a67f8fb` | 2,567 | 2,222 |
  | DPTCOV | `535674ab706410d46b02c35e74d07cd15484eff7bc359df5d14675a4b76ffae0` | 5,051 | 0 |
  | PHYSPC | `4d6a1b36b3759414b41660c6ef0091a590cbbd8b5acce53f1129fd91aafb7f73` | 3,682 | 1,812 |

- **What the data says about ownership.** The GHO `Indicator` entity holds
  only a code, a name and a language, and `DataSourceDim` is empty on every
  row, so the data carries no licence or owner field. The credits that do
  appear:
  - `WHS4_100`: the indicator name ends "(WUENIC)", meaning WHO/UNICEF
    estimates.
  - `MDG_0000000025`: every country row's `Comments` cites a national
    statistical office, ministry, DHS or UNICEF MICS source.
  - `HWF_0001`: every country row's `Comments` cites WHO's National Health
    Workforce Accounts portal.

## Source, owners and attribution

The real data comes from the World Health Organization's Global Health
Observatory:
- "Births attended by skilled health personnel (%)" comes from the
  UNICEF/WHO joint database, mostly from national household surveys.
- "Diphtheria tetanus toxoid and pertussis third-dose (DTP3) immunization
  coverage among 1-year-olds (%) (WUENIC)" is the WHO/UNICEF Estimates of
  National Immunization Coverage.
- "Medical doctors (per 10,000)" comes from the National Health Workforce
  Accounts, reported by WHO Member States.

Two things are still open, in `docs/data-governance-review.md` (GOV-1):
- which WHO terms govern data read through the GHO OData API;
- whether extracts may be redistributed, and with what attribution.

That document also separates legal permission from attribution to
contributing organizations.
