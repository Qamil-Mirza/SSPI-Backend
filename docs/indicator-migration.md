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
| UNSDG_BENFTS_UNEMP | `tests/fixtures/unsdg/1_3_1_sample.json` | `unsdg_benfts_unemp_cases.json` | `test_golden_unsdg.py`, `test_golden_unempb.py` | series code (`SI_COV_UEMP`) and `sex=BOTHSEX` dimension, in PROVENANCE |
| ILO_FATINJ | `tests/fixtures/ilo/DF_SDG_F881_SEX_MIG_RT.json` | `ilo_fatinj_cases.json` | `test_golden_fatinj.py` | `SEX`/`MIG` dimensions, in PROVENANCE |
| UNSDG_CSTUNT | `tests/fixtures/unsdg/2_2_1_sample.json` | `unsdg_cstunt_cases.json` | `test_golden_unsdg.py`, `test_golden_cstunt.py` | series code (`SH_STA_STNT`) and `sex=BOTHSEX`, `age=<5Y` dimensions, in PROVENANCE |
| WB_GDP_PERCAP_CURPRICE_USD | `tests/fixtures/wb/NY.GDP.PCAP.CD_sample.json` | `wb_gdp_percap_curprice_usd_cases.json` | `test_golden_cstunt.py` | imported as a PROVENANCE addition (CSTUNT's regression predictor), series code `NY.GDP.PCAP.CD` |
| WHO_ATBRTH | `tests/fixtures/who/MDG_0000000025_synthetic.json` (synthetic; real data opt-in, GOV-1) | `who_atbrth_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | series code (`MDG_0000000025`), in PROVENANCE |
| WHO_DPTCOV | `tests/fixtures/who/WHS4_100_synthetic.json` (synthetic; real data opt-in, GOV-1) | `who_dptcov_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | series code (`WHS4_100`), in PROVENANCE |
| WHO_PHYSPC | `tests/fixtures/who/HWF_0001_synthetic.json` (synthetic; real data opt-in, GOV-1) | `who_physpc_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | series code (`HWF_0001`), in PROVENANCE |
| WB_CREDIT | `tests/fixtures/wb/FS.AST.PRVT.GD.ZS_sample.json` | `wb_credit_cases.json` | `test_golden_fdepth.py` | none |
| WB_DPOSIT | `tests/fixtures/wb/GFDD.OI.02_sample.json` | `wb_dposit_cases.json` | `test_golden_fdepth.py` | none (the series is bank deposits, the name says financial-system deposits: FDEPTH-3, a methodology question) |
| WB_PUBACC | `tests/fixtures/wb/FX.OWN.TOTL.ZS_sample.json` | `wb_pubacc_cases.json` | `test_golden_pubacc.py` | the cleaner's unit literal `Percent`, in PROVENANCE |
| WB_SANSRV | `tests/fixtures/wb/SH.STA.BASS.ZS_sample.json` | `wb_sansrv_cases.json` | `test_golden_sansrv.py` | series code (`SH.STA.BASS.ZS`), in PROVENANCE |
| WB_DRKWAT | `tests/fixtures/wb/SH.H2O.SMDW.ZS_sample.json` | `wb_drkwat_cases.json` | `test_golden_drkwat.py` | series code (`SH.H2O.SMDW.ZS`), in PROVENANCE |
| WB_AVELEC | `tests/fixtures/wb/EG.ELC.ACCS.ZS_sample.json` | `wb_avelec_cases.json` | `test_golden_wef.py`; full response: `test_golden_wef_real_data.py` (opt-in) | series code (`EG.ELC.ACCS.ZS`), in PROVENANCE |
| WEF_QUELEC | `tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx` (synthetic; original workbook opt-in, GOV-2) | `wef_quelec_synthetic_cases.json` | `test_golden_wef.py`; original workbook: `test_golden_wef_real_data.py` (opt-in) | query code = the pinned workbook, series code, `Attribute 1: Value`, source note, in PROVENANCE |
| WB_MURDER | `tests/fixtures/wb/VC.IHR.PSRC.P5_sample.json` | `wb_murder_cases.json` | `test_golden_murder.py` | series code (`VC.IHR.PSRC.P5`) and the cleaner's unit literal `Per 100,000 people`, in PROVENANCE |
| ITU_CYBSEC | `tests/fixtures/itu/gci-local-indicator-summary_synthetic.csv` (synthetic; original transcription opt-in, GOV-4) | `itu_cybsec_synthetic_cases.json` | `test_golden_cybsec.py`; original transcription: `test_golden_public_safety_real_data.py` (opt-in) | query code = the local file key, series code `GCI`, the cleaner's unit literal `Percentage`, source note, in PROVENANCE; approved name correction (CYBSEC-1) |
| UNODC_PRIPOP | `tests/fixtures/unodc/data_cts_prisons_and_prisoners_synthetic.xlsx` (synthetic; original workbook opt-in, GOV-3) | `unodc_pripop_synthetic_cases.json` | `test_golden_prison.py`; original workbook: `test_golden_public_safety_real_data.py` (opt-in) | query code = the pinned release, series `Persons held`, five dimension filters, source note, in PROVENANCE |
| FSI_SECAPP | `tests/fixtures/fsi/fsi-2018_synthetic.xlsx`, `tests/fixtures/fsi/fsi-2021_synthetic.xlsx`, `tests/fixtures/fsi/fsi-2023_synthetic.xlsx` (synthetic; the 18 original workbooks opt-in, GOV-5) | `fsi_secapp_synthetic_cases.json` | `test_golden_secapp.py`; original workbooks: `test_golden_public_safety_real_data.py` (opt-in) | query code = the pinned edition set, series = column `C1: Security Apparatus`, unit `Index`, source note, in PROVENANCE; approved name repair (SECAPP-1) |
| VDEM_RULELW | `tests/fixtures/vdem/V-Dem-CY-FullOthers_csv_v13_synthetic.zip` (synthetic; original v13 archive opt-in, GOV-6) | `vdem_rulelw_synthetic_cases.json` | `test_golden_rights.py`; original archive: `test_golden_rights_real_data.py` (opt-in) | series = column `v2x_rule`, source note, in PROVENANCE |
| VDEM_EDEMOC | `tests/fixtures/vdem/V-Dem-CY-FullOthers_csv_v13_synthetic.zip` (synthetic; original v13 archive opt-in, GOV-6) | `vdem_edemoc_synthetic_cases.json` | `test_golden_rights.py`; original archive: `test_golden_rights_real_data.py` (opt-in) | series = column `v2x_polyarchy`, source note, in PROVENANCE |
| SIPRI_ARMEXP | `tests/fixtures/sipri/armstransfers_synthetic.json` (synthetic; original answer opt-in, GOV-7) | `sipri_armexp_corrected_synthetic_cases.json` (approved name table, ARMEXP-4; untouched legacy rows: `sipri_armexp_synthetic_cases.json`) | `test_golden_global_role.py`; original answer: `test_golden_global_role_real_data.py` (opt-in) | source note (the request and the TIV) in PROVENANCE |
| UNSDG_RDPGDP | `tests/fixtures/unsdg/9_5_1_sample.json` | `unsdg_rdpgdp_cases.json` | `test_golden_unsdg.py` | series code `GB_XPD_RSDV`, in PROVENANCE |
| UNSDG_NRSRCH | `tests/fixtures/unsdg/9_5_2_sample.json` | `unsdg_nrsrch_cases.json` | `test_golden_unsdg.py` | series code `GB_POP_SCIERD`, in PROVENANCE |

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
| UNEMPB | `unempb_cases.json` | `test_golden_unempb.py` | yes | UNEMPB-1, UNEMPB-2, UNEMPB-3 |
| FATINJ | `fatinj_cases.json` | `test_golden_fatinj.py` | no | FATINJ-1, FATINJ-2 |
| CSTUNT | `cstunt_cases.json` | `test_golden_cstunt.py` | yes | CSTUNT-1, CSTUNT-2, CSTUNT-3 |
| ATBRTH | `atbrth_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | yes | ATBRTH-1 |
| DPTCOV | `dptcov_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | no | DPTCOV-1 |
| PHYSPC | `physpc_synthetic_cases.json` | `test_golden_who.py`; real data: `test_golden_who_real_data.py` (opt-in) | yes | PHYSPC-1 |
| FDEPTH | `fdepth_cases.json` | `test_golden_fdepth.py` | no | FDEPTH-1, FDEPTH-2, FDEPTH-3 |
| PUBACC | `pubacc_cases.json` | `test_golden_pubacc.py` | no | PUBACC-1 |
| SANSRV | `sansrv_cases.json` | `test_golden_sansrv.py` | yes | SANSRV-1, SANSRV-2 |
| DRKWAT | `drkwat_cases.json` | `test_golden_drkwat.py` | no | DRKWAT-1 |
| AQELEC | `aqelec_synthetic_cases.json` | `test_golden_wef.py`; original workbook: `test_golden_wef_real_data.py` (opt-in) | no | AQELEC-1 |
| MURDER | `murder_cases.json` | `test_golden_murder.py` | yes | MURDER-1, MURDER-2 |
| CYBSEC | `cybsec_synthetic_cases.json` | `test_golden_cybsec.py`; original transcription: `test_golden_public_safety_real_data.py` (opt-in) | no | CYBSEC-1, CYBSEC-2, CYBSEC-3 |
| PRISON | `prison_synthetic_cases.json` | `test_golden_prison.py`; original workbook: `test_golden_public_safety_real_data.py` (opt-in) | yes | PRISON-1, PRISON-2, PRISON-3, PRISON-4 |
| SECAPP | `secapp_synthetic_cases.json` | `test_golden_secapp.py`; original workbooks: `test_golden_public_safety_real_data.py` (opt-in) | no | SECAPP-1, SECAPP-2, SECAPP-3 |
| RULELW | `rulelw_synthetic_cases.json` | `test_golden_rights.py`; original archive: `test_golden_rights_real_data.py` (opt-in) | yes | RULELW-1, RULELW-2, RULELW-3 |
| EDEMOC | `edemoc_synthetic_cases.json` | `test_golden_rights.py`; original archive: `test_golden_rights_real_data.py` (opt-in) | yes | EDEMOC-1, EDEMOC-2, EDEMOC-3 |
| ARMEXP | `armexp_synthetic_cases.json` | `test_golden_global_role.py`; original answer: `test_golden_global_role_real_data.py` (opt-in) | no | ARMEXP-1, ARMEXP-2, ARMEXP-3, ARMEXP-4 |
| RDFUND | `rdfund_cases.json` | `test_golden_global_role.py`; full responses: `test_golden_global_role_real_data.py` (opt-in) | yes | RDFUND-1, RDFUND-2, RDFUND-3 |

GINIPT's golden file was generated from two fixtures,
`tests/fixtures/wb/SI.POV.GINI_sample.json` and `tests/fixtures/wid`: its
regression fallback is trained on the ISHRAT scores computed from the WID
fixture.

CSTUNT's golden file was generated from three fixtures: the verbatim UN SDG
sample `tests/fixtures/unsdg/2_2_1_sample.json`, a synthetic variant of it
with year values blanked, `tests/fixtures/unsdg/2_2_1_synthetic_gaps.json`
(the live source has no gaps, so only a synthetic input exercises the series
fill; it is labelled as synthetic and is never source evidence), and the
World Bank sample `tests/fixtures/wb/NY.GDP.PCAP.CD_sample.json`, the
predictor of its regression fallback.

FDEPTH's golden file was generated from two fixtures,
`tests/fixtures/wb/FS.AST.PRVT.GD.ZS_sample.json` and
`tests/fixtures/wb/GFDD.OI.02_sample.json`. Its legacy impute route exists
but raises on every input; see "Inoperative legacy impute routes" below.

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

### How the Worker Wellbeing fixtures relate to the legacy source

The canonical Worker Wellbeing category (`methodology/ms/wwb/methodology.md`,
`category_code: WWB`) is UNEMPB, MATERN, FATINJ and SENIOR. UNEMPB is the
code the 2018 static data and `local/sspi-categories.json` call UNEMPL; the
executable route, the methodology file and `custom-sspi.json` use UNEMPB.
There is no UNEMPL indicator or alias. The legacy dataset `ILO_UNEMPL` (ILO
`DF_SDG_0131_SEX_SOC_RT`, `SOC_CONTIG_UNE`, the ILO's own copy of the same
SDG series, which the 2018 static values came from) has a cleaner but no
indicator reads it; it is not in the catalog and not ported.

**UNEMPB.** `tests/fixtures/unsdg/1_3_1_sample.json` is a verbatim subset of
the UN SDG PivotData response for indicator 1.3.1, read 2026-10-18 (4,864
rows in twelve social-protection series; the legacy collector requested the
whole indicator). It holds every `SI_COV_UEMP` row for Austria (both sexes,
female and male, so the `sex=BOTHSEX` filter is exercised), the `BOTHSEX`
row of the United States, Malaysia (one value, 2019), Germany (values of
100, as Austria), Canada, Japan (first value 2001, last 2020), India,
Nigeria, Singapore and Ethiopia (reported zeros), China, South Africa (last
value 2023), Colombia and Ethiopia (2024 values, past the extrapolation
target), Kuwait, the United Arab Emirates, Saudi Arabia, Kosovo (no ISO 3166
code) and two aggregates (World, Europe), plus one row of another series
each for Iceland and Malaysia. Every `SI_COV_UEMP` row has one age
group (`15+`) and one unit (`PERCENT`), so sex is the only slicing
dimension. Iceland, the hard-coded reference-class recipient, has no
`SI_COV_UEMP` row in the full response either. `generate_worker_wellbeing_cases.py`
runs the registered legacy cleaner and both legacy routes on it. Parity is
exact: 106 observations (16 countries, 2000–2024, 918 empty values, World,
Europe and Kosovo skipped), 106 observed and 304 imputed scores, including
Iceland's 24 rows at the mean of the fixture's 106 values (35.5288). The
impute route labels its scores `Tax Rate` (UNEMPB-1); with no data at all it
raised `ValueError: Reference data cannot be empty.`, and the new backend
raises `ImputationError` there.

**FATINJ.** `tests/fixtures/ilo/DF_SDG_F881_SEX_MIG_RT.json` is the complete,
unmodified response to the legacy collector's request,
`https://sdmx.ilo.org/rest/data/DF_SDG_F881_SEX_MIG_RT?format=jsondata` (no
key, no time window), read 2026-10-18: 366 series, 720 observations, of
which the `SEX_T` / `MIG_STATUS_TOTAL` slice the legacy cleaner keeps is
457 observations for 103 areas, 2000–2024. It holds no null value and no
aggregate area code (the adapter tests cover both), twelve reported zeros
(Iceland, San Marino, Colombia, French Guiana), a value exactly at the
lower goalpost (Cuba 2010, 25.0) and values far above it (India 2000–2007,
South Africa 2024 at 556.992). Parity is exact for all 457 observations and
all 457 scores. Legacy FATINJ has no impute route, so nothing is imputed.

