# ILO source fixtures

Two complete, unmodified SDMX-JSON responses of the ILOSTAT SDMX API,
downloaded 2026-10-05 with the requests the legacy collectors sent:

| File | Request | Rows |
|---|---|---|
| `DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json` | `https://sdmx.ilo.org/rest/data/DF_EMP_DWAP_SEX_AGE_RT/.A..SEX_T.AGE_YTHADULT_Y15-64?format=jsondata&startPeriod=2000` | 2,690 observations, 211 areas, 2000-2025 |
| `DF_ILR_CBCT_NOC_RT.json` | `https://sdmx.ilo.org/rest/data/DF_ILR_CBCT_NOC_RT?format=jsondata&startPeriod=1990-01-01&endPeriod=2024-12-31` | 865 observations, 99 areas, 2000-2020 |

The first is the employment-to-population ratio, both sexes, ages 15-64
(`ILO_EMPLOY_TO_POP`, indicator `EMPLOY`). The second is the collective
bargaining coverage rate (`ILO_COLBAR`, indicator `COLBAR`); the ILO
publishes nothing after 2020 for it and nothing for ten SSPI67 members
(ARE, DZA, ECU, IND, IRN, IRQ, KWT, NGA, PAK, SAU).

Neither response contains a null value or an aggregate area code; those
paths of the adapter are covered with synthetic messages in
`tests/unit/test_ilo_adapter.py`.

They are the parity fixtures for both datasets and both indicators. See
`tests/golden/generate_worker_engagement_cases.py`.
