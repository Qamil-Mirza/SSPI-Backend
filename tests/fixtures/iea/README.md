# IEA source fixture

`TESbySource_sample.json` is a row subset of the response of

    https://api.iea.org/stats/indicator/TESbySource

(total energy supply by source), downloaded 2026-10-05 with a plain GET, no
key and no parameters, as the legacy collector did. The full response had
34,039 rows for 179 areas, 1990-2025, all in terajoules. The file is a JSON
array like the response; rows are verbatim and in source order, one per
line. Only the selection of areas was reduced.

Areas kept (2,034 rows, every product and year the source has for them):

| Area | Why |
|---|---|
| `USA` | all seven products in every year: complete observed groups |
| `JPN` | nuclear reported as zero in 2014: dropped by the cleaner, then interpolated |
| `LTU` | nuclear ends in 2009: carried forward to 2023 |
| `PAK` | zero values in "solar, wind and other renewables" until 2012: dropped, then carried back |
| `MYS`, `AUT` | no nuclear row at all: zero-filled; Malaysia also has null values and interior gaps |
| `SGP` | no nuclear and no hydro row; gaps in coal |
| `BOL` | not an SSPI67 member and no nuclear row: never scored; has zero values |
| `WORLD` | an aggregate: skipped |
| `GUYANA` | a country the source names in full instead of by ISO code: skipped, as in legacy |

The endpoint is the interface the pinned legacy backend used. The IEA does
not document it as a stable public API, so it may change or disappear
without notice. The data belong to the IEA; this small excerpt is kept only
so that the parity tests run offline, and nothing here grants a right to
redistribute IEA data.

It is the parity fixture for the seven `IEA_*` datasets and for `ALTNRG`.
See `tests/golden/generate_iea_cases.py`.