**Live validation, 2026-10-18** (live, illustrative; not parity evidence):

| | UNEMPB | FATINJ |
|---|---|---|
| Request | UN SDG 1.3.1, all pages, one fetch | ILO `DF_SDG_F881_SEX_MIG_RT`, one fetch |
| Raw rows | 4,864 pivot rows (648 `SI_COV_UEMP`, 248 both sexes) | 366 series, 720 observations |
| Observations | 1,077 (207 countries, 2000–2024; 41 aggregates and Kosovo skipped; 12,171 empty values; 308 zeros kept) | 457 (103 areas, 2000–2024; nothing skipped or empty; 12 zeros kept) |
| Scores | 1,077 observed, 3,919 imputed, none unscored | 457 observed, none imputed |
| SSPI67 | all 66 scored (65 observed, Iceland by the reference class); 534 of 1,584 country-years 2000–2023 observed | 53 scored; 13 never (ARE, BGD, CHN, ETH, IDN, IRN, IRQ, KEN, KWT, NGA, PER, VEN, VNM); 277 of 1,584 country-years 2000–2023 scored |
| MYS / AUT / USA | MYS 2019 only, carried to 2000–2023 (0.104); AUT 0.99 in 2023 (2021 carried); USA 0.505 in 2023 (2021 carried) | MYS 2022 (0.4168); AUT 2024 only (no 2010–2023 score); USA 2023 (0.86) |
| Old data in recent years | 2023: 4 SSPI67 countries observed, 58 carried forward, 3 interpolated, 1 reference class; 20 SSPI67 countries' 2000 values come from 2015 or later (12 from 2019) | none carried: unscored years stay unscored |

### Worker Wellbeing indicators not ported

**MATERN: no executable legacy methodology, new source.** At the pinned
commit `api/core/sspi/ms/wwb/matern.py` holds one import and no route;
`OECD_MATERN` has no collector or cleaner (`api/core/datasets/oecd/__init__.py`
is empty) and its metadata has no series or query code (`base_url:
https://stats.oecd.org/`). The legacy backend never produced a MATERN
score, so there is nothing to hold parity against. The definition, "paid
parental leave available to mothers (full-rate equivalent) in weeks during
the first year", is the OECD Family Database indicator PF2.1. OECD.Stat
(`stats.oecd.org`) is retired and redirects to the OECD Data Explorer; the
OECD SDMX API (`https://sdmx.oecd.org/public/rest/`, no authentication)
lists no parental-leave dataflow, so the figures would come from the Family
Database's spreadsheet, a file per edition. The 2018 static values (49
countries, goalposts 0–52 weeks, `IndicatorDetailsStatic.csv`) are
consistent with that definition. A source decision (which publication and
edition, weeks of full-rate-equivalent leave, how a country with no scheme
is recorded) and a new OECD adapter are needed; the methodology question is
MATERN-1.

**SENIOR: route not executable, new source.** `compute_senior` reads raw
documents with `sspi_raw_api_data.fetch_raw_data("SENIOR")`, which raises
`InvalidQueryError` at the pinned commit (it requires a source-info dict).
Its collector is commented out and passes `"SENIOR"` as the query
parameters; the three canonical datasets (`OECD_POVNRT`, `OECD_YRSRTM`,
`OECD_YRSRTW`) have no collector or cleaner; the route writes its scores to
the clean-data collection, and `impute_senior` returns nothing. The intended
source is the OECD Pensions at a Glance dataflow
`OECD.ELS.SPD,DSD_PAG@DF_PAG`, still served without authentication at
`https://sdmx.oecd.org/public/rest/data/OECD.ELS.SPD,DSD_PAG@DF_PAG?startPeriod=1990&dimensionAtObservation=AllDimensions`
(SDMX-ML generic data, 12,939 observations on 2026-10-18). Even with a
working collector the route as written scores almost nothing: life
expectancy and the retirement age are published for 2024 only, old-age
poverty for 2014–2022 (even years), so no country-year has all five inputs
(SENIOR-1). Its formula also differs from the canonical datasets
(SENIOR-2) and rewards higher old-age poverty (SENIOR-3). A methodology
decision and a new OECD SDMX adapter are needed. The same adapter could
serve other OECD datasets in the catalog (MATERN if the OECD publishes it
there, and the OECD aid datasets).

Status: Worker Wellbeing is partly migrated. UNEMPB and FATINJ have exact
historical parity and run from an empty database; MATERN and SENIOR are
blocked as above; no category score is computed.

### How the Healthcare fixtures relate to the legacy source

The canonical Healthcare category (`methodology/pg/hlc/methodology.md`,
`category_code: HLC`) is ATBRTH, DPTCOV, PHYSPC, FAMPLN and CSTUNT; the
executable routes (`api/core/sspi/pg/hlc/`), the methodology files and
`custom-sspi.json` agree on these five codes. Nothing was renamed. Four read
WHO Global Health Observatory datasets and one, CSTUNT, reads the UN SDG
API, with World Bank GDP per capita as the predictor of its regression
fallback. CSTUNT, ATBRTH, DPTCOV and PHYSPC are ported; FAMPLN is not
(the WHO sections below).

**CSTUNT.** `tests/fixtures/unsdg/2_2_1_sample.json` is a verbatim subset of
the UN SDG PivotData response for indicator 2.2.1, read 2026-10-18 (1,188
rows in two series: `SH_STA_STNT`, the share of children under 5 moderately
or severely stunted, and `SH_STA_STNTN`, their number; every value is a
modelled Joint Malnutrition Estimate, `Nature` `M`, 2000–2024; the legacy
collector requested the whole indicator). It holds every sex slice of
`SH_STA_STNT` for Malaysia (so the `sex=BOTHSEX` filter is exercised), the
`SH_STA_STNTN` row for Malaysia, and the both-sexes row of the United
States, India, Burundi (the largest values, 63 % in 2000), Australia (the
smallest, 0.9 %), Germany, Japan, China, Nigeria, Pakistan, Brazil, Mexico,
Singapore, Kuwait, Saudi Arabia, North Korea (no GDP data), Yemen and the
Turks and Caicos Islands (GDP for part of the years), World and Africa.
Every country has every year 2000–2024, as in the full response, so the
legacy series fill adds nothing. `2_2_1_synthetic_gaps.json` is the same
sample with year values blanked for five countries (Malaysia at both ends,
the United States in the middle, India all but 2015, Nigeria after 2005,
Pakistan entirely): synthetic, and labelled so, to exercise the series fill
and a source country with no value. `tests/fixtures/wb/NY.GDP.PCAP.CD_sample.json`
is a row subset of the World Bank response for `NY.GDP.PCAP.CD` (see the
fixture README): every row, 1960–2025, for the countries of the UN sample
and for ten economies without a stunting estimate (Austria, Switzerland and
Luxembourg, above the 100,000-dollar goalpost in recent years, Canada, New
Zealand, Russia, Iceland, the United Arab Emirates, Bermuda and Monaco),
plus World, High income and Kosovo. `generate_healthcare_cases.py` runs the
registered legacy cleaners and both legacy routes on the two UN inputs,
observing the scikit-learn fit through a recording subclass. Parity is
exact:

| | Verbatim sample | Synthetic gaps |
|---|---|---|
| `UNSDG_CSTUNT` observations | 450 (18 countries, 2000–2024; World and Africa skipped; 702 empty values) | 370 |
| `WB_GDP_PERCAP_CURPRICE_USD` observations | 1,650 (27 economies, 1960–2025; 198 empty values) | same |
| Observed scores | 450 | 370 |
| Series-filled scores | 0 | 52 (29 forward, 20 backward, 3 interpolated; unit `Coefficient`) |
| Regression training set | 418 country-years | 338 |
| Coefficient, intercept | 1.1494583602006676, 0.39946324246142784 | 0.9346435547945705, 0.49488710839619365 |
| Predicted scores | 609 for 10 economies, 1960–2025 | 675 for 11 (Pakistan added) |

