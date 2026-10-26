# V-Dem archive fixtures

**`V-Dem-CY-FullOthers_csv_v13_synthetic.zip` is synthetic. Its values are
invented, not V-Dem's.**

`VDEM_RULELW` (column `v2x_rule`) and `VDEM_EDEMOC` (column `v2x_polyarchy`)
are read from one archive, "Country-Year: V-Dem Full+Others", version 13
(March 2023), at the legacy collector's address
`https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip`, pinned
by SHA-256 in `src/sspi/ingestion/vdem.py`. The original archive is not
distributed with the repository while its terms are open: V-Dem states a
CC BY-SA 4.0 licence today, the v13 archive states none. See
[`docs/data-governance-review.md`](../../../docs/data-governance-review.md),
GOV-6.

## Synthetic archive (committed)

- **Written by a script**, `build_synthetic.py`, deterministically (fixed
  member dates and order); `tests/golden/test_golden_rights.py` checks that
  the committed file is exactly its output.
- **Only the layout is copied**: a ZIP holding one CSV and a non-CSV member;
  the identifying columns `country_name`, `country_text_id`, `country_id`,
  `year`, `historical_date`, `project`; `v2x_polyarchy` and `v2x_rule` with
  their `*_codelow`, `*_codehigh` and `*_sd` companions; empty cells for
  missing values. Every row's `project` cell says the values are invented.
- **Real names and V-Dem identifiers, invented values.** It covers the
  years before, at and after the cleaner's window (1989–2026, with the
  golden run in 2026), values exactly 0 and 1 and beyond both goalposts,
  values with more than ten decimals, an empty run inside a series, a
  country with every value empty (`ZZB`), one with history before 1991 only
  (`DDR`), one with values only after 2023 (`SSD`), a series ending in 2015,
  and V-Dem's non-ISO identifiers (`XKX`, `PSG`).
- **Variants**, built in memory, never committed: a duplicate country-year,
  a lowercase code, a text value, the two columns missing, and the CSV in
  Latin-1. The golden files record how the legacy collector, cleaners and
  clean collection failed on each.

## Original archive (not committed)

Kept in `local-data/vdem/` (ignored by git), with the legacy code's output
on it in `local-data/vdem/golden/` (`generate_rights_cases.py --real
local-data`). `REAL_DATA.sha256` pins both; `SSPI_VDEM_REAL_DATA=local-data/vdem`
runs `tests/golden/test_golden_rights_real_data.py` (marker
`vdem_real_data`). To recreate it:

    mkdir -p local-data/vdem
    curl -L -o local-data/vdem/V-Dem-CY-FullOthers_csv_v13.zip \
        https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip
    shasum -a 256 local-data/vdem/V-Dem-CY-FullOthers_csv_v13.zip   # must match REAL_DATA.sha256
