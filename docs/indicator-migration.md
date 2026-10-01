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
   field) in `src/sspi/metadata/data/PROVENANCE.yaml` under `edits`, and in
   `scripts/import_legacy_metadata.py`.
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

### Indicators

| Indicator | Golden file | Parity tests | Imputes | Conflicts |
|---|---|---|---|---|
| BIODIV | `biodiv_imputation_cases.json` | `test_golden_biodiv_orchestration.py`, `test_golden_imputation.py` | yes | BIODIV-1, BIODIV-2, BIODIV-3, BIODIV-4, BIODIV-5 |
| REDLST | `redlst_cases.json` | `test_golden_redlst.py` | no | REDLST-1 |
| CHMPOL | `chmpol_cases.json` | `test_golden_chmpol.py` | no | CHMPOL-1, CHMPOL-2 |
| WATMAN | `watman_cases.json` | `test_golden_watman.py` | yes | WATMAN-1, WATMAN-2, WATMAN-3 |

### In progress (not executable yet)

| Indicator | Blocker | Evidence already committed | Conflicts |
|---|---|---|---|
| NITROG | no EPI adapter; legacy download URL no longer serves a zip | none: no legacy or source fixture is obtainable offline | none found |
| DEFRST | no FAO adapter (API now requires authorization); derived 1990s-average dataset; score-level imputation | none | DEFRST-1, DEFRST-2 |
| CARBON | no FAO adapter; derived 1990s-average dataset | none | CARBON-1 |

## Intentional divergences

The parity rule has one qualified exception. Where the pinned legacy route
itself cannot produce a result on the committed fixture (it raises), the
golden file records the failure (`legacy_impute_error`) and the new backend
may apply a documented policy instead. Such a case is registered in
`INTENTIONAL_DIVERGENCES` in `tests/golden/parity.py`, keyed by indicator
and variant, pointing at the `methodology-conflicts.md` entry that states
the literal legacy behaviour, why it fails, the magnitude of the difference
and the adopted policy. The gate checks that every recorded legacy failure
is registered, that every registration corresponds to one, and that the
cited entry states an implementation policy. A registered divergence is not
parity and is never described as such; exact parity is still required on
every variant the legacy route completes.

| Indicator | Variant | Conflict | Legacy failure | Policy |
|---|---|---|---|---|
| `WATMAN` | `fixture_as_committed` | WATMAN-3 | duplicate CWUEFF rows for Singapore | canonical CWUEFF first; reference-class fallback only when none exists |

## Imputation strategies

An indicator's legacy impute route is an `ImputationStrategy`
(`sspi.indicators.strategy`): a pure object that declares the auxiliary
datasets and the country group it needs, and turns the observed pass into
imputed scores. The runner is indicator-agnostic. Strategies in use:
`ImputeInputsThenScore` (BIODIV), `WatmanImputation` (WATMAN); `None` for
REDLST and CHMPOL. A score imputed at score level (planned for DEFRST)
carries its own `IndicatorScore.provenance`, persisted in
`indicator_score.provenance` (migration 0003); the `imputed` flag is derived
from that provenance or from an imputed input, never supplied.

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

## Known limits of the current evidence

- Fixtures are subsets of the source: five countries plus two regional
  aggregates per query. They prove the implementations agree on those rows,
  including missing values, skipped areas and a country with no marine
  series. They do not exercise every country.
- BIODIV has a second variant with Malaysia's marine series thinned, so that
  interpolation and extrapolation are exercised inside the indicator.
  The UN data itself has no gaps of that kind today.
- Parity covers cleaning, imputation and scoring. Legacy finalization and
  aggregation are not migrated and not compared.
- Legacy stored incomplete groups in their own collection. The new backend
  returns the same identities from a run (`IndicatorRun.unscored`) and the
  parity tests compare them, but does not store them yet.