The coefficient and intercept equal the legacy sklearn fit bit for bit. The
legacy route fails, and so does the new one (`ImputationError`, nothing
written), when there is no `UNSDG_CSTUNT` row (`IndexError`), no GDP row or
no country without stunting data (`KeyError: 'Score'`); the golden file
records the three legacy errors.

**Live validation, 2026-10-18** (live, illustrative; not parity evidence):

| | CSTUNT |
|---|---|
| Requests | UN SDG 2.2.1, all pages, one fetch; World Bank `NY.GDP.PCAP.CD`, one fetch |
| Observations | `UNSDG_CSTUNT` 4,050 (162 countries, every year 2000–2024; 36 aggregates skipped; 6,318 empty values; no zero). `WB_GDP_PERCAP_CURPRICE_USD` 11,721 (212 economies, 1960–2025; 51 aggregates and Kosovo skipped; 2,469 empty values) |
| Scores | 4,050 observed, 0 series-filled, 2,586 regression-predicted (51 economies, 1960–2025; 1,334 before 2000, 75 after 2023); fit 1.0892 × GDP score + 0.5054 over 3,982 country-years |
| SSPI67 | 48 observed in every year 2000–2024; 18 predicted only (ARE, AUT, CAN, CHE, DNK, ESP, FRA, HUN, ISL, ISR, ITA, LUX, NOR, NZL, RUS, SVK, SVN, SWE); none unscored |
| MYS / AUT / USA, 2023 | MYS 23.7 % observed (0.526); AUT predicted 1.0 (implied 0 %); USA 4.0 % observed (0.92) |
| Old data in recent years | none carried: every observed 2023 score is that year's modelled estimate. The estimates are model output, revised with each JME edition; the newest survey behind a country's estimate can be much older |
| Legacy on the same responses | the pinned legacy cleaners and routes produce the same 6,636 scores (identical digest of country, year, score, unit and imputed flag) |

Eleven SSPI67 members are predicted at 1.0 in 2023, above every observed
country (Poland, 0.978, is the highest); see CSTUNT-2.

### How the WHO fixtures relate to the legacy source

ATBRTH, DPTCOV and PHYSPC read the WHO Global Health Observatory (GHO)
OData API, approved as a source on 2026-10-19. The legacy collector
(`api/datasource/who.py`, `collect_who_data`) sent one unauthenticated GET
per indicator, `https://ghoapi.azureedge.net/api/<code>`, and stored the
parsed JSON object; the cleaner (`clean_who_data`) keeps rows whose
`SpatialDimType` is `COUNTRY` and whose `Value` is not `"No data"`, applies
an optional exact-match filter on row fields (unused for these three), and
takes `SpatialDim` as the country code (not checked against ISO 3166),
`int(TimeDim)` as the year and `float(NumericValue)` as the value, with the
dataset's unit literal. `sspi.ingestion.who` reproduces it with one
generic client and normalizer (no indicator-specific branch): base URL
configurable, the indicator from canonical `query_code`, OData
`@odata.nextLink` paging followed if the service ever pages (it does not
today), declared dimension filters on `Dim1`-`Dim3` or `DataSourceDim`,
duplicate (country, year) identities refused, zeros kept, a missing number
refused (legacy `float(None)` raised), and the request URL, OData context,
disaggregation fields, data source, bounds, WHO's comment and change date
in provenance. WHO announced that this OData implementation would be
deprecated "near the end of 2025"; it still answered on 2026-10-19, and the
adapter does not fall back to any other API.

**Fixtures: synthetic in the repository, real data opt-in (GOV-1).** WHO
extracts are not distributed with the repository while redistribution
rights are open. That is a data-governance and licensing review item, not
a methodology question (`docs/data-governance-review.md`, GOV-1). Production
ingestion always reads the live GHO API; only the test inputs differ.

*Committed, synthetic.* `tests/fixtures/who/<code>_synthetic.json` are
invented GHO-shaped responses. They are written by
`tests/fixtures/who/build_synthetic.py`, every row is labelled synthetic,
and nothing is copied from WHO data. `generate_who_cases.py` ran the
registered legacy cleaners and every legacy route on them at the pinned
commit. Parity is exact:

