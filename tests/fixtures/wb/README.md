# World Bank source fixtures

## SI.POV.GINI

`SI.POV.GINI_sample.json` is a row subset of one response of the World Bank
Indicators API,
`https://api.worldbank.org/v2/country/all/indicator/SI.POV.GINI?format=json&per_page=20000`
(source 2, last updated 2026-07-13, downloaded 2026-10-05; 17,490 rows).
The file keeps the API shape, `[page metadata, rows]`; rows are verbatim and
in API order, and the page metadata's `per_page` and `total` were set to the
number of rows kept.

Rows kept (2,175):

- every row with a value for the 62 SSPI67 members that have one, for every
  other economy whose ISO3 code starts with A, B or C, and for Namibia
  (its 1993 value, 71.1, lies outside the goalposts);
- every row, null values included, for Malaysia, Singapore and Kuwait
  (Singapore and Kuwait have no Gini value in any year), Kosovo (`XKX`, not
  an ISO 3166-1 code), and the aggregates World (`WLD`), Africa Eastern and
  Southern (`AFE`) and High income (empty `countryiso3code`, country id `XD`).

Kuwait, New Zealand, Saudi Arabia and Singapore have no valued row here, as
in the full response: they are the countries the legacy GINIPT regression
fallback predicts.

It is the parity fixture for `WB_GINIPT` and, with `tests/fixtures/wid`, for
`GINIPT`. See `tests/golden/generate_inequality_cases.py`.

## SP.POP.TOTL

`SP.POP.TOTL_sample.json` is a row subset of one response of
`https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json&per_page=20000`
(source 2, last updated 2026-07-13, downloaded 2026-10-08; 17,490 rows), in
the API shape, with `per_page` and `total` set to the number of rows kept.

Rows kept (1,056): every row, 1960-2025, for the countries of the
Greenhouse Gases fixtures (USA, AUT, MYS, SGP, PAK, KHM, BOL, KWT, BEL, LUX,
CHN, FSM), Palestine (`PSE`, 30 null years), Kosovo (`XKX`, not an ISO
3166-1 code), World (`WLD`) and "Not classified" (empty `countryiso3code`,
country id `XY`, all null).

It is the parity fixture for `WB_POPULN` and, with the IEA and FAOSTAT
samples, for `GTRANS` and `BEEFMK`. See `tests/golden/generate_ghg_cases.py`.

## SE.PRM.ENRL.TC.ZS

`SE.PRM.ENRL.TC.ZS_sample.json` is a row subset of one response of
`https://api.worldbank.org/v2/country/all/indicator/SE.PRM.ENRL.TC.ZS?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-08; 17,556 rows,
SHA-256 of the full response
`3cc041966d4dfa36736840264d20ed315505ddc50616ec57db7e1ee9ac84f6f4`), in the
API shape, with `per_page` and `total` set to the number of rows kept.

Rows kept (1,122): every row, 1960-2025, for

- Malaysia, Austria and the United States (the United States has values only
  for 2014, 2015 and 2017: backward extrapolation, one interpolated year,
  forward extrapolation);
- Venezuela and Australia, whose last values are 1987 and 1999 (forward
  extrapolation from before 2000), and Japan, whose first is 2013;
- Kazakhstan and Nepal, two of the four countries with a 2019 value;
- Kuwait (below the upper goalpost, 9), Pakistan and the Central African
  Republic (above the lower goalpost, 40; 100.2 in 2008), San Marino (the
  smallest value, 5.2) and Sint Maarten (one value);
- World (`WLD`), Africa Eastern and Southern (`AFE`), High income (empty
  `countryiso3code`, country id `XD`) and Kosovo (`XKX`), all skipped.

The source has no zero value. It is the parity fixture for `WB_PUPTCH` and
`PUPTCH`. See `tests/golden/generate_education_cases.py`.
