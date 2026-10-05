# FAOSTAT source fixture

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