| | WHO_ATBRTH / ATBRTH | WHO_DPTCOV / DPTCOV | WHO_PHYSPC / PHYSPC |
|---|---|---|---|
| Rows | 60: MYS, AUT, USA, QMA–QMF; 12 aggregate rows | 96: MYS, AUT, USA, QMA–QMC; 8 aggregate rows | 91: MYS, AUT, USA, QMA–QMF; 8 aggregate rows |
| Observations | 46 (8 countries, 2000–2024); 2 `"No data"` rows dropped | 87 (6 countries, 2000–2025); 1 `"No data"` | 82 (8 countries, 1990–2024); 1 `"No data"` |
| Observed scores | 46 | 87 | 82 |
| Imputed scores | 267: 62 forward, 55 backward, 30 interpolated, 120 reference class (five countries × 24 years at the mean of 46 rows) | none (no impute route) | 152: 50 forward, 37 backward, 65 interpolated (19 before 2000) |
| Covers | 80 and 79.9 (score 0), 100 (score 1), a reported zero carried both ways, a `"No data"` row inside a gap and as a country's only row, Austria's 2023 between 2022 and 2024 (interpolated), a 2024 value past the fill target, an early end carried 21 years, a rounded display value | 75 and 74.9 (score 0), 99 (0.96), 100 (score 1, which WUENIC's 99 % cap never produces), a zero, late starts and gaps left empty | 70 and 72 (score 1), an outlier of 140, a zero and 0.13, an 18-year gap mostly before 2000, a late start carried back 18 years, an early end |
| No rows at all | impute route raised `ValueError: Reference data cannot be empty.`; the new backend raises `ImputationError` | nothing scored | nothing scored or imputed |

Every kind of aggregate (GLOBAL, REGION, WORLDBANKINCOMEGROUP, UNREGION) is
skipped, and user-assigned country codes are kept as served, as the legacy
cleaner kept them. Paths no legacy fixture reaches are tested on synthetic
messages in `tests/unit/test_who_adapter.py`: a missing number, a
non-storable code, disaggregated rows, duplicates and paging.

*Real data, opt-in.* The real-data parity evidence is kept outside the
repository, in the git-ignored `local-data/who/`, pinned by the committed
`tests/fixtures/who/REAL_DATA.sha256` (see `tests/fixtures/who/README.md`).
It holds the verbatim GHO row subsets of 2026-10-18, the golden files the
pinned legacy code produced from them, and the full responses. With
`SSPI_WHO_REAL_DATA=local-data/who`, `test_golden_who_real_data.py` (marker
`who_real_data`) runs the original real-data parity tests, and
`tests/db/test_healthcare_end_to_end.py` runs the workflow on the real
subsets. Parity is exact:

| Real subset (of the full response) | Rows kept | Covers |
|---|---|---|
| `MDG_0000000025_sample.json` (2,749 rows) | 200: twelve countries and the GLOBAL and EUR aggregates | Malaysia, Austria (2023 missing: interpolated), the United States; Ethiopia (the smallest value, 6 %), Iraq (exactly 80 % in 2007), Palau (100 %), Turks and Caicos (one value, 2020), Spain (first value 2015), Slovenia (last value 2012), Libya (2007–2013), India and Nigeria (gaps); none of the five hard-coded recipients |
| `WHS4_100_sample.json` (5,337 rows) | 275: eight countries and the GLOBAL, EUR and WB_HI aggregates | Malaysia, Austria, the United States; Ukraine (19 % in 2016 and 99 %, the WUENIC cap, in 2000), Argentina (exactly 75 % in 2024–2025), South Sudan (first value 2011), Nigeria and India (below 75 %) |
| `HWF_0001_sample.json` (3,693 rows) | 205: ten countries and the GLOBAL, AFR and WB_LI aggregates | Malaysia, Austria (95.42 in 2018, PHYSPC-1), the United States (1993–2022); Cuba and Georgia (above 70), Liberia (the smallest value, 0.13), Canada (first value 2018), Nauru (last value 2015), San Marino and Monaco (long interior gaps, Monaco's before 2000) |

| Real subsets | WHO_ATBRTH / ATBRTH | WHO_DPTCOV / DPTCOV | WHO_PHYSPC / PHYSPC |
|---|---|---|---|
| Observations | 148 (12 countries, 2000–2024) | 197 (8 countries, 2000–2025) | 202 (10 countries, 1990–2024) |
| Observed scores | 148 | 197 | 202 |
| Imputed scores | 262: 33 forward, 45 backward, 64 interpolated, 120 reference class (mean of 148 rows, 89.94 %) | none | 96: 14 forward, 33 backward, 49 interpolated (seven before 2000) |
| Units | `Percent` → `%` (both routes) | `Percent` → `%` | `Doctors per 10000` → `Rate` (both routes) |

**Live validation, 2026-10-19** (live, illustrative; not parity evidence).
One request per indicator, one page each; the responses were identical to
those of 2026-10-18 (no row added, removed or changed). Run on the same
responses, the pinned legacy cleaners and routes produce the same scores as
the new backend (identical digest of country, year, score, unit and imputed
flag) for all three.

| | ATBRTH (`MDG_0000000025`) | DPTCOV (`WHS4_100`) | PHYSPC (`HWF_0001`) |
|---|---|---|---|
| Raw rows / canonical observations | 2,749 / 2,567 (193 countries, 2000–2024) | 5,337 / 5,051 (195 countries, 2000–2025) | 3,693 / 3,682 (194 countries, 1990–2024) |
| Skipped | 182 aggregate rows (7 areas) | 286 (11 areas) | 11 (11 areas) |
| `"No data"` / zeros | 0 / 0 | 0 / 0 | 0 / 0 |
| Scores | 2,567 observed, 2,222 imputed | 5,051 observed, none imputed | 3,682 observed, 1,812 imputed |
| SSPI67 | 61 with data; BEL, CHE, GBR, NLD, SWE by the reference class only (91.50 %, score 0.575, every year); none unscored | all 66 observed; none unscored | all 66 with data; none unscored |
| 2023 scores of SSPI67 members | 34 observed, 27 filled from the country's own series, 5 reference class; built from data more than five years old: CHN (7), CZE (6), ZAF (7), SVN (11 years) | 66 observed | 54 observed, 12 filled; more than five years old: LUX and VEN (6) |
| MYS / AUT / USA, 2023 | 0.99 (2022 value carried) / 0.92 (interpolated 2022–2024) / 0.94 observed | 0.80 / 0.48 / 0.76, all observed | 0.334 / 0.788 observed / 0.379 (2022 carried) |
| WHO change dates on the rows | 2024-04-26 to 2026-04-21 | 2025-07-14 to 2026-07-14 (WUENIC round) | 2026-01-23 to 2026-03-11 (NHWA, December 2025 update) |

The GHO API serves no editions: each fetch returns whatever WHO publishes
that day, and WUENIC and the workforce accounts revise past years (DPTCOV-1,
PHYSPC-1). A changed value after a re-ingest is a source revision, not a
parity failure; the synthetic fixtures and the checksummed real subsets pin
the parity evidence.

### Healthcare indicator not ported

**FAMPLN: the legacy route scores nothing, and the measure is ambiguous.**
The pinned collector requests GHO `SDGFPALL` ("Women of reproductive age
(aged 15-49 years) who have their need for family planning satisfied with
modern methods (%)"; numerator women using a modern method, denominator
total demand for family planning, in percent; rows `SEX_FMLE`,
`AGEGROUP_YEARS15-49`, no marital-status dimension). The cleaner keeps 480
country rows (142 countries, 2000–2023, survey-based; 34 SSPI67 members,
none for Austria). The compute route's score function is
`lambda UNSDG_FAMPLN: goalpost(UNSDG_FAMPLN, 20, 100)` while the data is
`WHO_FAMPLN`, so the legacy scorer finds no argument and stores 0 scores;
there is no impute route. The canonical description is unmet need among
married or in-union women (lower is better), the 2018 static SSPI scored
unmet need among girls 15–19 (`MDG_0000000006_AGE1519`) as
1 − value / 100, and WHO's metadata registry describes the demand-satisfied
measure for married or in-union women while the code's rows say only
"female, 15–49". These are different measures (contraceptive prevalence,
modern contraceptive prevalence, demand satisfied with modern methods,
unmet need) and the GHO publishes each under its own code. There is no
executable output to hold parity against and choosing among them is a
methodology decision (FAMPLN-1). The WHO adapter can read `SDGFPALL`, but
`WHO_FAMPLN` is not ingestible and FAMPLN is not registered.

Status: Healthcare is partly migrated. CSTUNT, ATBRTH, DPTCOV and PHYSPC
have exact historical parity and run from an empty database; FAMPLN is
blocked on a methodology decision; no category score is computed. The WHO
data-governance question (GOV-1, `docs/data-governance-review.md`) does not
block development: production ingests the real GHO data, the committed WHO
parity tests run on synthetic fixtures, and real-data parity is an opt-in
check against committed checksums.

### How the Financial Sector fixtures relate to the legacy source

The Financial Sector category (`FIN`) has three leaf indicators in the
canonical metadata and in the pinned legacy methodology tree: `FSTABL`,
`FDEPTH` and `PUBACC`. Two are migrated. All three World Bank fixtures are
row subsets of one live response each, cut the way the earlier World Bank
samples were (`tests/fixtures/wb/README.md`): verbatim rows in API order,
the page metadata's `per_page` and `total` set to the number of rows kept.
They were downloaded on 2026-10-19 with `per_page=20000`.

| Fixture | Series | Rows kept | Kept by the legacy cleaner |
|---|---|---|---|
| `FS.AST.PRVT.GD.ZS_sample.json` | WDI "Domestic credit to private sector (% of GDP)" (source 2, updated 2026-10-08) | 1,386 | 625 observations, 14 countries, 1960–2025 |
| `GFDD.OI.02_sample.json` | Global Financial Development "Bank deposits to GDP (%)" (source 32, updated 2022-09-23) | 1,178 | 616 observations, 12 countries, 1960–2021 |
| `FX.OWN.TOTL.ZS_sample.json` | WDI "Account ownership at a financial institution or with a mobile-money-service provider (% of population ages 15+)" (Global Findex) | 1,386 | 61 observations, 14 countries, survey years 2011–2024 |

Each keeps every row of the same economies: Malaysia, Austria and the
United States (the researcher guide's query); the United Kingdom (credit,
no deposit series at all); Serbia and DR Congo (served by GFDD with a
two-letter id and no ISO3 code, so the legacy cleaner drops their deposits
and only credit remains); San Marino (deposits, no credit); Romania and
Guinea-Bissau (zero credit values, dropped by the cleaner's truthiness
test); Luxembourg, Iceland, Denmark and Norway (deposits up to 462 % of
GDP, credit up to 301 %, account ownership of exactly 100 %); Mexico and DR
Congo (the 2022 Findex fieldwork); Zimbabwe and Turkmenistan (the smallest
values); the aggregates World, Africa Eastern and Southern, European Union,
High income (no ISO3 code, id `XD`) and GFDD's "IDA total" (no code at
all); Taiwan (GFDD id `TW`); and Kosovo (`XKX`).

`tests/golden/generate_financial_cases.py` ran the registered legacy
cleaners and the `compute_fdepth`, `impute_fdepth` and `compute_pubacc`
view functions on these samples. The new backend matches every
observation, skipped area, missing-value count, score, input and
incomplete identity exactly, first time, with the existing World Bank
adapter and no change to it (`GFDD.OI.02` is served by the same API path,
from source 32, in the same row shape). Both indicators use only the
generic compute path: no new strategy.

Live validation, 2026-10-19. The full responses of all three series, run
through the pinned legacy cleaners and routes and through the new backend,
gave identical records (SHA-256 of the sorted records, new backend):

| Item | Records | Digest |
|---|---|---|
| `WB_CREDIT` observations | 7,652 (185 countries, 1960–2025) | `310b5a658fd713052b7d76a58a3788e0de001a12c55381a3deaace69816cea39` |
| `WB_DPOSIT` observations | 8,334 (178 countries, 1960–2021) | `7deb931c832290274a835d585d344761ed2aae928cec3d39971f9f10cc8248e5` |
| `WB_PUBACC` observations | 700 (160 countries, 2011–2024) | `dc70e1444608c41393bc9c1f94762e0832c5352224d0e36eb4ae5229ed263f03` |
| `FDEPTH` scores | 6,527 (2,932 incomplete identities) | `bd32b02460eeddb62601e37e4b07a9540987b08096357abc01567ae330e5f0af` |
| `PUBACC` scores | 700 | `3ae4cf34a079cb730123e3479d4614d89d0326e7a6af5af64f61741e625629c4` |

Live coverage of SSPI67 over 2000–2023 (1,584 country-years): FDEPTH 1,260,
for 65 members (never the United Kingdom, which has no deposit series),
none after 2021; PUBACC 256, for all 66 members, only in 2011, 2014, 2017,
2021 and (three members) 2022. The World Bank serves no editions; WDI is
revised with each release, and GFDD has not changed since September 2022.

### Financial Sector indicator not ported

**FSTABL: no executable legacy computation, and no defined source.** The
canonical metadata and the methodology file name one dataset, `IMF_FSTABL`
("the percentage of loans that are nonperforming", goalposts 10 → 0), but
at the pinned commit:

- `api/core/sspi/ms/fin/fstabl.py` holds one import and a commented-out
  collector stub pointing at an IMF API package; there is no compute or
  impute view, so the legacy backend never produced an FSTABL score;
- `IMF_FSTABL` has no definition: its documentation file was deleted in
  commit `9064c4052` ("Added IMF datacollection, added FSTABL collection
  from WB", 2025-11-29), which added instead a `WB_FSTABL` collector and
  cleaner for the World Bank series `FB.AST.NPER.ZS` ("Bank nonperforming
  loans to total gross loans (%)", WDI, sourced from the IMF Financial
  Soundness Indicators) and a generic IMF DataMapper client that nothing
  calls;
- no route, score function or methodology file reads `WB_FSTABL`, and it is
  not in the canonical catalog (the importer takes the datasets indicators
  name).

The 2018 static values (`FSTABL_RAW`, scored as (10 − raw) / 10) are close
to, but not the same as, today's World Bank series (Austria 2018: 1.6
static, 2.9 now; Greece 38.5 and 43.4). Whether `WB_FSTABL` was meant to
replace the IMF dataset is not recorded. Substituting it, or adopting an
IMF Financial Soundness Indicators source (a new organization and
adapter), is a research decision (FSTABL-1). FSTABL is not registered and
`IMF_FSTABL` is not ingestible; both raise a clear error.

Status: Financial Sector is partly migrated. FDEPTH and PUBACC have exact
historical parity, identical live results and run from an empty database;
FSTABL is blocked on a source and methodology decision; no category score
is computed.

### How the Infrastructure fixtures relate to the legacy source

The Infrastructure category (`INF`) has five leaf indicators in the
canonical metadata and the pinned methodology tree: `AQELEC`, `SANSRV`,
`DRKWAT`, `INTRNT` and `TRNETW`. Three are migrated: SANSRV and DRKWAT
here, AQELEC in the next section. These two fixtures are row
subsets of one live World Bank response each (downloaded 2026-10-19 with
`per_page=20000`, cut as in `tests/fixtures/wb/README.md`):

| Fixture | Series | Rows kept | Kept by the legacy cleaner |
|---|---|---|---|
| `SH.STA.BASS.ZS_sample.json` | WDI "People using at least basic sanitation services (% of population)" (WHO/UNICEF JMP; updated 2026-10-08) | 1,320 | 355 observations, 16 countries, 2000–2024 |
| `SH.H2O.SMDW.ZS_sample.json` | WDI "People using safely managed drinking water services (% of population)" (WHO/UNICEF JMP; updated 2026-10-08) | 1,320 | 274 observations, 12 countries, 2000–2024 |

Both keep every row of the same economies: Malaysia, Austria and the United
States; Argentina (sanitation to 2016, no safely managed water), Angola and
Congo (series ending 2022 and 2021), Saudi Arabia, Romania, Russia and the
Turks and Caicos (series starting 2013, 2001, 2002 and 2016), Korea (water
from 2002), Ethiopia and Tanzania (the smallest values, below the 50 %
sanitation goalpost), Kuwait and the United Kingdom (100 %), China (no
safely managed water); and World, Africa Eastern and Southern, High income
(id `XD`, no ISO3 code) and Kosovo, all skipped. The source has no zero, no
interior gap and no single-year series, so `sansrv_cases.json` adds a
variant, `with_rows_removed`: the committed sample minus Malaysia
2010–2012 and Turks and Caicos 2017–2024 (rows removed, no value invented),
on which the legacy impute route leaves the gap empty and carries the
single year both ways.

`tests/golden/generate_infrastructure_cases.py` ran the registered legacy
cleaners and the `compute_sansrv`, `impute_sansrv` and `compute_drkwat`
view functions, with the legacy collections' insert validation applied. The
new backend matches every observation, skipped area, missing-value count,
observed and imputed score, input and imputation field exactly, first time,
with the existing World Bank adapter and the existing
`SeriesFillThenScore` (steps forward then backward, no interpolation). No
adapter or strategy changed.

Live validation, 2026-10-19. The full responses (17,556 rows each), run
through the pinned legacy cleaners and routes and through the new backend,
gave identical records (SHA-256 of the sorted records, new backend):

| Item | Records | Digest |
|---|---|---|
| `WB_SANSRV` observations | 5,166 (214 countries, 2000–2024) | `725ef06557bc543352ec392056b704d95d499403ccb4ab756365bb0502a9da8e` |
| `WB_DRKWAT` observations | 3,716 (151 countries, 2000–2024) | `e9235dd72929de18a176fb03b161f091f7bc3adb8c4825d2a9b173ccddc30f6d` |
| `SANSRV` observed scores | 5,166 | `59a96aac346b7bd99e86499cf5a066bb1a6b0844b6f3797152421687bd6810f3` |
| `SANSRV` imputed scores | 163 (2000–2023) | `576f587fb1867197f1d20d9e9d331ad324a35b0d252e051e152a155b3455ab67` |
| `DRKWAT` scores | 3,716 | `a5779d2a06da50ff1377a1a27c8696c9330b3afb167307734384ee0c2e427c52` |

Live coverage of SSPI67 over 2000–2023 (1,584 country-years): SANSRV all
1,584, of which one member's 2023 score is carried from an old value
(Argentina, 2016); DRKWAT 1,356, for 57 members, none for Argentina,
Australia, China, Kenya, Saudi Arabia, Thailand, Türkiye, Uruguay and
Venezuela, and partial series for Korea, Poland and the United States. The
latest source year is 2024 for both. The JMP revises its estimates with
each release and the World Bank API serves no editions.

### How the WEF fixtures relate to the legacy source

AQELEC reads `WB_AVELEC` (World Bank `EG.ELC.ACCS.ZS`, access to
electricity, % of population) and `WEF_QUELEC` (WEF `WEF.GCIHH.EOSQ064`,
"Quality of electricity supply, 1-7 (best)"). The WEF series comes from the
WEF Global Competitiveness Index Historical Dataset workbook hosted by the
World Bank. It is WEF data, not a WDI series, and it is read by its own
adapter, `src/sspi/ingestion/wef.py`, approved on 2026-10-19:

- **Pinned workbook.** The workbook is named by `query_code`
  (`WEF-GCIHH_2023-07-17`) and pinned in `WORKBOOKS`:
  - URL `https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx`;
  - SHA-256 `a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451`;
  - 3,476,362 bytes, served with Last-Modified 2024-02-16, verified
    2026-10-19;
  - dataset last updated 2023-07-17, covering 2007–2017.

  A download with other bytes is refused. Another edition is read only
  from an explicitly passed `workbooks` table.
- **Series selection from metadata.** The series is
  `organization_series_code`, and `dimensions` (`Attribute 1: Value`) drop
  the rank rows.
- **Exact legacy representation.** The adapter reproduces the legacy
  representation exactly:
  - the first sheet goes through `read_excel` and then the collector's CSV
    round trip;
  - each year column is melted, and blanks are dropped and counted;
  - the unit is the text after the comma of the indicator name;
  - the codes the legacy clean collection refused are errors: codes that
    are not three capital letters, duplicates and non-numbers.
- **Dependency.** Reading Excel needs `openpyxl`, added as `openpyxl==3.1.5`
  (the legacy environment's version, with `et-xmlfile==2.0.0`).

The original workbook is not committed while its licence terms are open
(`docs/data-governance-review.md`, GOV-2). Parity is held on invented data
in the same layout, as for the WHO fixtures:

| Fixture | Content | Kept by the legacy code |
|---|---|---|
| `tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx` | invented, written by `build_synthetic.py`; 21 data rows (value, rank and another indicator for seven economies), metadata sheets marked synthetic | 46 observations, 6 economies, 2007–2017, 31 blank cells |
| `tests/fixtures/wb/EG.ELC.ACCS.ZS_sample.json` | real World Bank rows (WDI, 2026-10-08) for MYS, AUT, USA, TCD, NER, SSD, GBR and four skipped areas | 209 observations |

The synthetic workbook has:
- a survey gap (Malaysia 2009);
- a value with full precision;
- integer cells (4 and 7);
- both goalposts (Chad 2007 at 1, the United States 2017 at 7);
- a late start (Austria from 2015) and an early end (Chad to 2012);
- an economy without access data (`QMA`) and an aggregate-like code
  (`QRA`), kept as legacy kept them;
- an all-blank economy;
- rank rows and a second indicator, both filtered out.

`tests/golden/generate_wef_cases.py` ran:
- the legacy collector, with `requests.get` answered from the workbook
  bytes;
- the registered cleaners, with the legacy clean collection's own
  validation;
- `compute_aqelec`.

The new backend matches all 46 WEF and 209 access observations, the 30
scores, their inputs and the 195 incomplete identities exactly. The legacy
cleaner refused four invalid variants of the workbook: a repeated row, a
lowercase code, a code with a digit and a text value. The new adapter
refuses each of them too.

Opt-in, original workbook (`SSPI_WEF_REAL_DATA=local-data/wef`). The
original workbook and the full World Bank response (2026-10-08) are pinned
by the committed `tests/fixtures/wef/REAL_DATA.sha256`. On them the legacy
code and the new backend give identical records:

| Item | Records | Digest |
|---|---|---|
| `WEF_QUELEC` observations | 1,524 (152 economies, 2007–2017; 148 blank cells) | `f53fd04e826764df0aa6ddaa57d063d90cc310f43251d5ab5005c7503f4c5429` |
| `WB_AVELEC` observations | 6,702 (214 countries) | in the private golden file |
| `AQELEC` scores | 1,513 (2007–2017), 5,200 incomplete identities | `cfd29584dd13808c8336d0499aaade541bf121cb261cace683897d92eb94283e` |

SSPI67 coverage: 711 of the 726 member-years 2007–2017. Iraq is never
scored, Ecuador lacks one year and Iran three. There is no AQELEC score
for 2000–2006 or 2018–2023: the WEF series ends in 2017, and the legacy
route neither imputes nor carries values.

### Infrastructure indicators not ported

**INTRNT: the legacy route never stored a score.** It reads `WB_INTRNT`
(`IT.NET.USER.ZS`) and `UNSDG_INTRNT` (SDG 17.6.1, `IT_NET_BBND`, 10 Mbps),
neither in the canonical catalog (which lists `UNSDG_AVINTR` and
`CABLE_QUINTR`), and stores `(WB_INTRNT + UNSDG_INTRNT) / 2`, a raw average
far above 1, which the legacy indicator collection rejects: on the live
sources the route raises before storing anything. Any port would have to
choose a normalization or a dataset mapping; INTRNT-1.

**TRNETW: no executable implementation.** The route file holds one
import; `WB_RAILNT` has no definition and `CIA_ROADNT` no collector or
cleaner; TRNETW-1.

Status: Infrastructure is partly migrated. AQELEC, SANSRV and DRKWAT have
exact historical parity (AQELEC on invented data in the WEF layout and,
opt-in, on the original workbook) and run from an empty database; INTRNT
and TRNETW are blocked on methodology decisions (INTRNT-1, TRNETW-1); no
category score is computed.

### How the Public Safety fixtures relate to the legacy source

The Public Safety category (`SAF`) has four leaf indicators in the
canonical metadata and the pinned methodology tree: `MURDER`, `CYBSEC`,
`SECAPP` and `PRISON`. All four are migrated. MURDER and PRISON reproduce
the legacy code end to end. CYBSEC and SECAPP reproduce the legacy cleaner
and scorer exactly, with approved source-representation corrections where
the pinned acquisition could not store the source (CYBSEC-1, SECAPP-1; see
"Approved source-representation corrections" below).

**MURDER.** `tests/fixtures/wb/VC.IHR.PSRC.P5_sample.json` is a row subset
of one live World Bank response (downloaded 2026-10-25 with
`per_page=20000`; 17,556 rows, source 2, updated 2026-10-08; SHA-256 of the
full response `9e622dad31f8172f995e12e2fe3f75f031829503e10ba271f4f4f3eb126224bc`),
cut as in `tests/fixtures/wb/README.md`: 1,320 rows, 297 kept by the legacy
cleaner. It covers interpolation across gaps (the United States 2003–2005,
Belgium 2003–2012, Iraq 1995–2006, China 1998–2001, so before 2000 too),
forward carries (Thailand from 2011, Iraq from 2013, Monaco from 2001),
backward carries (Nigeria from 2016), single observations (Ethiopia 2012,
Monaco 2001), values above the 20 goalpost (Venezuela, Nigeria, Estonia)
and the four reported zeros the cleaner drops (Iceland 2006, Liechtenstein
2007 and 2009, Malta 2006; MURDER-1), plus skipped areas (Channel Islands,
World, High income, Kosovo). `generate_public_safety_cases.py murder` ran the
registered cleaner and the `compute_murder` and `impute_murder` view
functions with the legacy insert validation; the new backend matched every
record first time, with the existing World Bank adapter and the existing
`SeriesFillThenScore` (steps interpolate, forward, backward: the legacy
order).

Live validation, 2026-10-25. The full World Bank response, run through the
pinned legacy cleaner and routes and through the new backend, gave
identical records (SHA-256 of `json.dumps(records, sort_keys=True,
separators=(",", ":"))`, records as in `tests/golden/parity.py`):

| Item | Records | Digest |
|---|---|---|
| `WB_MURDER` observations | 4,043 (194 countries, 1990–2023) | `5e34ce01b8d12bceea83247381272d7c3c0a62f1861ddacabba4897087a3482c` |
| `MURDER` observed scores | 4,043 | `2c098ed61b64c635a34271ae3cec06008407f0936be4227aa3776e6e3884921d` |
| `MURDER` imputed scores | 1,719 (1995–2023) | `e2ae91a0a1cd9b9ba8e02be298bee0185c3e65e537838a4721410591e7f440af` |

Every SSPI67 member has observations; all 1,584 member-years 2000–2023 are
scored, 1,262 from observations. The latest source year is 2023.
Malaysia, Austria and the United States are observed through 2023 (scores
0.9633, 0.9562 and 0.7118 in 2023). Members carried furthest: Thailand
and Viet Nam (last values 2011), Iraq (2013), Iran (2014), Egypt (2017),
Bangladesh (2018), Saudi Arabia (2019); Nigeria back from 2016, Ethiopia
both ways from 2012 (MURDER-2). The World Bank API serves no editions;
UNODC revises the series.

### How the UNODC and ITU fixtures relate to the legacy source

**PRISON** reads `UNODC_PRIPOP` from the UNODC "Prisons and prisoners"
workbook. The legacy collector's address
(`https://dataunodc.un.org/sites/dataunodc.un.org/files/data_cts_prisons_and_prisoners.xlsx`)
now redirects to the data portal's home page; the portal serves the same
file at `https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_prisons_and_prisoners.xlsx`
(release dated 30/09/2026, SHA-256
`27f6a3bbc89769a9acef0675335b9ca4dca7ec3776db9499127256d39b7e14e6`). The new
adapter, `src/sspi/ingestion/unodc.py`, pins that release and reproduces
the legacy collector's `read_excel` → `to_csv` → `read_csv(skiprows=2)`
round trip, the six filters (as series code and dimensions) and the
cleaner's unweighted United Kingdom mean (PRISON-1).

The workbook's terms are open (GOV-3), so the committed fixture is
`tests/fixtures/unodc/data_cts_prisons_and_prisoners_synthetic.xlsx`,
invented data in the UNODC layout written by `build_synthetic.py`: two title
rows, both sheets, years as numbers and as text, rows every filter drops,
the UK jurisdictions with changing composition (all three 2005–2020, two in
2021, one in 2022), Iraq's two units, a single year, reported zeros, values
at and beyond both goalposts, empty values and an interior gap; China
absent. Five invalid variants, built in memory, record how legacy failed:
a repeated country-year, a national GBR row beside the jurisdictions, a
lowercase code, a code with a digit and a text value.
`generate_public_safety_cases.py prison` ran the registered collector (with
`requests.get` answering with the workbook), the registered cleaner, and
`compute_prison` and `impute_prison`, with the legacy insert validation;
the new backend matched every record first time, with the existing
`SeriesFillThenScore` (steps forward, backward, interpolate; China as a
listed recipient). A probe adding Chinese rows shows the legacy route
failing ("Duplicate dataset document found"); the new backend raises too
(PRISON-2).

Opt-in, on the original workbook (`SSPI_UNODC_REAL_DATA=local-data/unodc`,
`test_golden_public_safety_real_data.py`), and as live validation on
2026-10-25 (same file):

| Item | Records | Digest |
|---|---|---|
| `UNODC_PRIPOP` observations | 3,346 (222 areas, 2003–2024) | `a24fe44b83914aef3804ebd08f0173bc52d096e93151e5c2c9377a712f24c54e` |
| `PRISON` observed scores | 3,346 | `8a3669b42582821e6887dfbb80d04b9ec4cd5b278f5b830f1ec0f3b232783e45` |
| `PRISON` imputed scores | 2,142 (2000–2023) | `d317931a86bee97c8477020f92776fd0843201d54aef77c1a0b05bb7a9c38400` |

All 1,584 SSPI67 member-years 2000–2023 are scored, 1,190 from
observations. China has no series and gets 185.76 per 100,000 (the flat
mean of 3,346 rows) every year; Iraq's only national value is 2021
(PRISON-4); the United Arab Emirates ends in 2016 and Saudi Arabia in 2019.
Malaysia, Austria and the United States are observed through 2023 (2023
scores 0.6475, 0.8809 and 0.0123; Austria's 2015 is interpolated). Source
updates are not parity failures: against the release of May 2025 (Internet
Archive capture of 2025-06-05, which legacy read in September 2025) the
current release has 157 more observations, starts in 2003 instead of 2000,
and revises 68 values (27 for SSPI67 members).

**CYBSEC** reads `ITU_CYBSEC` from the SSPI's own hand transcription of the
ITU Global Cybersecurity Index, `local/CYBSEC/gci-local-indicator-summary.csv`
in the legacy repository (SHA-256
`f438b04d231799d6957ac81d02ad9db65dcc75a34b77bfc15654f52e5ae739b9`). The
pinned collector and cleaner read `local/gci-local-indicator-summary.csv`,
which no longer exists: both raise `FileNotFoundError` (recorded in the
golden file). The new generic local-file source
(`src/sspi/ingestion/localfiles.py`) reads the pinned file from
`local-data/itu/`, and `src/sspi/ingestion/itu.py` reproduces the cleaner:
the reindex on its column list, the division of 2020 and 2024 by 100
(CYBSEC-2), the melt, the legacy name matcher (`legacy_country_code` in
`src/sspi/ingestion/geo.py`) and the ten-decimal `to_json` representation.
The terms are open (GOV-4), so the committed fixture is
`tests/fixtures/itu/gci-local-indicator-summary_synthetic.csv`, invented
scores in the transcription's layout with real country names (each matcher
rule), written by `build_synthetic.py`; three variants record legacy
failures (the original's five uncoded spellings, which the approved
correction repairs; a name nothing codes; two names for one code).
`generate_public_safety_cases.py cybsec` ran the collector and cleaner in a
scratch directory holding the fixture at the old path, and `compute_cybsec`;
the new backend matched first time. On the original transcription (opt-in,
`SSPI_ITU_REAL_DATA=local-data/itu`) the legacy cleaner leaves five names
unmatched and the legacy clean collection refuses the whole dataset. The
approved correction (CYBSEC-1) maps exactly those five spellings to CIV,
MKD, FSM, PSE and VAT; the adapter then equals the legacy cleaner's own 968
rows with only that correction applied, and CYBSEC equals the legacy
compute route's 968 scores on them. Every SSPI67 member is scored in all
five editions except Canada, which is not in the transcription (CYBSEC-3;
the ITU reports publish four of its five values, recorded there, not
merged).

### How the FSI fixtures relate to the legacy source

**SECAPP** reads `FSI_SECAPP`, component C1 "Security Apparatus" of the
Fragile States Index, from the Fund for Peace's annual workbooks. The
pinned acquisition never stored a value (SECAPP-1, recorded on synthetic
records in `tests/golden/secapp_characterization_cases.json`): the
collector parses its address string instead of the page, the raw shape it
would store is not the one the cleaner reads, its source fields differ from
the documented source the cleaner queries, and the registered cleaner's
rows lack `DatasetCode`. The project owner approved a reusable FSI adapter
on 2026-10-25: `src/sspi/ingestion/fsi.py`.

Editions. The /excel/ page linked 18 editions on 2026-10-25, each twice;
the adapter pins the first link per year (as the working collector of
March 2025 did) by URL and SHA-256:

| Edition | File | Year cells | Rows |
|---|---|---|---|
| 2006–2017 | `wp-content/uploads/data/fsi-<year>.xlsx` (Last-Modified 2019-03-27) | 1 January dates of the edition year | 146 (2006), 177 (2007–2011), 178 (2012–2017) |
| 2018, 2019, 2020 | `wp-content/uploads/<year>/<month>/fsi-<year>.xlsx` | dates of the edition year | 178 |
| 2021 | `wp-content/uploads/2021/05/fsi-2021.xlsx` | integer 2021 | 179 |
| 2022 | `wp-content/uploads/2022/07/fsi-2022-download.xlsx` (sheet "FSI 2006-2022", 2022 only) | dates of 2022 | 179 |
| 2023 | `wp-content/uploads/2023/06/FSI-2023-DOWNLOAD.xlsx` (indicators in another order) | integer 2023 | 179 |

Every edition has `Country`, `Year` and `C1: Security Apparatus`; in every
edition all `Year` cells equal the year in the file name. No 2024 or later
workbook is linked from the page. Which calendar year an edition assesses
is open (SECAPP-2).

What is reproduced and what is repaired. The adapter reproduces the pinned
cleaner applied to each workbook as the March 2025 collector stored it
(`read_excel` rows, round-tripped through MongoDB). The repair adds the
dataset code, strips surrounding whitespace from names and maps five
spellings ("Cote d'Ivoire" → CIV, "Macedonia" → MKD, "Micronesia" → FSM,
"Palestine" → PSE, "North Korea" → PRK; the legacy matcher sends North
Korea to KOR, the code of South Korea); it changes no value and no year.
The FSI terms are unreviewed (GOV-5), so the committed fixtures are three
invented workbooks, `tests/fixtures/fsi/fsi-{2018,2021,2023}_synthetic.xlsx`,
written by `build_synthetic.py` in the three layouts, with the names that
exercise every rule; four invalid variants record what legacy and the
adapter do with an uncoded name, a duplicate, a blank value and a year that
is not the edition's.

`generate_public_safety_cases.py secapp` records, at the pinned commit, (A)
the registered cleaner's failure on those workbooks, (B) the cleaner's own
rows with only the approved repair, accepted by the legacy clean
collection's validation, and (C) `compute_secapp` on them. The new backend
equals (B) and (C) exactly, first time; every row whose name needed no
repair is the pinned cleaner's own row. Opt-in, on the 18 original
workbooks (`SSPI_FSI_REAL_DATA=local-data/fsi`): 3,170 observations, 179
countries, 2006–2023, and 3,170 SECAPP scores, identical to the legacy
outputs (A: the pinned cleaner refuses them; 99 unmatched name-editions and
two KOR rows in each of the 18 editions). SSPI67 coverage 2006–2023: 1,185
of 1,188 member-years (the United Arab Emirates, Iceland and Luxembourg are
not in the 2006 edition); nothing before 2006, nothing imputed. Malaysia,
Austria and the United States score 0.52, 0.86 and 0.53 in 2023. Israel's
unit of assessment changes in 2021 (SECAPP-3).

Status: Public Safety is migrated at leaf level, 4 of 4. MURDER and PRISON
reproduce the legacy code end to end; CYBSEC and SECAPP reproduce the
legacy cleaner and scorer with approved source-representation corrections
(CYBSEC-1, SECAPP-1, all confirmed); no category score is computed.

### How the Rights fixtures relate to the legacy source

The Rights category (`RTS`) has five leaf indicators in the canonical
metadata and the pinned methodology tree: `RULELW`, `PUBSRV`, `EDEMOC`,
`UNCONV` and `GENDEQ`. RULELW and EDEMOC have executable legacy routes and
are migrated with exact parity. PUBSRV, UNCONV and GENDEQ are one-line
stubs with no implementation anywhere in the repository's history; they
are blocked (see "Rights indicators not ported" below). No Rights category
score is computed.

**RULELW and EDEMOC** read two columns of one V-Dem archive: `v2x_rule`
(`VDEM_RULELW`) and `v2x_polyarchy` (`VDEM_EDEMOC`), the point estimates
of V-Dem's rule of law and electoral democracy indices (0–1; the
confidence bounds and standard deviations are never read). Both are scored
`goalpost(x, 0, 1)` with unit `Index`; both impute by carrying each
country's latest value forward to 2023 (nothing backward, no
interpolation). Both impute routes write into the observed collection
(RULELW-1, EDEMOC-1, resolved by an approved storage correction; see
"Approved storage corrections" below; the imputation question stays open as
RULELW-3 and EDEMOC-3).

