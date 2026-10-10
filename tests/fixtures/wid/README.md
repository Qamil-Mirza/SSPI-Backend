# World Inequality Database source fixture

Row subsets of the per-country files inside the official WID bulk archive,
`https://wid.world/bulk_download/wid_all_data.zip` (882,096,194 bytes,
last modified 2026-09-09, downloaded 2026-10-05), for the 66 members of the
`SSPI67` country group: `WID_data_<XX>.csv` and `WID_metadata_<XX>.csv`,
keyed by ISO 3166-1 alpha-2 as in the archive. Headers and rows are verbatim
(semicolon-delimited).

Data rows kept per country:

- variable `sptincj992` (share of pre-tax national income, equal-split
  adults, age 20+), percentiles `p0p50`, `p90p100` and `p99p100`, years
  from 1998 on. `p99p100` and the years 1998-1999 are decoys: no dataset
  selects them;
- variable `aptincj992`, percentile `p0p50`, years 2000 and 2001 (a decoy
  variable with the same percentile);
- variable `sdiincj992` (share of post-tax national income, equal-split
  adults, age 20+), percentiles `p0p50`, `p90p100` and `p99p100`, years from
  1998 on, added 2026-10-09 from the same archive edition for TXRDST.
  `p99p100` and 1998-1999 are again decoys. Every row present before was
  kept unchanged and in archive order.

Metadata rows kept per country: the rows for `sptincj992`, `aptincj992` and
`sdiincj992`.

It is the parity fixture for `WID_NINCSH_PRETAX_P0P50`,
`WID_NINCSH_PRETAX_P90P100`, `ISHRAT`, `WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50`,
`WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100` and `TXRDST`, and supplies the ISHRAT scores the
`GINIPT` regression fallback is trained on. See
`tests/golden/generate_inequality_cases.py` and
`tests/golden/generate_tax_cases.py`.
