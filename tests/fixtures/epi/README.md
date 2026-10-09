# EPI source fixture

`epi2024indicators_P5_Indicator_SNM_ind_na.csv` is the file
`P5_Indicator/SNM_ind_na.csv` from `epi2024indicators.zip`, the archive the
legacy collector (`sspi_flask_app/api/datasource/epi.py`) downloaded from
`https://epi.yale.edu/downloads/epi2024indicators.zip`. That URL now serves
an HTML page; the archive was recovered from the Internet Archive's capture
of the URL (`https://web.archive.org/web/20260424222356id_/https://epi.yale.edu/downloads/epi2024indicators.zip`,
zip SHA-256 `7ac83a74aa7959b8ce49267f59fab65bac035b2d7b6b0c8d55302573b115774d`)
on 2026-10-01. The CSV is committed byte for byte (SHA-256
`9b5dcf42be488f55b1ba981400c938288c7ac411fbffc655b14806b953a76536`).

It is the historical parity reference for `EPI_NITROG` and `NITROG`
(`tests/golden/epi_nitrog_cases.json`, `tests/golden/nitrog_cases.json`).
Production ingestion reads the 2026 edition archive instead; see NITROG-1 in
`docs/methodology-conflicts.md`.

`epi2024indicators_P5_Indicator_WPC_ind_na.csv` is `P5_Indicator/WPC_ind_na.csv`
from the same recovered archive, committed byte for byte (SHA-256
`741d97b67a88f9b98b1aac2451e341aeb8a7cf012e9d134eabcf67fd456117c5`). It is
the historical parity reference for `EPI_MSWGEN` and `MSWGEN`
(`tests/golden/epi_mswgen_cases.json`, `tests/golden/mswgen_cases.json`).
The 2026 edition has no WPC file, so `EPI_MSWGEN` has no live source and is
not ingestible (`UNAVAILABLE_SOURCES`); see `docs/indicator-migration.md`.