### How the V-Dem fixtures relate to the legacy source

The legacy collector downloads
`https://v-dem.net/media/datasets/V-Dem-CY-FullOthers_csv_v13.zip`,
"Country-Year: V-Dem Full+Others", version 13 (March 2023). On 2026-10-26
that address still served it: 26,868,858 bytes, SHA-256
`8186847fa025e7fbc41b9f3b46aeccc6a13817c47d7305bc74e2289f062a28d4`, one CSV
(`V-Dem-CY-Full+Others-v13.csv`, 396,125,082 bytes, 4,602 columns, 27,555
rows, 1789–2022) and four PDFs. The adapter `src/sspi/ingestion/vdem.py`
pins it in `ARCHIVES` (key `V-Dem-CY-FullOthers_csv_v13`, the datasets'
query code) and refuses any other content; the series is the dataset's
`organization_series_code` (set from the cleaners' hard-coded columns in
PROVENANCE). It reproduces what the legacy code did, verified by running it:

- the collect route's iterator collects once for both datasets
  (`reduce_dataset_list`); the collector stores every member whose name
  contains `.csv` as UTF-8 text; the raw collection splits text longer than
  16,609,443 characters into fragments (24 for v13, not the "24 slices" its
  docstring promises by design: the count follows from the size) and the
  cleaner's fetch joins them again, losslessly;
