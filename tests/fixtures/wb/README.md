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

## GC.TAX.TOTL.GD.ZS

`GC.TAX.TOTL.GD.ZS_sample.json` is a row subset of one response of
`https://api.worldbank.org/v2/country/all/indicator/GC.TAX.TOTL.GD.ZS?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-09; 17,556 rows,
SHA-256 of the full response
`bd749f9aa4874cf8222800556b7f25dcb2831483ded6fe62bcd0715d2f48f0be`), in the
API shape, with `per_page` and `total` set to the number of rows kept.

Rows kept (1,386, 473 with a value): every row, 1960-2025, for

- Malaysia, Austria and the United States;
- Japan (last value 1993: forward extrapolation over thirty years), Kuwait
  (a 1975-1976 gap, last value 1998), India (a 2019-2021 gap), Indonesia
  (gaps in 2000 and 2005-2007, last value 2009), Greece and Andorra (first
  value 2018);
- the United Arab Emirates (the smallest values, about 0.04 % of GDP),
  Timor-Leste and Sudan (above 100 % of GDP; Sudan 638.7 in 1999);
- Vietnam, Nigeria, Venezuela and Algeria (all null: the legacy hard-coded
  reference-class recipients) and Pakistan (all null, not a recipient);
- World (`WLD`), European Union (`EUU`), High income (empty
  `countryiso3code`, country id `XD`) and Kosovo (`XKX`), all skipped.

The source has no zero and no negative value. It is the parity fixture for
`WB_TAXREV` and `TAXREV`. See `tests/golden/generate_tax_cases.py`.

## NY.GDP.PCAP.CD

`NY.GDP.PCAP.CD_sample.json` is a row subset of one response of
`https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-18; 17,556 rows,
SHA-256 of the full response
`db261cc00cf014d9441b9834d5382dc47d83188b59473cf492b267f4b4553cc6`), in the
API shape, with `per_page` and `total` set to the number of rows kept.

Rows kept (2,046, 1,800 with a value): every row, 1960-2025, for

- the countries of the UN SDG 2.2.1 sample (`tests/fixtures/unsdg/2_2_1_sample.json`):
  Malaysia, the United States, India, Burundi, Australia, Germany, Japan,
  China, Nigeria, Pakistan, Brazil, Mexico, Singapore, Kuwait, Saudi Arabia,
  North Korea (every row null), Yemen (1990-2018) and the Turks and Caicos
  Islands (2001-2024);
- ten economies with no stunting estimate, the regression recipients:
  Austria, Switzerland and Luxembourg (above 100,000 dollars in recent
  years), Canada, New Zealand, Russia (from 1988), Iceland, the United Arab
  Emirates (from 1970), Bermuda and Monaco (from 1970);
- World (`WLD`), High income (empty `countryiso3code`, country id `XD`) and
  Kosovo (`XKX`), all skipped.

The source has no zero and no negative value. It is the parity fixture for
`WB_GDP_PERCAP_CURPRICE_USD` and, with the UN SDG 2.2.1 samples, for
`CSTUNT`. See `tests/golden/generate_healthcare_cases.py`.

## SH.STA.BASS.ZS and SH.H2O.SMDW.ZS

The two Infrastructure samples are row subsets of one response each,
downloaded on 2026-10-19 with `?format=json&per_page=20000`, in the API
shape, with `per_page` and `total` set to the number of rows kept:

| Sample | Full response | Rows kept (with a value) |
|---|---|---|
| `SH.STA.BASS.ZS_sample.json` | source 2 (WDI, WHO/UNICEF JMP), last updated 2026-10-08; 17,556 rows, SHA-256 `417d31a7a79143e6918d4a42137cc128d72277ade00ddb109b77d6918ded4698` | 1,320 (430) |
| `SH.H2O.SMDW.ZS_sample.json` | source 2 (WDI, WHO/UNICEF JMP), last updated 2026-10-08; 17,556 rows, SHA-256 `aedd516bc87741b962359fff2920867a7b8579502b934c92c6ae3da7bba76c8c` | 1,320 (349) |

Rows kept: every row, in API order, whose `countryiso3code` is one of MYS,
AUT, USA, ARG, SAU, ROU, RUS, AGO, ETH, TZA, KWT, GBR, KOR, COG, TCA, CHN,
WLD, AFE or XKX, or which has no `countryiso3code` and the country id XD
(High income). What each one exercises:

- Malaysia, Austria and the United States: the researcher guide's query
  (the United States' safely managed water starts in 2005);
- Argentina (sanitation ends 2016), Angola (2022) and Congo (2021):
  forward extrapolation to 2023; Argentina, China and Saudi Arabia have no
  safely managed water estimate;
- Saudi Arabia (2013), Romania (2001), Russia (2002), Turks and Caicos
  (2016) and Korea (water, 2002): late starts, backward extrapolation;
- Ethiopia and Tanzania: the smallest values, below the 50 % sanitation
  goalpost; Kuwait and the United Kingdom: 100 %;
- World, Africa Eastern and Southern, High income and Kosovo: skipped.

They are the parity fixtures for `WB_SANSRV`, `SANSRV`, `WB_DRKWAT` and
`DRKWAT`. See `tests/golden/generate_infrastructure_cases.py`.

## EG.ELC.ACCS.ZS

`EG.ELC.ACCS.ZS_sample.json` is a row subset of one response of
`https://api.worldbank.org/v2/country/all/indicator/EG.ELC.ACCS.ZS?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-19; 17,556 rows,
SHA-256 of the full response
`677da72ab359c44e5fa2c4697a5eee678374e206efc26a2a6a78b060f482d30e`), in the
API shape, with `per_page` and `total` set to the number of rows kept.

Rows kept (726, 306 with a value): every row, in API order, of:
- Malaysia, Austria, the United States, Chad, Niger, South Sudan and the
  United Kingdom;
- World, Africa Eastern and Southern, High income (no ISO3 code, id `XD`)
  and Kosovo, all skipped.

Niger, South Sudan and the United Kingdom have access data but no value in
the synthetic WEF workbook, so their AQELEC groups are incomplete. The
source has no zero value. With `tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx`,
it is the parity fixture for `WB_AVELEC` and `AQELEC`. See
`tests/golden/generate_wef_cases.py`.
