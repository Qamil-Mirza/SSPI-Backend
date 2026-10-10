# Indicator migration: the parity gate

For maintainers porting an indicator from the legacy backend
(`sspi-data-webapp`). Researchers do not need this page.

## The rule

> An indicator is migrated only when the new backend reproduces the pinned
> legacy backend **from the same committed source fixture**, or every
> difference is written down and justified.

"Same source snapshot" is the point. Running the legacy backend on one live
download and the new backend on another compares two vintages of the data,
not two implementations. Live figures may illustrate the size of an effect
in `methodology-conflicts.md`; they are never parity evidence.

Pinned legacy commit: `76f842b08e551dfa8fb9563e4c812be086654ba6`
(`PINNED_LEGACY_COMMIT` in `tests/golden/parity.py`).

## How parity is tested

```
legacy backend at the pinned commit
    |   tests/golden/generate_*.py, run once, in the legacy virtualenv
    v
committed golden file  (tests/golden/*_cases.json)
    |   generated FROM a committed source fixture (tests/fixtures/...)
    v
offline test: the same fixture through the new backend, compared record by record
```

- Generators import legacy functions directly and need the legacy repository
  and its virtualenv. They are run by hand, never by `pytest`.
  `generate_legacy_cleaner_cases.py` calls the registered legacy cleaner
  function itself with its Mongo handles stubbed, so dimension filters and
  derived series are the legacy code's own output; prefer it for new
  datasets. `generate_compute_route_cases.py` does the same for a compute
  route whose formula is copied verbatim.
- Golden files and source fixtures are committed. Normal test runs need no
  legacy repository, no legacy virtualenv and no network.
- Every golden file records the legacy commit and that the legacy working
  tree was clean. Tests refuse a file from any other commit.
- A golden file is never edited by hand. To change one, change the generator
  or the fixture and regenerate.

## What must match

| Dimension | Identity | Compared |
|---|---|---|
| A. Canonical observations | (dataset_code, country_code, year) | exact identity set, value, unit, count, country coverage, year range, areas skipped |
| B. Indicator scores | (indicator_code, country_code, year) | exact identity set, score, unit, each input's dataset, value and unit, observed or imputed classification, score range |
| C. Imputation, where the legacy indicator imputes | (dataset_code, country_code, year) | which values are imputed, method, value, distance, reference mean and contributing count, recipients, that observed and imputed score sets do not overlap |
| D. Missing data | as above | empty source values produce no observation; incomplete groups are the same identities; nothing is scored that legacy did not score |

Provenance is compared where it carries methodology: imputation flags,
methods and distances. Legacy clean documents hold no per-observation source
flags, so flags such as `nature` are new information and have no legacy
counterpart to compare.

For an indicator with no legacy impute route, dimension C is the assertion
that nothing is imputed.

## Float comparison

Exact equality, everywhere. Legacy and new run the same arithmetic in the
same order on the same inputs, so results are bit-identical; the BIODIV
formulas keep the legacy summation order for this reason. No tolerance is
used today.

GINIPT's regression fallback is the one place where the legacy arithmetic
ran inside a library (scikit-learn's `LinearRegression`, which centers the
data and calls LAPACK `gelsd`). The new backend performs the same steps
with `numpy.linalg.lstsq` and reproduces the legacy coefficient, intercept
and all predictions bit for bit on the committed fixture; the textbook
covariance-over-variance formula does not (it differs by one or two units
in the last place). The comparison is exact. Because the result comes from
LAPACK, a different BLAS/LAPACK build could in principle round differently;
if that ever happens the parity test will say so, and the remedy is to be
decided then, not pre-empted with a tolerance.

If a future indicator cannot be bit-identical, for example because the
legacy code used a library that orders a sum differently, use the tightest
tolerance that passes, set it at that one call site, and record here the
indicator, the tolerance and the cause. A tolerance must never be wide
enough to hide a different formula, goalpost or input.

## Checklist for a port

1. **Characterize** the legacy behaviour at the pinned commit: collect,
   clean, compute, impute, finalize; years, countries, units, goalposts.
2. **Identify methodology conflicts**: places where executable code,
   methodology text, static metadata or published scores disagree, and
   choices that are reproducible but questionable.
3. **Record conflicts** in [methodology-conflicts.md](methodology-conflicts.md)
   as `unresolved`. Implement the executable behaviour.
4. **Record source corrections** (wrong series code, value in the wrong
   field) in `src/sspi/metadata/data/PROVENANCE.yaml` under `edits`, and
   nowhere else. `scripts/import_legacy_metadata.py` reads its edits and
   additions from that file, so re-running it keeps every recorded
   correction; `tests/golden/test_metadata_importer.py` checks that a
   regeneration reproduces the checked-in metadata byte for byte.
5. **Commit a source fixture** and **generate golden files** from it in the
   legacy virtualenv: one observation file per dataset
   (`generate_unsdg_cases.py` for UN SDG datasets) and one score file per
   indicator.
6. **Register** the files in `tests/golden/parity.py` (`OBSERVATION_CASES`,
   `INDICATOR_CASES`) and add the rows to the register below.
7. **Write the parity tests** with `load_cases`, `score_records` and
   `assert_parity`, and run them offline.
8. **Confirm** observation parity, score parity, imputation parity and
   missingness parity. Run the full suite under `-W error`, with and without
   `SSPI_TEST_DATABASE_URL`.
9. Only then add the dataset to `SUPPORTED_DATASETS` and the indicator to the
   registry.

`tests/golden/test_migration_gate.py` enforces steps 6 and 9: a dataset that
is ingestible or an indicator that is executable without a registered golden
file from the pinned commit, or without a row in the register below, fails
the suite.

## Register of migrated items

`Conflicts` lists entry IDs in
[methodology-conflicts.md](methodology-conflicts.md), or `none known`.

### Datasets

