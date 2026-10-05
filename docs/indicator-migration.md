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

| Indicator | Variant | Conflict | Legacy behaviour | Current behaviour | Parity variant |
|---|---|---|---|---|---|
| `DEFRST` | `fixture_as_committed` | DEFRST-1 | stores observed and imputed scores for ARE 2000–2022 and two imputed scores for ARE 2023 | `run("DEFRST")` raises; nothing written | `without_are_source_rows` |
| `CARBON` | `fixture_as_committed` | CARBON-1 | stores observed and imputed scores for KWT 2000–2023 | `run("CARBON")` raises; nothing written | `without_kwt_source_rows` |

The parity variants are the committed fixture with that recipient's level
rows removed, the source state the hard-coded recipient lists were written
against. On them both legacy routes run consistently and exact parity holds
on every dimension. On live FAO data both indicators currently stop.

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
COLBAR: forward, backward and interpolated fill of the one input, no
reference class); `None` for REDLST, CHMPOL, NITROG and ISHRAT.
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
  (WATMAN-3) is not approval for another.
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
