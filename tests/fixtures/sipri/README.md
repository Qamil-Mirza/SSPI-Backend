# SIPRI source fixtures

**`armstransfers_synthetic.json`, `milex_synthetic.json` and
`milex_workbook_synthetic.xlsx` are synthetic. Their values are invented, not
SIPRI's.**

`SIPRI_ARMEXP` is requested from the SIPRI Arms Transfers Database API with
the legacy collector's request (`src/sspi/ingestion/sipri.py`). The legacy
collector read `SIPRI_MILEXP` from the SIPRI Military Expenditure Database
API (`milex_synthetic.json` copies that answer's layout, to characterize the
legacy cleaner); its approved source is now SIPRI's revised workbook
(MILEXP-4; `milex_workbook_synthetic.xlsx` copies its "Share of GDP" sheet).
SIPRI's terms allow free analytical use under a
fair-use policy (non-commercial, less than 10 per cent of a data set) and ask
for attribution; reproduction beyond that needs SIPRI's authorization. The
original answers are therefore not distributed with the repository. See
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-7.

## Synthetic answers (committed)

- **Written by a script**, `build_synthetic.py`;
  `tests/golden/test_golden_global_role.py` checks that the committed files
  are exactly its output.
- **Only the layout is copied**: the arms-transfers answer's
  `{"result": "<csv text>"}` with SIPRI's notes, the `Exports by,` header
  (36 year columns, then total and percentage columns), a `Total world
  export` row and trailing blank lines; the military-expenditure answer's
  sections, with a "Share of GDP" sheet headed `Country, Notes, 1990.0 …
  2024.0`, region rows, note marks and fractions written as text.
- **Real names, invented values.** The names exercise the legacy matching
  (Korea rules, the skip list, names the matcher misses, among them Brunei
  and Bosnia-Herzegovina, which the approved ARMEXP-4 table repairs). The arms answer
  holds every-year and sparse suppliers, published zeros (`0 `), history
  before 2000 only, values after 2023 only and values around the 500
  goalpost; the military answer holds recognised and unrecognised note marks,
  `...`, `xxx`, a value above 1 and Iceland's empty row.
- **Variants**, built in memory, never committed: an answer without the
  table, two names for one country, and the probes in which the United Arab
  Emirates exports (ARMEXP-2) or the share sheet is empty. The MILEXP-2
  check of shares of 100% or more is exercised with an invented stand-in
  recorded in `milexp_workbook_synthetic_cases.json` (Eritrea 1991, 150%).
  The workbook holds published zeros (Costa Rica, Panama from 2000), markers,
  former states, years outside 1990–2024 and Iceland without values; its
  variants (never committed) publish Iceland's zero or break the schema.

## Original answers (not committed)

Kept in `local-data/sipri/` (ignored by git) with the legacy code's output on
them in `local-data/sipri/golden/` (`generate_global_role_cases.py --real
local-data`); `REAL_DATA.sha256` pins them; `SSPI_SIPRI_REAL_DATA=local-data/sipri`
runs the `sipri_real_data` tests. The arms API has no editions, so a new
download differs (each answer states when it was generated); the pinned
answers are those of 2026-10-26. `SIPRI-Milex-data-1949-2025_v1.2.xlsx` is
SIPRI's revised workbook (https://www.sipri.org/databases/milex, revised 27
April 2026), downloaded 2026-10-26, MILEXP's approved source; the real-data
tests read it as a configured local copy (`SIPRIClient(local_workbook_directory=...)`),
which must match the pinned checksum.