| Dataset | Source fixture | Golden file | Parity test | Source corrections |
|---|---|---|---|---|
| UNSDG_MARINE | `tests/fixtures/unsdg/14_5_1_sample.json` | `unsdg_marine_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_TERRST | `tests/fixtures/unsdg/15_1_2_sample.json` | `unsdg_terrst_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_FRSHWT | `tests/fixtures/unsdg/15_1_2_sample.json` | `unsdg_frshwt_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_REDLST | `tests/fixtures/unsdg/15_5_1_sample.json` | `unsdg_redlst_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_STKHLM | `tests/fixtures/unsdg/12_4_1_sample.json` | `unsdg_stkhlm_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_MINMAT | `tests/fixtures/unsdg/12_4_1_sample.json` | `unsdg_minmat_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_MONTRL | `tests/fixtures/unsdg/12_4_1_sample.json` | `unsdg_montrl_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_BASELA | `tests/fixtures/unsdg/12_4_1_sample.json` | `unsdg_basela_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE |
| UNSDG_ROTDAM | `tests/fixtures/unsdg/12_4_1_sample.json` | `unsdg_rotdam_cases.json` | `test_golden_unsdg.py` | series code, in PROVENANCE; legacy Stockholm mapping kept, see CHMPOL-1 |
| UNSDG_WTSTRS | `tests/fixtures/unsdg/6_4_2_sample.json` | `unsdg_wtstrs_cases.json` | `test_golden_unsdg.py` | series code and `activity=TOTAL` dimension, in PROVENANCE |
| UNSDG_WUSEFF | `tests/fixtures/unsdg/6_4_1_sample.json` | `unsdg_wuseff_cases.json` | `test_golden_unsdg.py` | added to the catalog (PROVENANCE `additions`) |
| UNSDG_CWUEFF | `tests/fixtures/unsdg/6_4_1_sample.json` | `unsdg_cwueff_cases.json` | `test_golden_unsdg.py` | series code and dimension, in PROVENANCE; derived from UNSDG_WUSEFF in `sspi.ingestion.derived` |
| EPI_NITROG | `tests/fixtures/epi/epi2024indicators_P5_Indicator_SNM_ind_na.csv` | `epi_nitrog_cases.json` | `test_golden_nitrog.py` | edition archive (`query_code`), in PROVENANCE; fixture is the legacy 2024 archive's file, production reads the 2026 archive (NITROG-1) |
| UNFAO_FRSTLV | `tests/fixtures/fao/Inputs_LandUse_E_All_Data_(Normalized)_sample.csv` | `unfao_frstlv_cases.json` | `test_golden_fao_datasets.py` | none; bulk file read instead of the authenticated API, M49 geography (see below) |
| UNFAO_FRSTAV | `tests/fixtures/fao/Inputs_LandUse_E_All_Data_(Normalized)_sample.csv` | `unfao_frstav_cases.json` | `test_golden_fao_datasets.py` | unit label noted in PROVENANCE; derived from UNFAO_FRSTLV in `sspi.ingestion.derived` (1990s mean, 1990-2022, DEFRST-2) |
| UNFAO_CRBNLV | `tests/fixtures/fao/Inputs_LandUse_E_All_Data_(Normalized)_sample.csv` | `unfao_crbnlv_cases.json` | `test_golden_fao_datasets.py` | element code 7215 -> 72151, in PROVENANCE |
| UNFAO_CRBNAV | `tests/fixtures/fao/Inputs_LandUse_E_All_Data_(Normalized)_sample.csv` | `unfao_crbnav_cases.json` | `test_golden_fao_datasets.py` | element code and unit label, in PROVENANCE; derived from UNFAO_CRBNLV in `sspi.ingestion.derived` (1990s mean, every source year) |
| WID_NINCSH_PRETAX_P90P100 | `tests/fixtures/wid` | `wid_nincsh_pretax_p90p100_cases.json` | `test_golden_inequality_datasets.py` | series code (`sptincj992`) and `percentile` dimension, in PROVENANCE; legacy float32 value representation kept (see below) |
| WID_NINCSH_PRETAX_P0P50 | `tests/fixtures/wid` | `wid_nincsh_pretax_p0p50_cases.json` | `test_golden_inequality_datasets.py` | series code (`sptincj992`) and `percentile` dimension, in PROVENANCE; legacy float32 value representation kept (see below) |
| WB_GINIPT | `tests/fixtures/wb/SI.POV.GINI_sample.json` | `wb_ginipt_cases.json` | `test_golden_inequality_datasets.py` | none |
| ILO_EMPLOY_TO_POP | `tests/fixtures/ilo/DF_EMP_DWAP_SEX_AGE_RT_SEX_T_Y15-64.json` | `ilo_employ_to_pop_cases.json` | `test_golden_ilo_datasets.py` | series code (`DF_EMP_DWAP_SEX_AGE_RT`) and `SEX`/`AGE` dimensions, in PROVENANCE |
| ILO_COLBAR | `tests/fixtures/ilo/DF_ILR_CBCT_NOC_RT.json` | `ilo_colbar_cases.json` | `test_golden_ilo_datasets.py` | none |
| IEA_TLCOAL | `tests/fixtures/iea/TESbySource_sample.json` | `iea_tlcoal_cases.json` | `test_golden_altnrg.py` | `product=COAL` dimension, in PROVENANCE |
| IEA_NATGAS | `tests/fixtures/iea/TESbySource_sample.json` | `iea_natgas_cases.json` | `test_golden_altnrg.py` | `product=NATGAS` dimension, in PROVENANCE |
| IEA_NCLEAR | `tests/fixtures/iea/TESbySource_sample.json` | `iea_nclear_cases.json` | `test_golden_altnrg.py` | `product=NUCLEAR` dimension, in PROVENANCE |
| IEA_HYDROP | `tests/fixtures/iea/TESbySource_sample.json` | `iea_hydrop_cases.json` | `test_golden_altnrg.py` | `product=HYDRO` dimension, in PROVENANCE |
| IEA_GEOPWR | `tests/fixtures/iea/TESbySource_sample.json` | `iea_geopwr_cases.json` | `test_golden_altnrg.py` | `product=GEOTHERM` dimension, in PROVENANCE |
| IEA_BIOWAS | `tests/fixtures/iea/TESbySource_sample.json` | `iea_biowas_cases.json` | `test_golden_altnrg.py` | `product=COMRENEW` dimension, in PROVENANCE |
| IEA_FSLOIL | `tests/fixtures/iea/TESbySource_sample.json` | `iea_fsloil_cases.json` | `test_golden_altnrg.py` | `product=MTOTOIL` dimension, in PROVENANCE |
| UNSDG_NRGINT | `tests/fixtures/unsdg/7_3_1_sample.json` | `unsdg_nrgint_cases.json` | `test_golden_unsdg.py` | series code (`EG_EGY_PRIM`), in PROVENANCE |
| UNSDG_AIRPOL | `tests/fixtures/unsdg/11_6_2_sample.json` | `unsdg_airpol_cases.json` | `test_golden_unsdg.py` | series code (`EN_ATM_PM25`) and `location=ALLAREA` dimension, in PROVENANCE |
| UNFAO_BFPROD | `tests/fixtures/fao/FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv` | `unfao_bfprod_cases.json` | `test_golden_fao_datasets.py`, `test_golden_ghg_datasets.py` | element code 2510 -> 5511 and source note, in PROVENANCE; bulk file read instead of the authenticated API, M49 geography |
| UNFAO_BFCONS | `tests/fixtures/fao/FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv` | `unfao_bfcons_cases.json` | `test_golden_fao_datasets.py`, `test_golden_ghg_datasets.py` | published unit `kg/cap` (legacy label `kg/capita/year` kept) and source note, in PROVENANCE |
| WB_POPULN | `tests/fixtures/wb/SP.POP.TOTL_sample.json` | `wb_populn_cases.json` | `test_golden_ghg_datasets.py` | none |
| IEA_TCO2EM | `tests/fixtures/iea/CO2BySector_sample.json` | `iea_tco2em_cases.json` | `test_golden_ghg_datasets.py` | `seriesLabel=Transport Sector` dimension, published unit `MtCO2`, value multiplier 10^9 and source note, in PROVENANCE |
| EPI_MSWGEN | `tests/fixtures/epi/epi2024indicators_P5_Indicator_WPC_ind_na.csv` | `epi_mswgen_cases.json` | `test_golden_mswgen.py` | source note, in PROVENANCE; live source unavailable: not ingestible (see below) |
| WB_PUPTCH | `tests/fixtures/wb/SE.PRM.ENRL.TC.ZS_sample.json` | `wb_puptch_cases.json` | `test_golden_puptch.py` | series code and the cleaner's unit literal `Average`, in PROVENANCE |
| UIS_ENRPRI | `tests/fixtures/uis/NERT.1.CP_sample.json` | `uis_enrpri_cases.json` | `test_golden_enrollment.py` | series code, in PROVENANCE; UIS release recorded in provenance |
| UIS_ENRSEC | `tests/fixtures/uis/NERT.2.CP_sample.json` | `uis_enrsec_cases.json` | `test_golden_enrollment.py` | series code, in PROVENANCE; UIS release recorded in provenance |
| UIS_YRSEDU | `tests/fixtures/uis/YEARS.FC.COMP.1T3_sample.json` | `uis_yrsedu_cases.json` | `test_golden_yrsedu.py` | none; UIS release recorded in provenance; reported zeros dropped as in legacy (YRSEDU-1) |
| WB_TAXREV | `tests/fixtures/wb/GC.TAX.TOTL.GD.ZS_sample.json` | `wb_taxrev_cases.json` | `test_golden_taxrev.py` | series code and the cleaner's unit literal `% of GDP`, in PROVENANCE |
| WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50 | `tests/fixtures/wid` | `wid_nincsh_posttax_equalsplit_p0p50_cases.json` | `test_golden_txrdst.py` | series code (`sdiincj992`), `percentile` dimension and source note, in PROVENANCE; legacy float32 value representation kept |
| WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100 | `tests/fixtures/wid` | `wid_nincsh_posttax_equalsplit_p90p100_cases.json` | `test_golden_txrdst.py` | series code (`sdiincj992`), `percentile` dimension and source note, in PROVENANCE; legacy float32 value representation kept |
| TF_CRPTAX | `tests/fixtures/taxfoundation/rates_final_2025-01_sample.csv` | `tf_crptax_cases.json` | `test_golden_crptax.py` | edition-specific query code (`rates_final_2025-01`) and source note (edition, URL, SHA-256), in PROVENANCE |