- the cleaners keep `country_text_id`, `year` and the column, the years
  `> 1990` and `< datetime.now().year`, round-trip the rows through
  `to_json(orient="records")` (at most ten decimals) and drop empty values.
  The upper bound is the calendar year of the run: the adapter takes it
  from the date the archive is fetched (`VDemArchive.evaluation_year`) and
  records the window on each observation (`source_years`). On v13 it
  removes nothing for any run since 2023;
- V-Dem's identifiers are kept as published, with no ISO check: `XKX`
  (Kosovo), `PSE` (Palestine/West Bank), `PSG` (Palestine/Gaza), `SML`
  (Somaliland), `ZZB` (Zanzibar) are observations like any other.

`tests/fixtures/vdem/V-Dem-CY-FullOthers_csv_v13_synthetic.zip` is
invented data in the V-Dem layout (the original is not distributed,
GOV-6), written by `tests/fixtures/vdem/build_synthetic.py`: years before,
at and after the window (1989–2026, run year 2026), values exactly 0 and 1
and beyond both goalposts, more than ten decimals, an empty run inside a
series, a country with every value empty, one with history before 1991
only, one with values only after 2023, a series ending in 2015 (carried
eight years) and V-Dem's own identifiers. `generate_rights_cases.py` ran the
collect route's iterator with the legacy `SSPIRawAPIData` class over an
in-memory collection, the registered cleaners with the clock fixed to
2026-10-26 (and to 2024-06-30, recorded as `earlier_evaluation`), and the
`compute_*`/`impute_*` view functions with the legacy insert validation,
in four orders (`legacy_storage`). Five invalid variants record how legacy
failed (duplicate country-year, lowercase code and text value: refused by
the clean collection; missing column: `KeyError` in the cleaner; Latin-1
text: `UnicodeDecodeError` in the collector). The new backend matched every
record first time, with the existing `SeriesFillThenScore` (steps
`("forward",)`).

