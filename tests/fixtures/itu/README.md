# ITU Global Cybersecurity Index transcription fixtures

**`gci-local-indicator-summary_synthetic.csv` is synthetic. Its scores are
invented, not ITU's.**

The only source of `ITU_CYBSEC` is the SSPI's own hand transcription of the
ITU Global Cybersecurity Index country scores (editions 2014, 2017, 2018,
2020 and 2024), committed to the legacy repository as
`local/CYBSEC/gci-local-indicator-summary.csv`. Production ingestion reads
it as a local file (`sspi.ingestion.localfiles`, pinned by SHA-256, from
`local-data/itu/`) and normalizes it as the legacy cleaner did
(`sspi.ingestion.itu`), with the approved correction of five country
names (CYBSEC-1).

It is not distributed with the repository while its licence terms are open:
the 2024 report is CC BY-NC-SA 3.0 IGO, and the terms of the other editions
and the status of a transcription are unreviewed. See
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-4.

## Synthetic transcription (committed)

- **Written by a script**, `build_synthetic.py`;
  `tests/golden/test_golden_cybsec.py` checks that the committed file is
  exactly its output.
- **Only the layout is copied**: the header with its legacy misspelling
  (`Globa Rank`) and repeated `Global Rank` columns, a trailing empty
  column, 2014-2018 scores on 0-1 and 2020-2024 scores on 0-100, blank cells.
- **Real country names, invented scores.** The names exercise the legacy
  name matcher (`United States`, `Korea (the Republic of)`, `Russian
  Federation`, `Türkiye`, `Niger` and `Nigeria`, `Democratic Republic of the
  Congo`, `Viet Nam`, ...); the scores attached to them mean nothing. It
  also holds published zeros, a 100 in 2024, values with more than ten
  decimals, an edition left blank, a country in two editions only and a
  country with every cell blank.
- **Variants**, built in memory, never committed: the five spellings of
  the original transcription the legacy matcher cannot place (legacy
  refused the dataset; the approved correction, CYBSEC-1, maps them to CIV,
  MKD, FSM, PSE and VAT, and the golden files record the legacy cleaner's
  rows with only that correction and the legacy scores on them), a name
  neither the matcher nor the correction codes, and two names for one code.
  The last two are refused by legacy and by the new adapter.

## Original transcription (kept outside the repository)

| Path | Content |
|---|---|
| `local-data/itu/gci-local-indicator-summary.csv` | a copy of `sspi-data-webapp@76f842b:local/CYBSEC/gci-local-indicator-summary.csv` (11,308 bytes) |
| `local-data/itu/golden/itu_cybsec_cases.json` | the pinned legacy code's output on it (`generate_public_safety_cases.py --real local-data`) |

`REAL_DATA.sha256` pins both. To run the opt-in tier:

```
SSPI_ITU_REAL_DATA=local-data/itu .venv/bin/python -m pytest -m itu_real_data
```