### Indicators

| Indicator | Golden file | Parity tests | Imputes | Conflicts |
|---|---|---|---|---|
| BIODIV | `biodiv_imputation_cases.json` | `test_golden_biodiv_orchestration.py`, `test_golden_imputation.py` | yes | BIODIV-1, BIODIV-2, BIODIV-3, BIODIV-4, BIODIV-5 |
| REDLST | `redlst_cases.json` | `test_golden_redlst.py` | no | REDLST-1 |
| CHMPOL | `chmpol_cases.json` | `test_golden_chmpol.py` | no | CHMPOL-1, CHMPOL-2 |
| WATMAN | `watman_cases.json` | `test_golden_watman.py` | yes | WATMAN-1, WATMAN-2, WATMAN-3 |
| NITROG | `nitrog_cases.json` | `test_golden_nitrog.py` | no | NITROG-1 |
| DEFRST | `defrst_cases.json` | `test_golden_defrst.py` | yes | DEFRST-1, DEFRST-2, DEFRST-3 |
| CARBON | `carbon_cases.json` | `test_golden_carbon.py` | yes | CARBON-1, CARBON-2 |
| ISHRAT | `ishrat_cases.json` | `test_golden_ishrat.py` | no | none known |
| GINIPT | `ginipt_cases.json` | `test_golden_ginipt.py` | yes | GINIPT-1, GINIPT-2, GINIPT-3 |
| EMPLOY | `employ_cases.json` | `test_golden_worker_engagement.py` | yes | EMPLOY-1, EMPLOY-2 |
| COLBAR | `colbar_cases.json` | `test_golden_worker_engagement.py` | yes | COLBAR-1, COLBAR-2 |
| ALTNRG | `altnrg_cases.json` | `test_golden_altnrg.py` | yes | ALTNRG-1, ALTNRG-2 |
| NRGINT | `nrgint_cases.json` | `test_golden_energy.py` | yes | NRGINT-1 |
| AIRPOL | `airpol_cases.json` | `test_golden_energy.py` | yes | AIRPOL-1, AIRPOL-2 |
| BEEFMK | `beefmk_cases.json` | `test_golden_beefmk.py` | yes | BEEFMK-1, BEEFMK-2, BEEFMK-3 |
| COALPW | `coalpw_cases.json` | `test_golden_coalpw.py` | yes | COALPW-1 |
| GTRANS | `gtrans_cases.json` | `test_golden_gtrans.py` | yes | GTRANS-1 |
| MSWGEN | `mswgen_cases.json` | `test_golden_mswgen.py` | no | MSWGEN-1 |
| PUPTCH | `puptch_cases.json` | `test_golden_puptch.py` | yes | PUPTCH-1 |
| ENRPRI | `enrpri_cases.json` | `test_golden_enrollment.py` | yes | ENRPRI-1 |
| ENRSEC | `enrsec_cases.json` | `test_golden_enrollment.py` | yes | ENRSEC-1 |
| YRSEDU | `yrsedu_cases.json` | `test_golden_yrsedu.py` | yes | YRSEDU-1, YRSEDU-2 |
| TAXREV | `taxrev_cases.json` | `test_golden_taxrev.py` | yes | TAXREV-1, TAXREV-2, TAXREV-3 |
| TXRDST | `txrdst_cases.json` | `test_golden_txrdst.py` | no | TXRDST-1, TXRDST-2 |
| CRPTAX | `crptax_cases.json` | `test_golden_crptax.py` | yes | CRPTAX-1 |

GINIPT's golden file was generated from two fixtures,
`tests/fixtures/wb/SI.POV.GINI_sample.json` and `tests/fixtures/wid`: its
regression fallback is trained on the ISHRAT scores computed from the WID
fixture.

### How the FAO and EPI fixtures relate to the legacy source