Live validation, 2026-10-26. The archive downloaded by
`VDemArchiveClient` is byte-identical to the pinned one. Run through the
pinned legacy collector, raw collection, cleaners and routes and through the
new backend (`test_golden_rights_real_data.py`, opt-in), every record is
identical (digests as for MURDER):

| Item | Records | Digest |
|---|---|---|
| `VDEM_RULELW` observations | 5,674 (179 V-Dem countries, 1991–2022; 0 empty) | `729743fe01b6f0b4eccfaf79db7b546e1c4a06a08332c53ec44daf554dbc806d` |
| `RULELW` observed scores | 5,674 | `40c3cc878d940fe6d726c2e73e3b5544530999351d68b26aac89385aa217c38b` |
| `RULELW` imputed scores | 179 (2023, carried one year) | `0f24d1a65ec1e5d0bfef4a8dc8745d093216c76f6874996c375f3dd44489c8f3` |
| `VDEM_EDEMOC` observations | 5,674 (179 V-Dem countries, 1991–2022; 0 empty) | `8386d4fbdb420db4f3d4a67847c3eef4ef0019024d3918f8fd4cf878ccd6e722` |
| `EDEMOC` observed scores | 5,674 | `6b17d57d717c096793d617bfc5ac2557ca9ed630749b7738ce0d9c9b2044749c` |
| `EDEMOC` imputed scores | 179 (2023, carried one year) | `1886b998588034fb7df5493b6b7fd40771d049c165d869db66f72b78391488ff` |

Every SSPI67 member is in v13 for every year 1991–2022; all 1,584 member-years
2000–2023 are scored for each indicator, 66 (2023) carried forward from 2022.
Illustrative 2022 scores (carried to 2023): RULELW 0.646 (MYS), 0.909 (AUT),
0.959 (USA); EDEMOC 0.438, 0.794, 0.819. This is the fixed v13 release, not
the current one: V-Dem v16 (March 2026, data to 2025) revises most past
values and was not used. The project owner decided on 2026-10-26 to keep
v13 for this migration; the edition question stays open (RULELW-2,
EDEMOC-2).

### Rights indicators not ported

**PUBSRV, UNCONV, GENDEQ: no executable implementation.** Each route file
holds one import (`sspi_flask_app/api/core/sspi/pg/rts/{pubsrv,unconv,gendeq}.py`)
and has held nothing else since it was created; no commit on any branch
ever held a compute or impute route for them, and their datasets
(`WGI_PUBSRV`, `UNSDG_UNCONV`, `IPU_WMPLMT`, `WBL_WMMOBL`, `WBL_WMMARR`,
`WBL_WMFNMN`) are documented but have no collector or cleaner (an unmerged
branch holds an IPU collector that cannot run). The 2018 static SSPI shows
what was once published: PUBSRV = (raw + 2.5) / 5 for 49 of 49 countries;
UNCONV = raw / 10, raw in thirds up to 10, although 12 instruments are
listed; GENDEQ = raw / 4, with no component values, so the described
weights cannot be checked. No golden output is manufactured from the
static values. Each entry lays out the decisions needed and a proposal for
review: PUBSRV-1, UNCONV-1, GENDEQ-1.

Status: Rights is partly migrated, 2 of 5 leaf indicators, and is not
complete. RULELW and EDEMOC have exact historical
parity (on invented data in the V-Dem layout and, opt-in, on the original
v13 archive) and run from an empty database; PUBSRV, UNCONV and GENDEQ are
blocked on methodology decisions; no category score is computed.

### How the Global Role fixtures relate to the legacy source

The Global Role category (`GLB`) has four leaf indicators in the canonical
metadata and the pinned methodology tree: `ARMEXP`, `MILEXP`, `RDFUND` and
`FORAID`. ARMEXP and RDFUND are migrated with exact parity; ARMEXP runs
observed-only on live data (approved execution treatment, ARMEXP-2 open). MILEXP and FORAID are
characterized and blocked. No Global Role category score is computed.

**ARMEXP** reads `SIPRI_ARMEXP` through `src/sspi/ingestion/sipri.py`: the
SIPRI Arms Transfers Database API, POSTed with the legacy collector's request
(delivered transfers, 1990–2025, exports by supplier), which answers
`{"result": "<csv text>"}`. The API serves the current database; there are
no editions to pin, so the request is recorded instead of a checksum. The
adapter reproduces the registered cleaner's pandas steps (the `Exports by,`
table, world-total rows dropped, year columns melted, empty cells dropped,
the skip list, the explicit Korea rules, the legacy matcher), plus one
approved SIPRI_ARMEXP-only name table, "Brunei" → BRN and
"Bosnia-Herzegovina" → BIH, for the two rows the cleaner dropped (ARMEXP-4;
the untouched legacy rows are kept in their own golden file). Scores:
`goalpost(SIPRI_ARMEXP, 500, 0)`, unit `Expenditure` (ARMEXP-1). ARMEXP runs
observed-only (approved execution treatment, see "Approved observed-only
executions"); the legacy impute route (forward to 2023, backward to 2000,
interpolation, then the all-row mean for ARE, BGD and IRQ) is preserved as
`armexp.LEGACY_IMPUTATION` and raises when a listed country has data
(ARMEXP-2). `tests/fixtures/sipri/armstransfers_synthetic.json` is
invented data in the SIPRI layout (GOV-7), written by
`tests/fixtures/sipri/build_synthetic.py`; `generate_global_role_cases.py` ran
the registered collector (with `requests.post` answering), the cleaner with
the clean collection's validation, and both routes; the new backend matched
every record first time.

**RDFUND** reads `UNSDG_RDPGDP` (`GB_XPD_RSDV`, SDG 9.5.1) and
`UNSDG_NRSRCH` (`GB_POP_SCIERD`, SDG 9.5.2) through the existing UN SDG
adapter (series codes recorded in PROVENANCE; one row per area, no
dimension). `tests/fixtures/unsdg/9_5_1_sample.json` and `9_5_2_sample.json`
are verbatim row subsets of the live responses of 2026-10-26 (World, Europe,
Austria, the United States, Malaysia, Peru, Israel, the Philippines, Egypt,
Nigeria, the Dominican Republic), like the other UN SDG samples. Scores: the
mean of `goalpost(UNSDG_RDPGDP, 0, 4)` and `goalpost(UNSDG_NRSRCH, 0, 5000)`;
impute: a new strategy, `SeriesFillInputsThenScore` in
`src/sspi/indicators/strategy.py`, for the route's shape (each dataset filled
on its own, observed rows scored with the fills, hard-coded reference classes
per dataset, the scores with an imputed input kept; RDFUND-1, RDFUND-2).

Live validation, 2026-10-26, every record identical between the pinned
legacy code and the new backend on the original answers (opt-in tiers
`sipri_real_data` and `unsdg_real_data`; digests as for MURDER):

| Item | Records | Digest |
|---|---|---|
| `SIPRI_ARMEXP` observations, legacy cleaner untouched | 1,569 (108 suppliers, 1990–2025) | `39bcc9795e8db5354a32cd191caa92b0c7781304a10483245730d02b0f08ab7b` |
| `ARMEXP` observed scores, legacy rows | 1,569 | `d2d9a0a9522011462d712689e759703441ccbc63ff6e0dd2e0f565829c48239e` |
| `SIPRI_ARMEXP` observations, with the ARMEXP-4 name table | 1,577 (110 suppliers; BIH 6, BRN 2 added) | `2d99ffd17b71f0e398530cb2b934fa6cc18371dc999640dcbcf714ab849581d7` |
| `ARMEXP` observed scores, observed-only run | 1,577 | `6f9696943aee38059ee45fd1e21edb420030b739efffec4d409af440c7661133` |
| `ARMEXP` imputed scores | none: the legacy route raised on the United Arab Emirates; the new backend runs observed-only (ARMEXP-2) | |
| `UNSDG_RDPGDP` observations | 2,212 (155 areas, 2000–2024) | `f0e07ddbd767c2bdedb831e65f92c7b20f98832e6428ac8ae17e82fdfc0c3c08` |
| `UNSDG_NRSRCH` observations | 1,793 (145 areas, 2000–2024) | `77547c524f49ac27ace80d4ddf4a547515c7fac581af0d781332122940cb1e90` |
| `RDFUND` observed scores | 1,719 (567 incomplete) | `8780251328c711612b473b090c713a59595010520da1069064b07d3d6a20a533` |
| `RDFUND` imputed scores | 1,763 (2000–2023) | `b720de83f5fbb32e9b40962724119fee5bdb5c1babd23d33fe6d12e477faf24e` |

SSPI67, 2000–2023: RDFUND scores all 1,584 member-years (1,109 observed);
ARMEXP has observed scores for 847 (unchanged by ARMEXP-4: neither Brunei nor
Bosnia and Herzegovina is a member), and 7 members never appear in SIPRI's
export table (ARMEXP-3). Illustrative: RDFUND 2022 = 0.248 (MYS), 0.897
(AUT), 0.930 (USA); ARMEXP 2023 = 0.992 (AUT), 0.0 (USA), Malaysia observed
only in 2013, 2014, 2019 and 2024.

### Global Role indicators not ported

**MILEXP: source approved and implemented, not registered (MILEXP-5).**
Executed with the pinned code on SIPRI's API answer, the legacy cleaner
stores every country's values 10 or 11 years after their year and drops or
misplaces six names (MILEXP-1); values of 1 or more are not scaled
(MILEXP-2); Iceland is a hard-coded zero and the 2018 scores used other
goalposts (MILEXP-3). That API still serves the Belarus 1992–2013 shares
SIPRI withdrew on 27 April 2026, and differs from the revised workbook in
196 values (MILEXP-4). The project owner approved, on 2026-10-26, the
header years and a SIPRI_MILEXP-only name table (MILEXP-1), converting
every fraction to percentage points with large values verified (MILEXP-2),
and SIPRI's revised workbook `SIPRI-Milex-data-1949-2025_v1.2.xlsx` as the
single source (MILEXP-4, option B). `src/sspi/ingestion/workbooks.py` is a
reusable pinned-workbook source (download from the official URL, or an
explicitly configured local copy; SHA-256 enforced); `normalize_milex_workbook`
reads the "Share of GDP" sheet, 1990–2024, with schema checks. Evidence in
three kinds, kept apart: (A) the legacy cleaner on the API answer, untouched
(`milexp_characterization_cases.json`); (B) the backend's reading of the
workbook against an independent reading in the generator, checked by the
legacy clean collection's validation (`milexp_workbook_synthetic_cases.json`;
this is not legacy parity: the legacy code never read the workbook); (C) the
pinned legacy compute and impute routes on the same rows. On the revised
workbook: 5,219 observations (167 countries, all SSPI67 members), 5,219
observed scores reproduced exactly; the legacy impute route completes with
424 imputed scores, but 24 of them are Iceland's fixed zero beside Iceland's
newly published zero for 2000–2023 (MILEXP-5). No precedence is decided, so
the backend refuses, MILEXP stays unregistered and `SIPRI_MILEXP` not
ingestible (`blocked_by` MILEXP-5). The other 400 imputed scores equal the
legacy route's.

