# ILO source fixtures

Three complete, unmodified SDMX-JSON responses of the ILOSTAT SDMX API,
downloaded with the requests the legacy collectors sent (the first two on
2026-10-05, the third on 2026-10-18):

| File | Request | Rows |
|---|---|---|
| `DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json` | `https://sdmx.ilo.org/rest/data/DF_EMP_DWAP_SEX_AGE_RT/.A..SEX_T.AGE_YTHADULT_Y15-64?format=jsondata&startPeriod=2000` | 2,690 observations, 211 areas, 2000-2025 |
| `DF_ILR_CBCT_NOC_RT.json` | `https://sdmx.ilo.org/rest/data/DF_ILR_CBCT_NOC_RT?format=jsondata&startPeriod=1990-01-01&endPeriod=2024-12-31` | 865 observations, 99 areas, 2000-2020 |
| `DF_SDG_F881_SEX_MIG_RT.json` | `https://sdmx.ilo.org/rest/data/DF_SDG_F881_SEX_MIG_RT?format=jsondata` | 720 observations in 366 series; 457 in the `SEX_T` / `MIG_STATUS_TOTAL` slice, 103 areas, 2000-2024 |

The first is the employment-to-population ratio, both sexes, ages 15-64
(`ILO_EMPLOY_TO_POP`, indicator `EMPLOY`). The second is the collective
bargaining coverage rate (`ILO_COLBAR`, indicator `COLBAR`); the ILO
publishes nothing after 2020 for it and nothing for ten SSPI67 members
(ARE, DZA, ECU, IND, IRN, IRQ, KWT, NGA, PAK, SAU). The third is SDG 8.8.1,
fatal occupational injuries per 100,000 workers, by sex and migrant status;
`ILO_FATINJ` (indicator `FATINJ`) keeps the totals (`SEX_T`,
`MIG_STATUS_TOTAL`). Most areas report one year, and thirteen SSPI67 members
none.

No response contains a null value or an aggregate area code; those paths of
the adapter are covered with synthetic messages in
`tests/unit/test_ilo_adapter.py`.

They are the parity fixtures for the three datasets and their indicators.
See `tests/golden/generate_worker_engagement_cases.py` (EMPLOY, COLBAR) and
`tests/golden/generate_worker_wellbeing_cases.py` (FATINJ).