The legacy FAO collector read the FAOSTAT JSON API with `area_cs=ISO3`;
that API now requires authentication. The committed fixture is a sample of
the official normalized bulk file (18 areas, items 6717 and 6646, every
element, as downloaded 2026-10-01; bulk file dated 2026-09-16).
`generate_fao_land_cases.py` presents each bulk row to the legacy cleaner
the way the API did: ISO3 where the area's M49 code is a country (the same
pycountry mapping the new adapter uses), the FAO area code otherwise, which
the legacy filter drops as it dropped the API's aggregate codes. Values are
passed as the bulk file's strings. Everything after that adaptation is the
legacy code. Geography decision (canonical M49): "China, mainland" (M49 156)
is CHN; FAO's broader "China" (M49 159), "Belgium-Luxembourg" (058) and the
regional aggregates are skipped and reported. The adaptation cannot know
which ISO3-style codes the API gave dissolved entities (USSR, Yugoslav SFR,
Sudan (former), ...), so it presents them with FAO's numeric code and both
sides drop them; the resulting difference on live data is recorded as
CARBON-2 and DEFRST-3, not hidden.

The legacy EPI collector read `epi2024indicators.zip`, whose URL now serves
an HTML page. The committed fixture is that archive's `SNM_ind_na.csv`,
recovered from the Internet Archive's capture of the legacy URL, so NITROG
parity is against the exact file the legacy backend processed. Production
ingestion reads the current 2026 archive; it is not parity evidence.

MSWGEN's fixture is the same archive's `WPC_ind_na.csv` (file SHA-256
`741d97b67a88f9b98b1aac2451e341aeb8a7cf012e9d134eabcf67fd456117c5`), committed
whole: 220 rows, 1995–2024, 6,210 values, 390 `NA` cells and 53 reported
zeros, which the legacy cleaner keeps. The 2026 archive has no `WPC` file,
so unlike NITROG there is no production edition to read (see below).

### How the WID and World Bank fixtures relate to the legacy source

