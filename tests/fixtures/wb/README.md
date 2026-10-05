# World Bank source fixture

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