**FORAID: no working implementation.** The compute route raises
`InvalidQueryError` before reading data, nothing collects its OECD and GDP
inputs, it has no impute route and it would write scores to the clean-data
collection (FORAID-1); its rule differs from the methodology (FORAID-2) and
its OECD query cannot express the methodology's measure (FORAID-3).
`tests/golden/foraid_characterization_cases.json` records the failure.

Status: Global Role is partly migrated, 2 of 4 leaf indicators registered
(ARMEXP observed-only, RDFUND), both running on today's live data; MILEXP's
source corrections are approved and implemented, but it stays unregistered
on the Iceland precedence decision MILEXP-5; FORAID is blocked; no category
score is computed.

## Proposed source-representation corrections

Repairs approved in principle by the project owner and implemented, whose
concrete transformation, affected rows and divergence from legacy are
reported for review but not yet confirmed. The dataset stays NOT
ingestible and the indicator NOT registered until the correction moves to
`APPROVED_SOURCE_CORRECTIONS`. Registered in `PROPOSED_SOURCE_CORRECTIONS`
(`tests/golden/parity.py`, `confirmed=False`); the gate checks that each is
unconfirmed, unregistered, recorded in its golden file and described in an
open entry. The untouched legacy output stays in its own characterization
file.

None at present: `SIPRI_MILEXP`'s correction (MILEXP-1) was confirmed on
2026-10-26 and moved to "Approved source-representation corrections".

## Approved source-representation corrections

A fourth situation, at the source rather than the route: the pinned legacy
cleaner runs, but its output cannot be stored, or is stored wrongly (rows of
countries it cannot name dropped, values under the wrong year, a unit
misread), and the project owner has approved a correction of the source's
representation. Imputation and scoring never change. Such a dataset is
registered in `APPROVED_SOURCE_CORRECTIONS` in `tests/golden/parity.py`,
with every approved correction, the conflict entries that record the
approval and whether the approval is confirmed. Its golden file records,
from executed legacy code, what the legacy cleaner did (`legacy_clean_error`
on the source or on a named variant, `legacy_dropped_rows`, or
`legacy_divergence`), the approved table (`approved_name_corrections`) and
the legacy cleaner's OWN rows with only that correction applied, which the
legacy clean collection's validation accepts; the indicator's golden scores
are the legacy routes' on those rows. The untouched legacy output keeps its
own golden file. The new backend must equal both exactly. A correction
`blocked_by` an unresolved entry keeps its dataset not ingestible and its
indicator unregistered until that entry is decided. The gate checks the
registration both ways, the recorded legacy behaviour, the table, the cited
entries and the block.

| Dataset | Conflict | Legacy failure | Approved correction |
|---|---|---|---|
| `ITU_CYBSEC` | CYBSEC-1 | five transcription names stay uncoded; the clean collection refuses the dataset | "Cote d'Ivoire" → CIV, "Macedonia" → MKD, "Micronesia" → FSM, "State of Palestine" → PSE, "Vatican" → VAT, only where the legacy matcher fails |
| `FSI_SECAPP` | SECAPP-1 | the pinned acquisition never stores a row; the cleaner's rows lack `DatasetCode`, names stay uncoded, North and South Korea are both KOR | dataset code set; surrounding whitespace stripped; "Cote d'Ivoire" → CIV, "Macedonia" → MKD, "Micronesia" → FSM, "Palestine" → PSE, "North Korea" → PRK, "South Korea" stays KOR (whitespace and North Korea confirmed 2026-10-26) |
| `SIPRI_ARMEXP` | ARMEXP-4 | the legacy matcher returns "Brunei" and "Bosnia-Herzegovina" unchanged; the cleaner drops their rows (8 on the answer of 2026-10-26) | "Brunei" → BRN, "Bosnia-Herzegovina" → BIH, SIPRI_ARMEXP only (2026-10-26) |
| `SIPRI_MILEXP` | MILEXP-1, MILEXP-2, MILEXP-4; blocked by MILEXP-5 (not ingestible) | every value stored 10 years late (51 countries) or 11 (110); "Brunei", "Gambia, The", "Cote d'Ivoire", "Congo, Republic" dropped (117 rows), "Korea, North" → KOR and "German Democratic Republic" → COD (0 rows today); fractions of 1 or more kept unscaled (23 values) | years from the header columns; "Brunei" → BRN, "Gambia, The" → GMB, "Cote d'Ivoire" → CIV, "Congo, Republic" → COG, "Korea, North" → PRK, "German Democratic Republic" kept out; every fraction × 100, a fraction of 1 or more only where verified (Kuwait 1991); SIPRI's revised workbook (v1.2, revised 2026-04-27, SHA-256 `6cc3a30b…9a9d`), 1990–2024, as the single source instead of the API; SIPRI_MILEXP only (2026-10-26) |

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

## Inoperative legacy impute routes

A third situation: the legacy impute route exists but raises on **every**
input, whatever the data, so the legacy backend never stored an imputed
score for the indicator. The route deletes the stored imputations first,
then fails. Nothing is replaced and nothing is chosen. The new backend
stores what legacy stored: the compute route's scores and no imputed
score, by having no imputation strategy. The golden file records the
failure at the top level (`legacy_impute_error`), with the route's queries
and the exception, on three states: the committed fixture, an empty
dataset, and a probe written in the schema the route was written for. Such
an indicator is registered in `INOPERATIVE_IMPUTE_ROUTES` in
`tests/golden/parity.py`, pointing at an unresolved entry that lays out the
options for the methodology team ("Potential direction A/B") without
adopting one. The gate checks the registration both ways, the three
recorded failures, that the definition imputes nothing, and the entry.
Exact parity is required on everything the compute route produces.

The project owner approved this treatment for FDEPTH on 2026-10-19 as a
narrowly scoped, evidence-backed exception: `run("FDEPTH")` stores observed
scores only, does not raise because the legacy route was inoperative, and
neither repairs nor emulates the intended imputation. The register is not
to be used for an indicator whose observed and imputed legacy behaviour has
not been independently characterized from the pinned code. FDEPTH-1 stays
unresolved: the methodology question (whether and how to impute) is open.

| Indicator | Conflict | Why the route always fails | Stored by legacy, and by the new backend |
|---|---|---|---|
| `FDEPTH` | FDEPTH-1 | it reads clean data by `IndicatorCode` and slices `CREDIT` / `DPOSIT` out of a `Datasets` list that clean rows never have, so the hard-coded GBR reference class gets no data and raises `ValueError: Reference data cannot be empty.` | observed scores only |

## Approved observed-only executions

A fifth situation: the legacy impute route works on the committed fixture
(exact parity required there) but fails on the CURRENT source data, so that a
live legacy run stored the compute route's scores only. Where the project
owner approves it, the registered definition has no imputation strategy
(the FDEPTH precedent): a live run stores the observed scores, and no imputed
score is attempted, stored, or shown as observed or as zero. The legacy route
is kept, unregistered, and its golden test requires exact parity on
collision-free inputs and the legacy failure on a probe of the current
situation. Registered in `OBSERVED_ONLY_EXECUTIONS` in
`tests/golden/parity.py`; the gate checks the registration both ways, the
working route on the fixture, the probe, the preserved strategy, the
confirmation, the register row and the unresolved entry.

| Indicator | Conflict | Why the live legacy imputation fails | Preserved legacy route | Stored by the new backend |
|---|---|---|---|---|
| `ARMEXP` | ARMEXP-2 | the United Arab Emirates, hard-coded for the all-exporter mean, now exports; legacy refused all imputation | `sspi.indicators.armexp.LEGACY_IMPUTATION` | observed scores only (1,577 on the answer of 2026-10-26, 8 of them restored by ARMEXP-4) |

## Approved storage corrections

A fourth situation: the legacy impute route completes and computes
consistent scores, but clears `sspi_imputed_data` and inserts them into
`sspi_indicator_data`, the observed collection. Only RULELW and EDEMOC do
this in the pinned repository. The golden file records it from executed
legacy code (`impute_route_inserts_into`, and in `legacy_storage` what each
collection held after compute then impute, after a second impute, after a
second compute, and after impute then compute): the carried scores sit
among the observed ones, a second impute run holds each of them twice, a
later compute run erases them. Legacy readers label them observed (the
dynamic line's `source: "real"`), although each row's input is marked
`Imputed`.

One compute-then-impute pass holds no identity twice, so exact parity is
required on both routes' scores. The project owner approved a storage and
provenance correction on 2026-10-26: the forward-carried scores are stored
as imputed scores, with their exact legacy values and the source year they
are carried from (`anchor_year`; 2022 on V-Dem v13), idempotently: a run
replaces every score of the indicator, so the duplicates and the erasure
are not reproduced. It is not a new scoring formula and not an imputation
policy. Each indicator is registered in `APPROVED_STORAGE_CORRECTIONS` in
`tests/golden/parity.py` with the treatment and the confirmed approval,
citing the resolved entry that records the decision and an UNRESOLVED
entry that keeps the broader question (whether to impute at all, how far,
and how a carried score should count) open for the methodology team. The
gate checks the registration both ways against the golden files, the
recorded storage states, the imputed inputs, the confirmation and both
entries.

| Indicator | Approved correction | Open question | What the legacy route writes | Stored by the new backend |
|---|---|---|---|---|
| `RULELW` | RULELW-1 | RULELW-3 | each V-Dem series carried forward to 2023, into `sspi_indicator_data` | the same scores, flagged imputed, source year kept, once per run |
| `EDEMOC` | EDEMOC-1 | EDEMOC-3 | the same, for `v2x_polyarchy` | the same scores, flagged imputed, source year kept, once per run |

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
scores via `regression_impute_scores`), `CstuntImputation` (CSTUNT: the
`SeriesFillThenScore` fill, then the same regression on goalposted GDP per
capita, an auxiliary dataset), `SeriesFillThenScore` (EMPLOY,
COLBAR, PUPTCH, ENRPRI, YRSEDU, CRPTAX, PHYSPC: forward, backward and interpolated fill of the one
input, or the steps the legacy route used (YRSEDU backward only, CRPTAX backward then
interpolated), no reference class; with `listed_recipients`, ENRSEC, TAXREV, UNEMPB and ATBRTH: the
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
`None` for REDLST, CHMPOL, NITROG, ISHRAT, MSWGEN, TXRDST, FATINJ and DPTCOV.
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