Both fixtures are row subsets of the artifacts the legacy collectors read
(the WID bulk archive's per-country files and the World Bank API response),
so no adaptation is needed: `generate_inequality_cases.py` hands them to the
legacy cleaners as the raw documents the collectors stored.

The legacy WID cleaner parsed the value column as `float32` and serialized
it with pandas `to_json` (ten decimals), so a published `0.1921` is stored
as `0.1921000034`. The new adapter reproduces that number exactly
(`sspi.ingestion.wid.legacy_float32_value`; verified against pandas on every
row of two complete country files, 1,036,737 values) and keeps the published
text in provenance. It is a source-representation quirk kept for parity,
recorded in PROVENANCE.yaml, not a methodology.

`SE.PRM.ENRL.TC.ZS_sample.json`, the PUPTCH fixture, is a row subset of the
response of
`https://api.worldbank.org/v2/country/all/indicator/SE.PRM.ENRL.TC.ZS?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-08; 17,556 rows), in
the API shape, handed to the legacy cleaner by `generate_education_cases.py`.
It keeps every row of thirteen countries chosen for the cases they
exercise, plus three aggregates and Kosovo (see `tests/fixtures/wb/README.md`).
The legacy cleaner wrote the unit literal `Average`; canonical metadata now
records that literal (PROVENANCE). The source has no zero, so the shared
cleaner's zero drop is not exercised here; it is covered by the World Bank
adapter tests. Both legacy routes produce consistent output on it (no
identity both observed and imputed), and parity is exact for all 358
observations, 358 observed scores and 231 imputed scores.

### How the ILO fixtures relate to the legacy source

Both fixtures are complete, unmodified responses of the ILOSTAT SDMX API to
the two requests the legacy collectors sent (same dataflow, key and time
window), downloaded 2026-10-05. `generate_worker_engagement_cases.py` hands
each to the legacy cleaner as the raw document the collector stored, so the
legacy SDMX parsing (`parse_sdmx_json_to_tabular`) and filtering
(`filter_ilo`) run unchanged. The legacy cleaner keeps the ILO's own area
codes with no ISO check (it drops only codes containing a digit, the ILO's
aggregates), so `KOS` and `ANT` are stored as observations; the new adapter
does the same. The legacy impute routes write a different unit literal
(`Tax Rate`) from the compute routes; `SeriesFillThenScore.unit` reproduces
it (EMPLOY-2, COLBAR-2).

### How the Energy fixtures relate to the legacy source

`7_3_1_sample.json` and `11_6_2_sample.json` are verbatim rows of the UN SDG
PivotData responses of 2026-10-05, in source order, reduced to 19 and 14
countries plus three aggregates. The 11.6.2 sample keeps all five location
slices for four countries and World, so the `location=ALLAREA` selection is
exercised. `generate_energy_cases.py` runs the legacy cleaners and the
`compute_*` / `impute_*` routes on them. Because the AIRPOL sample holds 14
countries, the other 53 SSPI67 members receive the legacy reference-class
mean there (1,272 scores); on the full source every member has data and
none does.

The legacy reference-class mean adds the scores in the order MongoDB returns
them (source row order); the new backend adds them in country and year
order. The two sums are bit-identical on the committed sample. On other
data they could differ in the last bit; if that ever shows up it must be
reported, not absorbed by a tolerance.

### How the IEA fixture relates to the legacy source

The legacy collector sent one unauthenticated GET to
`https://api.iea.org/stats/indicator/TESbySource` and stored one raw
document per row. `TESbySource_sample.json` is a row subset of that
response as of 2026-10-05 (ten areas, see `tests/fixtures/iea/README.md`);
`generate_iea_cases.py` hands the rows to the seven legacy cleaners and then
runs `compute_altnrg` and `impute_altnrg`. The sample holds eight countries,
so the other 59 SSPI67 members are absent from all seven datasets there and
the legacy route scores them 0.0 from seven zero-filled inputs (1,416 of
the 1,518 imputed scores); on the full source every member is present.

The endpoint is the interface the pinned legacy backend used and was
reachable without authentication during migration. The IEA does not
document it as a stable public API: treat it as fragile. Replacing it with
another IEA product needs its own characterization and parity review. The
adapter (`sspi.ingestion.iea`) is keyed on the indicator name and on the
dataset's canonical `dimensions`, not on ALTNRG. COALPW reads the same
seven `TESbySource` datasets (same canonical observations, same fixture);
GTRANS reads IEA indicator `CO2BySector` through the same adapter (next
section).

### How the Greenhouse Gases fixtures relate to the legacy source

`generate_ghg_cases.py` runs the legacy cleaners and the `compute_*` /
`impute_*` routes of BEEFMK, COALPW and GTRANS on four fixtures:

- `TESbySource_sample.json`, the ALTNRG fixture, unchanged: COALPW's inputs
  are ALTNRG's. As for ALTNRG, the 59 SSPI67 members the sample omits are
  zero-filled in every dataset; COALPW scores that all-zero case 1.0
  (COALPW-1), so 1,416 of its 1,518 imputed scores are 1.0 here. On the full
  source no member is absent.
- `CO2BySector_sample.json`: verbatim rows of the response of 2026-10-08,
  the transport rows of eleven areas plus every sector for Austria (so the
  `seriesLabel` selection is exercised), with Pakistan's rows from 2020 on
  removed so the impute route's forward extrapolation has something to do;
  on the full source every series reaches 2024 and GTRANS imputes nothing.
  The legacy cleaner multiplied MtCO2 by 10^9 and wrote its own unit label;
  canonical metadata declares both (`source.published_unit`,
  `source.value_multiplier`, read by `sspi.ingestion.units`), so the
  adapter stays generic.
- `SP.POP.TOTL_sample.json`: a row subset of the World Bank response of
  2026-10-08 in the API's shape, as for `SI.POV.GINI`.
- `FoodBalanceSheets_E_All_Data_(Normalized)_sample.csv`: a row subset of
  the FAOSTAT Food Balances bulk file (domain FBS, CSV dated 2025-10-14,
  zip SHA-256 `26200855ed5da3d0805e34219124e241d0e0bc6959d0995ebc77a10dd84cbaf1`),
  presented to the legacy cleaners the way the Land generator does. The
  legacy API's element code for Production, 2510, is 5511 in the bulk file
  (PROVENANCE). The beef cleaners differ from the Land ones: they select on
  the element *name*, keep zeros, and the consumption cleaner writes the
  literal unit `kg/capita/year` (the bulk file says `kg/cap`). Pakistan's
  beef rows after 2020 are removed so BEEFMK's forward extrapolation is
  exercised.

All three legacy routes produce consistent output on these fixtures (no
identity both observed and imputed), so exact parity is required and holds
for every dataset and every score, observed and imputed. GTRANS's impute
route read back only 2000–2023; its groups still incomplete are compared
inside that window with the route's own scoring and outside it with the
compute route's.

### Historical parity only: live source unavailable

A dataset in `UNAVAILABLE_SOURCES` (`src/sspi/ingestion/runner.py`) has
committed observation parity evidence like any other, but its legacy source
can no longer be fetched and no replacement source is approved. It is never
in `SUPPORTED_DATASETS`; `sspi.ingest()` refuses it with
`SourceUnavailableError` (a `NotIngestibleError`) and the recorded reason,
before any network or database use. The gate requires observation parity for
exactly `SUPPORTED_DATASETS` plus `UNAVAILABLE_SOURCES`, never both. An
indicator reading such a dataset is registered and executable with exact
score parity, but a researcher cannot populate its input from a source, so
it is not part of any runnable workflow.

| Dataset | Indicators | Why there is no live source |
|---|---|---|
| `EPI_MSWGEN` | `MSWGEN` | The legacy collector read series `WPC` from `https://epi.yale.edu/downloads/epi2024indicators.zip`, which now serves an HTML page. The current edition (`epi2026_indicators_na_2026-08-31.zip`) publishes no `WPC` file; its nearest waste file, `SMW` ("Sustainably managed solid waste", a proportion), is a different indicator. Not substituted: not `SMW`, not What a Waste, not another waste-per-capita source, not the Internet Archive capture. |

Status: MSWGEN, executable methodology characterized, historical parity
complete, live source unavailable.

### Waste indicators not ported

The executable Waste category at the pinned commit is MSWGEN, RECYCL and
STCONS (`methodology/sus/wst/methodology.md`, canonical `category_code: WST`).
EWASTE belongs to the 2018 static SSPI only: at the pinned commit it has no
route, dataset definition or methodology file, and it is not in the catalog.
It is not ported and has no alias.

**RECYCL: source decision pending.** The legacy route scores
`goalpost(WB_RECYCL, 0, 100)` and extrapolates scores to 2000–2023 with an
SSPI67 reference-class average (the `ExtrapolateScores` shape of NRGINT and
AIRPOL), but `WB_RECYCL` has no collector or cleaner at the pinned commit
(`query_code: null`), so the legacy backend produced no RECYCL scores and
there is no executable output to compare with. The historical source is the
What a Waste 2.0 country file (`country_level_data.csv`, World Bank data
catalog dataset 0039597, resource DR0049199), field
`waste_treatment_recycling_percent`: the 2018 static `RECYCL_RAW` equals it
exactly for all 45 of 49 countries that have a value (the other four are the
static file's income-group means of the 49, 26.82 and 11.22). The current
catalog lists only What a Waste 3.0 (`What_a_Waste_3.0_COUNTRY_Dataset_&_Codebook.xlsx`,
resource DR0095901, CC BY 4.0; also Data360 `WB_WAW` / `WM_MSW_TREAT`).
Its `waste_treatment_recycling_percent` is not demonstrably the same
measure:

- unit: 3.0 stores a fraction (0–1) under a "% weight MSW generated" label;
  2.0 stored a percentage (0–100);
- definition: in 2.0 the United States' 34.6 is the EPA's recycling *plus
  composting* rate; 3.0 reports recycling 24.1 and composting 8.8
  separately (2018). Elsewhere 3.0 appears to fold composting into
  recycling: Austria 25.66 (+31.24 composting) in 2.0, 51.47 with no
  composting value in 3.0; Canada 20.59 (+4.08) vs 35.52;
- values: of the 102 countries with a value in both files, 79 differ by more
  than 0.5 points and 11 are unchanged (36 of the 42 static-2018 countries
  with both differ), for example Iceland 55.81 -> 20.70, South Africa 28.00 -> 8.37,
  Korea 58.00 -> 38.43, Saudi Arabia 15.00 -> 3.73;
- years: 3.0 records a measurement year per country (2018–2023); the 2.0
  file has none, and 3.0 does not retain the 2.0 values.

What a Waste 2.0's file is still served at its old address but is no longer
listed, and it is a one-off snapshot with no year. A decision on the source
and its definition is needed before RECYCL can be ported.

**STCONS: blocked on a new source organization.**
`goalpost(FPI_ECOFPT_PER_CAP * WID_CARBON_TOT_P90P100 / WID_CARBON_TOT_P0P100, 30, 1.6)`.
The two WID datasets (`lpfghgi999`, `p90p100` and `p0p100`, SSPI67, 2000–2024)
fit the existing WID adapter, and the impute route is the BIODIV shape
(`ImputeInputsThenScore`, 2000–2023, SSPI67). `FPI_ECOFPT_PER_CAP` is the
Global Footprint Network's `EFCpc`, collected from
`https://api.footprintnetwork.org/v1/data/all/{year}/EFCpc` with HTTP basic
authentication (a named account and `SSPI_FPI_API_KEY`); the API returns
403 without credentials. A source and access decision is needed first.

### How the Tax fixtures relate to the legacy source

The executable Tax category at the pinned commit is CRPTAX, TAXREV and
TXRDST (`methodology/ms/tax/methodology.md`, canonical `category_code: TAX`).
All three are ported with exact parity: the Tax category is complete at the
leaf-indicator level only. No Tax category score is computed.

`GC.TAX.TOTL.GD.ZS_sample.json`, the TAXREV fixture, is a row subset of the
response of
`https://api.worldbank.org/v2/country/all/indicator/GC.TAX.TOTL.GD.ZS?format=json&per_page=20000`
(source 2, last updated 2026-10-08, downloaded 2026-10-09; 17,556 rows,
SHA-256 of the full response
`bd749f9aa4874cf8222800556b7f25dcb2831483ded6fe62bcd0715d2f48f0be`), in the
API shape, with `per_page` and `total` set to the number of rows kept. It
keeps every row, 1960-2025, of Malaysia, Austria and the United States;
Japan (last value 1993: thirty years of forward extrapolation); India (a
2019-2021 gap) and Indonesia (a 2000 and a 2005-2007 gap, last value 2009);
Greece; Kuwait (a 1975-1976 gap, last value 1998); the United Arab Emirates
(the smallest values, near the lower goalpost); Timor-Leste and Sudan (values
above 100 % of GDP, clamped by the upper goalpost, and pulled into the
reference-class mean); Andorra (first value 2018); Vietnam, Nigeria,
Venezuela and Algeria (no value: the hard-coded reference-class recipients);
Pakistan (no value and not a recipient: no score, TAXREV-2); and the
aggregates World, European Union and High income (empty `countryiso3code`,
id `XD`) and Kosovo, which the cleaner skips: 1,386 rows, 473 with a value.
The source has no zero and no negative value. Parity is exact: 339
observations (783 empty values dropped), 339 observed and 235 imputed
scores, among them 96 reference-class rows at the fixture's all-rows mean
(19.1236). The legacy impute route raised on an empty dataset; the golden
file records that and the new strategy raises too.

TXRDST reads the two pre-tax WID shares ISHRAT already uses and two post-tax
shares (`sdiincj992`, post-tax national income, equal-split adults 20+,
percentiles `p0p50` and `p90p100`), through the same WID adapter and the same
single archive fetch. The WID fixture now also keeps the `sdiincj992` rows
(`p0p50`, `p90p100` and the decoy `p99p100`, years from 1998) and the
`sdiincj992` metadata row of each country, from the same archive edition
(last modified 2026-09-09); every row already in the fixture is unchanged
and the pre-tax golden files are untouched (`generate_tax_cases.py`
re-cleans them from the extended fixture and asserts they are identical).
Every SSPI67 member has all four shares for 2000-2024, so legacy TXRDST
scores 1,650 identities with no incomplete group; a golden variant with five
clean rows removed (`with_rows_removed`) gives the legacy incomplete groups
(four identities). Legacy TXRDST has no impute route. Its score function is a
closure inside `compute_txrdst`; the generator records the function the
route passed to `score_indicator` and evaluates it on synthetic shares (a
zero pre-tax bottom share scores `goalpost(0, -10, 100)` with a warning; a
zero top share raises `ZeroDivisionError`; the goalpost boundaries), and the
new function must give the same result or raise the same error.

**CRPTAX.** `goalpost(TF_CRPTAX, 0, 40)` (higher rate, higher score), unit
"Tax Rate" in both routes; the impute route extrapolates backward to 2000,
then interpolates interior gaps (any year), with no forward extrapolation
and no reference class (`SeriesFillThenScore` with
`steps=("backward", "interpolate")`). `TF_CRPTAX` is the Tax Foundation's
worldwide corporate tax rate file, January 2025 edition (approved
2026-10-09: exactly this edition, no newer one): the combined (central plus
average subnational) statutory corporate income tax rate in percent,
1980-2024, one wide CSV (`iso_3` × year) at
`https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv`, the
legacy collector's literal URL. The Tax Foundation has no API; the general
adapter `sspi.ingestion.taxfoundation` reads configured edition files
(`FILES`: canonical `query_code` `rates_final_2025-01` -> edition, URL,
SHA-256) and refuses a download whose content differs, with no fallback.

The file is established exactly: the address still serves it (HTTP 200,
`text/csv`, 45,749 bytes, CRLF line endings, SHA-256
`7dd8f506e2942c816e28f01c7c478402fb39d3c263cf6c38b32f04df3fab9f52`), and it
is byte-identical to the Internet Archive's captures of 2025-01-17 and
2025-05-28 (same SHA-1 digest `JLDGQRPGPDEK5HNORPE6WZFNLNU74XJK`); the
legacy collector was written in February 2025. The legacy cleaner and the
new adapter give the same 7,205 observations (226 areas, 4,090 `NA` cells
dropped) on the whole file. The legacy collector's `requests` decoded it as
ISO-8859-1 (the server sends no charset) and the adapter as UTF-8; the file
is pure ASCII, so both read the same text.

Licence: the file is Tax Foundation work ("Corporate Tax Rates Around the
World, 2024", Cristina Enache), licensed under CC BY-NC 4.0 by the
publisher's site-wide copyright notice; neither the file, its publication
page nor its GitHub repository states otherwise (checked 2026-10-09).
Attribution, the licence link and the note that commercial use or
redistribution may require the publisher's permission are in
`tests/fixtures/taxfoundation/README.md`.

The complete file is committed as `rates_final_2025-01.csv`, so the pin is
tested against bytes offline (`tests/unit/test_taxfoundation_pin.py`): its
size and SHA-256 are compared with values recorded in that test and its
SHA-1 with the Internet Archive's digest, independently of the adapter's
`FILES` constant; the default client must accept exactly those bytes and
refuse a one-byte change, changed line endings or a missing final newline;
and the parity excerpt must be a verbatim, in-order excerpt whose
observations equal the full file's for the same areas.

`rates_final_2025-01_sample.csv` is a verbatim subset of that file (header
and 21 rows, CRLF kept; `.gitattributes` marks it `-text`): Malaysia,
Austria, the United States; Germany, Canada, Switzerland and Japan, whose
2018 static values are central-government rates (CRPTAX-1); the United
Arab Emirates (0 % until 2022, then 9 %), Bahrain (0 % every year) and
Jersey (zeros and a 1999 gap); Niue, the Comoros and Kosovo (first values
2020, 2015 and 2014: backward extrapolation); South Africa and Kuwait
(interior gaps in the 1990s); the Netherlands Antilles (ends 2009, gaps;
not an ISO code, kept); Namibia (its `iso_2` is the string `NA`); Iran
(75 %) and Saudi Arabia (45 %), above the upper goalpost, and Singapore
(exactly 40 % in 1980); North Korea (every cell `NA`). The generator runs
the legacy collector with `requests.get` answering from the fixture, then
the registered cleaner and both routes. Parity is exact: 731 observations
(214 `NA` cells), 731 observed and 69 imputed scores (49 backward
extrapolations, 20 interpolations), no identity both observed and imputed.
With no data the legacy routes score nothing and do not raise; neither does
the new strategy. The 2018 static values are recorded as evidence in
CRPTAX-1, never used as the expected result.

### How the UIS fixtures relate to the legacy source

The legacy collector (`api/datasource/uis.py`, `collect_uis_data`) made one
GET of `https://api.uis.unesco.org/api/public/data/indicators?indicator=<code>`
with no key, no paging and no release, and stored every element of the
response's `records` list as one raw document. `UISClient` makes the same
request with the release named (see below). The fixtures are verbatim
subsets of those responses, in API order, read 2026-10-09 from release
`20260507-91260335` ("February 2026 Data Release"; byte-identical with and
without the release named):

- `NERT.1.CP_sample.json` (full response 4,898 records, SHA-256
  `a878fc726dc5f8d33bb132b3ecf6e8619643412b73ecdf8703ac649a832e391b`):
  every record of Malaysia, Austria, the United States, China (last value
  1997), Nigeria (a 2010-2023 gap), Argentina and Guadeloupe (values of 100),
  Brazil (first value 2012), North Korea (one value), Afghanistan (last
  value 1993) and Benin (low values): 179 records;
- `NERT.2.CP_sample.json` (full response 3,298 records, SHA-256
  `409aee949c56909c82f1a58297651988704757fc1afc8612b8100dcf5f150014`):
  every record of Malaysia, Austria, the United States, Uruguay (100),
  Afghanistan (one value, 1974), Australia (first value 2013), Benin,
  Tunisia (last value 1985) and Brazil: 120 records. China and Nigeria
  have no record, as in the full response;
- `YEARS.FC.COMP.1T3_sample.json` (full response 5,894 records, SHA-256
  `25c4a3e54a5d14febf709a86a7eb601928d98670c3877d356e1ced7dbd2f8de2`):
  every record of Malaysia, Austria, the United States, Indonesia, India,
  Nigeria and Oman (each reports 0 years before its first compulsory
  schooling law), St Helena (one value, then zeros), Albania (no record for
  2018-2020), Saudi Arabia (first record 2004), North Korea (from 1975),
  Venezuela (the series' one `UIS_EST` record), Germany (13 years) and
  Bangladesh (5 years): 388 records, 52 of them 0;
- `versions_default.json`: the `/versions/default` answer naming that release.

`generate_education_cases.py` hands the records to the legacy cleaners as
the raw documents the collector stored. UIS serves national areas only, all
ISO3, and has no zero or null value in these series, so no area is skipped
and no value dropped here; the adapter tests cover both. Both legacy routes
produce consistent output on the fixtures (no identity both observed and
imputed), and parity is exact for every observation and every observed and
imputed score, including ENRSEC's China and Nigeria rows (the mean of the
fixture's 120 rows, 90.2529, for 2000-2023).

YRSEDU differs from the enrolment series in one way that matters: its
zeros are real values. UIS reports 0 years, with magnitude `NIL`, where a
country had no compulsory schooling in law (564 records of 5,894 in the
full series, among them Malaysia, Indonesia, India, Nigeria and Singapore).
The shared legacy cleaner drops every falsy value, and the YRSEDU impute
route only extrapolates backward to 2000, so the years before a law take
the first later value (India 2000-2008: 8 years, 0.333, instead of 0), a 0
before 2000 leaves no score, and a 0 after an earlier value leaves no score
at all (St Helena). That is reproduced exactly and recorded as YRSEDU-1. On
the fixture: 336 observations (52 zeros dropped), 336 observed and 37
imputed scores, every one exact.

**Releases.** The API serves a versioned database
(`/api/public/versions`); its data endpoint takes a documented `version`
parameter and otherwise reads the current default release. The legacy
request named none. By default the new client asks for the default release
first (`/versions/default`) and then names it in the data request, so the
release recorded on every observation (`provenance["source_version"]`) is
the one the data came from; `UISClient(version=...)` reads a specific
release. Production is not pinned. A new UIS release can revise past
values, and so change scores although the methodology is unchanged; the
parity evidence does not move, since it is held on the committed fixtures.

**Carried values.** ENRPRI and ENRSEC, like PUPTCH, carry each country's
last observation forward to 2023 with no limit on distance (China's primary
rate is carried from 1997 to 2023, 26 years). That is the legacy
methodology and is preserved; the input provenance of every carried score
names its anchor year and distance.

## Intentional divergences

The parity rule has one qualified exception. Where the pinned legacy route
itself cannot produce a result on the committed fixture (it raises), the
golden file records the failure (`legacy_impute_error`) and the new backend
may apply a replacement policy **that has been approved**. Such a case is
registered in `INTENTIONAL_DIVERGENCES` in `tests/golden/parity.py`, keyed
by indicator and variant, pointing at the `methodology-conflicts.md` entry
that states the literal legacy behaviour, why it fails, the magnitude of the
difference and the adopted policy. The gate checks that every recorded
legacy failure is registered, that every registration corresponds to one,
and that the cited entry states an implementation policy. A registered
divergence is not parity and is never described as such; exact parity is
still required on every variant the legacy route completes consistently.

| Indicator | Variant | Conflict | Legacy failure | Approved policy |
|---|---|---|---|---|
| `WATMAN` | `fixture_as_committed` | WATMAN-3 | raises: duplicate CWUEFF rows for Singapore | canonical CWUEFF first; reference-class fallback only when none exists (approved for WATMAN only) |

## Pending methodology decisions

A different situation: the legacy route completes but its output holds more
than one score for one identity (`legacy_output_conflicts` in the golden
file: identities both observed and imputed, or imputed twice), which one row
per identity cannot store, and **no replacement methodology has been
approved**. Nothing is selected. The new backend raises `ImputationError`
naming the conflict entry and writes nothing; the entry lays out the options
for the methodology team ("Potential direction A/B") without adopting one.
Such a case is registered in `PENDING_METHODOLOGY_DECISIONS`, never in
`INTENTIONAL_DIVERGENCES`; the gate checks the registration, that the entry
is unresolved, states the options and claims no adopted policy, and the
indicator's golden test proves the raise. Exact parity is required on the
fixture variant without the conflict.

No variant is pending today.

## Resolved methodology decisions

When the methodology team decides such a case, the variant moves from
`PENDING_METHODOLOGY_DECISIONS` to `RESOLVED_METHODOLOGY_DECISIONS` in
`tests/golden/parity.py`. The cited entry must be `resolved` with a
`Resolution evidence:` section.

The indicator's golden test derives the expected result from the legacy
output itself. It applies the decided rule, which keeps for each identity
the one legacy row the rule selects, and requires exact equality. No
expected value comes from anywhere but the legacy output. Exact parity on
the variant without the conflict is still required.

| Indicator | Variant | Conflict | Legacy behaviour | Decided rule | Expected result | Parity variant |
|---|---|---|---|---|---|---|
| `DEFRST` | `fixture_as_committed` | DEFRST-1 | stores observed and imputed scores for ARE 2000–2022 and two imputed scores for ARE 2023 | direction B: a listed country with observed scores is not a reference-class recipient | legacy output minus ARE's 24 reference-class rows (207 observed, 57 imputed) | `without_are_source_rows` |
| `CARBON` | `fixture_as_committed` | CARBON-1 | stores observed and imputed scores for KWT 2000–2023 | direction B: a listed country with observed scores receives no imputed inputs | legacy output minus KWT's 24 imputed rows (309 observed, 48 imputed) | `without_kwt_source_rows` |

The parity variants are the committed fixture with that recipient's level
rows removed, the source state the hard-coded recipient lists were written
against. On them the decided rule and the legacy routes coincide, and exact
parity holds on every dimension.

## Imputation strategies

An indicator's legacy impute route is an `ImputationStrategy`
(`sspi.indicators.strategy`): a pure object that declares the auxiliary
datasets and the country group it needs, and turns the observed pass into
imputed scores. The runner is indicator-agnostic. Strategies in use:
`ImputeInputsThenScore` (BIODIV), `WatmanImputation` (WATMAN),
`CarbonImputation` (CARBON, input-level: reference-class means of both
inputs), `DefrstImputation` (DEFRST, score-level: forward extrapolation of
scores and reference-class mean of scores, via `extrapolate_scores_forward`
and `reference_class_average_scores`), `GiniptImputation` (GINIPT: series
fill of the inputs, then a score-level regression on another indicator's
scores via `regression_impute_scores`), `SeriesFillThenScore` (EMPLOY,
COLBAR, PUPTCH, ENRPRI, YRSEDU, CRPTAX: forward, backward and interpolated fill of the one
input, or the steps the legacy route used (YRSEDU backward only, CRPTAX backward then
interpolated), no reference class; with `listed_recipients`, ENRSEC and TAXREV: the
same fill, then the all-rows mean for a hard-coded list, a listed country
with observed rows stopping the run), `ExtrapolateScores` (NRGINT: latest score carried forward;
AIRPOL: earliest score carried backward as well, and the mean of all
observed scores for group members with none, via
`extrapolate_scores_backward`, `extrapolate_scores_forward` and
`reference_class_average_scores`), `ConstantFillInputsThenScore` (ALTNRG
and COALPW: per dataset, zero for group members with no row, then backward,
forward and interpolated fill of the series present, scored with the
impute-route formula), `ExtrapolateScores` with `listed_recipients`
(BEEFMK: scores carried back to 2000 and forward to 2023, and the
reference-class mean for a hard-coded list; a listed country with observed
scores stops the run, since no precedence is decided),
`ExtrapolateInputsForwardThenScore` (GTRANS: within 2000–2023, one input
carried forward to 2023 and scored with the other inputs as they are);
`None` for REDLST, CHMPOL, NITROG, ISHRAT, MSWGEN and TXRDST.
A score imputed at score level carries its own `IndicatorScore.provenance`
(`imputed`, `imputation_method`, `source_year` / `reference_score_count`,
`imputation_distance`), persisted in `indicator_score.provenance` (migration
0003); the `imputed` flag is derived from that provenance or from an imputed
input, never supplied. An extrapolated score keeps the anchor year's inputs;
no observation is fabricated. A definition may also carry an
`observation_filter`, the legacy compute route's pre-selection of rows
(DEFRST and CARBON keep level rows from 2000); the strategy still sees every
canonical row, as the legacy impute routes did.

An imputation procedure that reads another indicator's scores declares that
indicator in `IndicatorDefinition.score_dependencies` (GINIPT declares
ISHRAT). The runner loads the dependency's persisted scores and passes them
to the strategy as `context.dependency_scores`; it never runs the
dependency. If the dependency has no scores, the run raises
`ScoreDependencyError` and writes nothing. There is no freshness tracking:
rerun the dependent indicator after rerunning its dependency.

Parity dimension C for an indicator with a strategy therefore compares the
imputed scores, their inputs' imputation fields, the identities and the
groups still incomplete, as the BIODIV and WATMAN golden tests do. Where the
legacy route itself fails on the committed fixture (WATMAN-3), the golden
file records the failure, a fixture variant on which the route runs supplies
the exact parity, and the current-source behaviour is a registered
intentional divergence (previous section).

## Lessons from the Land ports

- A legacy cleaner can do more than select a series. Check for `filter_sdg`
  keyword filters (now `source.dimensions`) and for arithmetic after the
  filter (now a `Derivation` in `sspi.ingestion.derived`), and let the
  golden file come from the cleaner function, not from re-applied helpers.
- A legacy source identifier can be wrong on purpose (CHMPOL-1). When the
  cleaner and the documentation disagree, the port reproduces the cleaner
  and the disagreement goes to `methodology-conflicts.md`, not to a quiet
  correction in `PROVENANCE.yaml`.
- Source values can be the string `"NaN"` (6.4.1). The legacy extractor
  dropped them as missing; the normalizer now does the same.
- Run the legacy impute route itself when generating evidence
  (`generate_watman_cases.py` unwraps the view function and stubs its
  collections). It can reveal that the route no longer runs on current data,
  which a re-implementation would hide.
- A legacy route can run and still produce output that one row per identity
  cannot hold (DEFRST and CARBON on current data: hard-coded recipients that
  now have source rows). Record the conflicting identities in the golden
  file, register the variant as a pending methodology decision, raise, and
  do not pick a precedence quietly; a policy approved for one indicator
  (WATMAN-3) is not approval for another. Once the team decides (DEFRST-1
  and CARBON-1, 2026-10-08), move the variant to the resolved register and
  hold the decided result exactly against the legacy output.
- When the legacy source is gone, look for the exact artifact first (the 2024
  EPI archive was recoverable from the Internet Archive) before building a
  fixture from a different vintage; a different vintage is validation, not
  parity.
- Golden files for score-level imputation need the score's own imputation
  fields (`score_level_records` in `tests/golden/parity.py`), not only its
  inputs'.

## Known limits of the current evidence

- Fixtures are subsets of the source: five countries plus two regional
  aggregates per UN SDG query; 18 areas for the FAO bulk sample (the seven
  usual countries, the six hard-coded DEFRST/CARBON recipients, China twice,
  Belgium-Luxembourg, two aggregates, Nicaragua for empty values, Greenland
  for zero values). The EPI fixture is the complete 2024 SNM file. They
  prove the implementations agree on those rows, including missing values,
  skipped areas and a country with no marine series. They do not exercise
  every country.
- BIODIV has a second variant with Malaysia's marine series thinned, so that
  interpolation and extrapolation are exercised inside the indicator.
  The UN data itself has no gaps of that kind today.
- Parity covers cleaning, imputation and scoring. Legacy finalization and
  aggregation are not migrated and not compared.
- Legacy stored incomplete groups in their own collection. The new backend
  returns the same identities from a run (`IndicatorRun.unscored`) and the
  parity tests compare them, but does not store them yet.
