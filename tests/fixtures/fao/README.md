# FAOSTAT source fixtures

## Land Use (domain RL)

`Inputs_LandUse_E_All_Data_(Normalized)_sample.csv` is a row subset of the
official FAOSTAT bulk download for domain RL (Land Use),
`https://bulks-faostat.fao.org/production/Inputs_LandUse_E_All_Data_(Normalized).zip`
(zip SHA-256 `f6ccf002c3e83a32613d84f032e002b77ac80c8f871c454b12104815f36a9ad5`,
CSV dated 2026-09-16, downloaded 2026-10-01). Header and rows are verbatim
(CRLF line endings, quoted fields, M49 codes with their leading apostrophe).

Rows kept: every element for items 6717 (Naturally regenerating forest) and
6646 (Forest land) for 18 areas: Albania, Austria, Kenya, Malaysia,
Singapore, Switzerland, United States of America (the usual sample
countries); Belgium, Luxembourg, United Arab Emirates, Kuwait (the hard-coded
DEFRST/CARBON imputation recipients); China, mainland (M49 156) and China
(M49 159); Belgium-Luxembourg (M49 058); World and Europe (aggregates);
Nicaragua (empty values, flag L); Greenland (zero carbon-stock values).
2777 rows.

It is the parity fixture for `UNFAO_FRSTLV`, `UNFAO_FRSTAV`, `UNFAO_CRBNLV`,
`UNFAO_CRBNAV`, `DEFRST` and `CARBON`. The legacy backend read the FAOSTAT
JSON API, not this file; `tests/golden/generate_fao_land_cases.py` explains
how the rows are presented to the legacy cleaner.

## Food Balances (domain FBS)

`FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv` is a row subset of
the official FAOSTAT bulk download for domain FBS (Food Balances, 2010-),
`https://bulks-faostat.fao.org/production/FoodBalanceSheets_E_All_Data_(Normalized).zip`
(zip SHA-256 `26200855ed5da3d0805e34219124e241d0e0bc6959d0995ebc77a10dd84cbaf1`,
CSV dated 2025-10-14, downloaded 2026-10-08). Header and rows are verbatim.

Rows kept (524): item 2731 (Bovine Meat), elements 5511 (Production),
645 (Food supply quantity (kg/capita/yr)) and 5611 (Import quantity, not
selected by any dataset), for 13 areas: United States of America, Austria,
Malaysia, Pakistan (rows after 2020 removed, so BEEFMK carries its 2020
score forward), Belgium, Luxembourg, Kuwait, China, mainland (M49 156) and
China (M49 159), China, Taiwan Province of (no World Bank population),
Micronesia (Federated States of) (zero production, 2019-2023 only), World
and Europe (aggregates); plus item 2501 (Population) for the United States,
not selected. Singapore and Japan are not in the bulk file at all.

It is the parity fixture for `UNFAO_BFPROD`, `UNFAO_BFCONS` and, with
`tests/fixtures/wb/SP.POP.TOTL_sample.json`, `BEEFMK`. See
`tests/golden/generate_ghg_cases.py`.
