# Methodology conflicts and questions for review

This file records methodology questions found while migrating indicators
from the legacy backend (`sspi-data-webapp`). It is written for maintainers,
methodology reviewers and research leads.

**These are open questions, not necessarily bugs.** In every case the new
backend reproduces what the legacy executable code does. An entry means the
legacy sources disagree with each other, or the executable behaviour is
reproducible but deserves a deliberate decision.

## What belongs here, and what does not

| Kind of finding | Where it is recorded |
|---|---|
| Executable behaviour disagrees with methodology text, static metadata or published scores | here |
| Imputation or missing-data treatment that is undocumented, inconsistent or questionable | here |
| Legacy readers that disagree with each other on precedence | here |
| Wrong source identifier in legacy metadata, a value stored in the wrong field, a renamed key | `src/sspi/metadata/data/PROVENANCE.yaml` (`edits`) |
| Legacy capability not yet rebuilt (for example storing incomplete groups) | the module docstring that defers it; it is not a methodology question |
| Architecture differences (PostgreSQL, one score row per identity, DataFrames) | not recorded; they change representation only |

## Rules for this file

- One entry per question, with a stable ID (`CODE-n`). IDs are never reused.
- `Status` is one of `unresolved`, `reviewed`, `resolved`.
  - `unresolved`: nobody with methodology authority has decided.
  - `reviewed`: a reviewer has looked and the entry records who, when and what was said, but the code does not yet reflect a final decision.
  - `resolved`: a decision exists **and** the entry cites it in a `Resolution evidence:` section (decision record, commit, updated methodology text). Never mark an entry resolved without it; the test suite rejects it.
- The new backend preserves executable legacy behaviour until an entry is resolved. Resolving an entry that changes scores is a methodology change, made in its own commit with the golden fixtures updated and the reason stated.
- Impact figures state which data they come from. Figures marked *live, illustrative* come from the UN SDG API on the stated date and show magnitude only; they are not parity evidence.

Legacy paths are relative to `sspi-data-webapp` at the pinned commit
`76f842b08e551dfa8fb9563e4c812be086654ba6`.

## Index

| ID | Title | Status |
|---|---|---|
| BIODIV-1 | Countries with no marine or freshwater series: omit the component or impute it | unresolved |
| BIODIV-2 | Composition of the reference-class average | unresolved |
| BIODIV-3 | Observed and imputed scores use different formulas | unresolved |
| BIODIV-4 | Legacy readers disagree on observed-versus-imputed precedence | unresolved |
| BIODIV-5 | Observed scores cover more years than imputed scores | unresolved |
| REDLST-1 | Historical goalpost discrepancy | unresolved |
| CHMPOL-1 | The Rotterdam dataset is populated from the Stockholm series | unresolved |
| CHMPOL-2 | Methodology text, indicator goalposts and executable formula disagree | unresolved |
| WATMAN-1 | Change-in-water-use-efficiency goalposts: (−25, 50) in static metadata, (−20, 50) executable | unresolved |
| WATMAN-2 | Imputation recipients are hard-coded lists and the synthetic CWUEFF method is undocumented | unresolved |
| WATMAN-3 | The legacy impute route fails on current source data: Singapore now has a derived CWUEFF series | unresolved |
| DEFRST-1 | Imputation of indicator scores for a hard-coded country list | unresolved |
| DEFRST-2 | The 1990s-average datasets behave differently and the methodology text drops the ×100 | unresolved |
| CARBON-1 | Reference-class imputation of both inputs for a hard-coded country list | unresolved |
| NITROG-1 | The current EPI edition may not be methodologically identical to the historical EPI source | unresolved |
| CARBON-2 | Historic FAO entities enter the legacy reference-class means; canonical M49 geography skips them | unresolved |
| DEFRST-3 | Historic FAO entities and the Sudan series under canonical M49 geography | unresolved |
| GINIPT-1 | The World Bank Gini series mixes income-based and consumption-based surveys and is not specifically "after taxes" | unresolved |
| GINIPT-2 | The 2018 static GINIPT values for some countries do not come from the World Bank series | unresolved |
| GINIPT-3 | GINIPT imputation and prediction cover more years than the usual 2000–2023 window | unresolved |

---

## BIODIV-1 — Countries with no marine or freshwater series: omit the component or impute it

Status: unresolved

Current executable behavior:
- A country in SSPI67 with no rows at all for a dataset receives the reference-class average (see BIODIV-2) for that dataset, for every year 2000 to 2023.
- The score then averages all three components: `(marine + terrestrial + freshwater) / 3 / 100`.
- There is no concept of a landlocked country anywhere in executable code.

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv` (retired static metadata), BIODIV description: "For landlocked countries, marine percentage is omitted from the average."
- `local/SSPIStaticData2018.csv` (published 2018 static scores) is consistent with omission: Austria's raw value is 69.282, close to the mean of its terrestrial and freshwater values and far from any three-component average.
- `methodology/sus/eco/biodiv/methodology.md` says "Arithmetic average of three measures" and has no imputation section and no landlocked rule.
- `local/2025-06-25-indicator-status.json` marks BIODIV "Finalization in Progress" with the note "Source data on landlocked countries. Run imputations based on landlocked countries", which suggests the treatment was still being decided.

Implementation decision in the new backend:
- Preserve the executable behaviour: impute and average three. No landlocked-specific code exists.

Reason:
- The executable route is the only source that is unambiguous and reproducible. The documents disagree with each other, so choosing between them would be a methodology decision.

Potential impact:
- Material for every affected country. In current UN data the SSPI67 members with no marine series are exactly the seven landlocked members: AUT, CHE, CZE, ETH, HUN, LUX, SVK. KWT and SGP have no freshwater series and are treated the same way.
- 2018 scores, *live, illustrative* (UN SDG API, 2026-09-29):

  | Country | Executable (impute, average three) | Omit marine (average two) |
  |---|---|---|
  | AUT | 0.5913 | 0.6958 |
  | CHE | 0.4473 | 0.4798 |
  | CZE | 0.7511 | 0.9355 |
  | ETH | 0.2377 | 0.1654 |
  | HUN | 0.6962 | 0.8531 |
  | LUX | 0.5136 | 0.5793 |
  | SVK | 0.6997 | 0.8584 |

- The imputed marine value pulls high scorers down and low scorers up, toward the global marine mean.
- In the committed test fixture (four countries with marine data) Austria 2020 is 0.5858737782051282 with an imputed marine value of 36.56867346153846.

Question for methodology review:
- Should a country with no marine sites be scored on two components, or on three with an imputed marine value? Is the answer the same for a country with no freshwater series (KWT, SGP)?
- If omission is intended, is "landlocked" the criterion, or "no series at the source"? They coincide today but are different rules.

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/eco/biodiv.py` (`impute_biodiv`)
- `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`)
- `methodology/sus/eco/biodiv/methodology.md`
- `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/biodiv.py`
- `src/sspi/indicators/runner.py` (`compute_indicator`)
- `src/sspi/imputation.py` (`impute_dataset`, `reference_class_average`)
- `tests/golden/biodiv_imputation_cases.json` (`methodology_conflict`), `tests/golden/test_golden_biodiv_orchestration.py`

---

## BIODIV-2 — Composition of the reference-class average

Status: unresolved

Current executable behavior:
- The reference-class average for a dataset is the plain mean of **every** clean observation of that dataset: all countries the source reports, not only SSPI67, and all years the source reports, including 2024 and 2025, which are outside the 2000 to 2023 imputation window.
- One constant value is used for every imputed year. It does not vary over time.
- The SSPI67 group decides only which countries receive the value, not which countries contribute to it.
- Each observation has equal weight, so countries with longer series weigh more.

Conflicting evidence:
- The legacy function is named and documented as a "reference class" average, which suggests a defined comparison group. No document defines the class. The executable class is "everything the cleaner kept".
- No methodology text describes this imputation at all.

Implementation decision in the new backend:
- Preserve the executable behaviour exactly. The number of contributing observations is stored in each imputed value's provenance (`reference_observation_count`).

Reason:
- Any narrower class (SSPI67 only, within-window only, per-year) would be a new methodological choice.

Potential impact:
- Marine, *live, illustrative* (UN SDG API, 2026-09-29): mean over all 4,966 observations is 38.23; restricted to SSPI67 and 2000 to 2023 it would be 44.68 (1,416 observations); restricted to the year window only, 37.52.
- A 6.4-point difference in the marine component is about 0.02 in the BIODIV score of each affected country.
- Because the mean includes future source revisions and new years, imputed scores for past years change whenever the source adds data for any country.

Question for methodology review:
- What is the intended reference class: all reporting countries, SSPI67, or a regional or income peer group?
- Should the average be per year, so imputed values follow the global trend?
- Should years outside the scoring window contribute?

Relevant legacy files:
- `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`)
- `sspi_flask_app/api/core/sspi/sus/eco/biodiv.py` (`impute_biodiv`, which passes the unfiltered clean list as `ref_data`)

Relevant new-backend files:
- `src/sspi/imputation.py` (`reference_class_average`)
- `tests/golden/imputation_cases.json` (`reference_cases`), `tests/golden/test_golden_imputation.py`

---

## BIODIV-3 — Observed and imputed scores use different formulas

Status: unresolved

Current executable behavior:
- Observed scores (legacy compute route): `(goalpost(F, 0, 100) + goalpost(T, 0, 100) + goalpost(M, 0, 100)) / 3`. Each component is clamped to [0, 1] before averaging.
- Imputed scores (legacy impute route): `(M + T + F) / 3 / 100`. Nothing is clamped.
- The two agree, up to floating-point summation order, whenever all three inputs are inside [0, 100]. They differ for an input outside that range.

Conflicting evidence:
- `methodology/sus/eco/biodiv/methodology.md` gives one formula, the goalposted one, for the indicator.
- The impute route defines its own function with the same name and a different body.

Implementation decision in the new backend:
- Keep both formulas verbatim, including summation order: `score_biodiv_observed` and `score_biodiv_imputed`.

Reason:
- Collapsing them would change imputed scores at the last floating-point digit today, and more if an out-of-range value ever appears.

Potential impact:
- None on interpretation today: no source value is outside [0, 100] (*live*, 2026-09-29, 15,496 observations checked), and linear interpolation or flat extrapolation of in-range values stays in range.
- Latent: an out-of-range source value would be clamped for observed scores and not for imputed ones.

Question for methodology review:
- Is the unclamped formula intentional, or should the impute route use the documented goalposted formula?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/eco/biodiv.py` (`compute_biodiv.score_biodiv`, `impute_biodiv.score_biodiv`)

Relevant new-backend files:
- `src/sspi/indicators/biodiv.py`
- `tests/unit/test_biodiv_formulas.py`, `tests/golden/biodiv_imputation_cases.json` (`score_function`, `observed_score_function`)

---

## BIODIV-4 — Legacy readers disagree on observed-versus-imputed precedence

Status: unresolved

Current executable behavior (legacy):
- Observed and imputed scores live in separate collections. Each route clears and rewrites only its own, so rerunning one route can leave the other stale, and the same (indicator, country, year) can then exist in both.
- When that happens, legacy readers behave differently: the dynamic line finalizer and the dashboard prefer the observed score; `finalize_sspi_dynamic_score_iterator` unions both collections and the `SSPI` model then raises `DataMetadataMismatchError` because it receives more scores than indicators.
- On a single consistent snapshot the two sets are exact complements and the question does not arise (committed fixture: 78 observed, 48 imputed, 0 shared identities).

Conflicting evidence:
- No document states which score wins. Two readers choose observed; one fails.

Implementation decision in the new backend:
- One score row per (indicator, country, year). A run replaces the indicator's whole score set, so stale rows cannot survive. Where both could exist, observed takes precedence over imputed; this is enforced in the database write.
- The project owner approved this as the architecture for the port. It has not been reviewed as methodology.

Reason:
- It matches the majority legacy behaviour and makes the failure case impossible.

Potential impact:
- None on a consistent snapshot. It matters only to anyone comparing against a legacy database that was in a torn state.

Question for methodology review:
- Confirm that an observed score always supersedes an imputed one for the same country and year.

Relevant legacy files:
- `sspi_flask_app/api/core/finalize.py` (`finalize_dynamic_line_indicator_datasets`, `finalize_sspi_dynamic_score_iterator`)
- `sspi_flask_app/api/core/dashboard.py`
- `sspi_flask_app/models/sspi.py` (`DataMetadataMismatchError`)

Relevant new-backend files:
- `src/sspi/db/repository.py` (`save_scores`, `replace_indicator_scores`)
- `src/sspi/indicators/runner.py`
- `tests/db/test_score_precedence.py`

---

## BIODIV-5 — Observed scores cover more years than imputed scores

Status: unresolved

Current executable behavior:
- The compute route scores every year the source reports, with no year filter. Today that is 2000 to 2025.
- The impute route fills 2000 to 2023 only.
- So a country with complete source data has scores for 2024 and 2025, and a country that depends on imputation does not.
- Legacy readers apply a 2000 to 2023 window at read time, which hid the difference in the legacy application.

Conflicting evidence:
- No document defines the scoring window. The bound exists only as literals in the impute route and in the finalizers.

Implementation decision in the new backend:
- Preserve both behaviours. `query()` applies no hidden year window, so the asymmetry is visible: pass `years=(2000, 2023)` to reproduce the legacy view.

Reason:
- Dropping 2024 and 2025 observed scores, or extending imputation, would each change the stored result.

Potential impact:
- Cross-country comparisons for 2024 or 2025 silently exclude every country that depends on imputation: nine SSPI67 members in current UN data (the seven in BIODIV-1, plus KWT and SGP).

Question for methodology review:
- Is 2000 to 2023 the official scoring window? If so, should observed scores outside it be stored at all? How is the window meant to advance?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/eco/biodiv.py`
- `sspi_flask_app/api/core/finalize.py` (year bounds)

Relevant new-backend files:
- `src/sspi/indicators/registry.py` (`LEGACY_IMPUTATION_YEARS`)
- `src/sspi/indicators/runner.py`
- `tests/db/test_biodiv_run.py`

---

## REDLST-1 — Historical goalpost discrepancy

Status: unresolved

Current executable behavior:
- goalposts: (0, 1)
- formula: `goalpost(UNSDG_REDLST, 0, 1)`
- no imputation; every year the source reports is scored

Conflicting evidence:
- `methodology/sus/eco/redlst/methodology.md` says `LowerGoalpost: 0`, `UpperGoalpost: 1`, `Score = goalpost(UNSDG_REDLST, 0, 1)`. The executable route reads its goalposts from this file at runtime.
- `local/IndicatorDetailsStatic.csv` says `GoalpostString "(0, 1)"`, lower 0, upper 1.
- `local/SSPIStaticData2018.csv` (published 2018 static scores) behaves as though the goalposts were (0.5, 1): all 49 rows satisfy `score = (raw - 0.5) / 0.5`, and none satisfies `score = raw`. Example: Austria raw 0.89, score 0.780.

Implementation decision in the new backend:
- Preserve the executable (0, 1). The definition declares its goalposts and every run checks them against the canonical metadata, so code and metadata cannot drift apart silently.

Reason:
- Executable route, methodology file and static metadata agree. Only the historical published scores disagree, and nothing documents why.

Potential impact:
- Material. With (0, 1) the score equals the index value; with (0.5, 1) it is `2 x value - 1`, floored at 0. Differences between countries double.
- On the committed fixture, Austria 2018: 0.95597 with (0, 1), 0.91194 with (0.5, 1). Malaysia 2018: 0.83317 against 0.66634.
- *Live, illustrative* (UN SDG API, 2026-09-29): scores range from 0.40526 to 1.0 with (0, 1). Under (0.5, 1), 110 observations from four non-SSPI67 territories (CXR, GUM, KNA, MUS) would score 0.
- The 2018 static raw values are also a different source vintage (Austria 0.89 then, 0.95597 now), so the two files cannot be compared value by value.

Question for methodology review:
- Was (0.5, 1) an earlier methodology that was deliberately replaced, or were the 2018 scores computed inconsistently with the documented goalposts?
- Which goalposts should published REDLST scores use?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/eco/redlst.py` (`compute_redlst`)
- `methodology/sus/eco/redlst/methodology.md`
- `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/redlst.py`
- `src/sspi/indicators/registry.py` (`IndicatorDefinition.goalposts`, `check_against`)
- `tests/golden/redlst_cases.json` (`historical_discrepancy`), `tests/golden/test_golden_redlst.py`

---

## CHMPOL-1 — The Rotterdam dataset is populated from the Stockholm series

Status: unresolved

Current executable behavior:
- The legacy `UNSDG_ROTDAM` cleaner maps `SG_HAZ_CMRSTHOLM` (Stockholm Convention) to `UNSDG_ROTDAM`.
- CHMPOL therefore averages the Stockholm percentage twice and never uses Rotterdam Convention data, although the source publishes `SG_HAZ_CMRROTDAM` (204 areas, live 2026-10-01).

Conflicting evidence:
- `datasets/unsdg/unsdg_rotdam/documentation.md`: "Rotterdam Convention on the prior informed consent procedure for certain hazardous chemicals and pesticides in international trade."
- `methodology/sus/lnd/chmpol/methodology.md` lists `UNSDG_ROTDAM` as one of five distinct conventions.
- The status note calls CHMPOL the successor to STKHLM "adding Montreal Convention and others, available from the same dataset".

Implementation decision in the new backend:
- Reproduce the executable mapping. `UNSDG_ROTDAM.yaml` carries `organization_series_code: SG_HAZ_CMRSTHOLM` with a note pointing here; the correction record in `PROVENANCE.yaml` says the same.

Reason:
- Approved by the project owner on 2026-10-01: preserve executable behaviour for this port and record the discrepancy rather than silently correct it.

Potential impact:
- Material for every scored country-year. On the committed fixture, Austria 2020 is 0.6476 with the Stockholm value counted twice (28.57); with the Rotterdam value (96.55) in its place it would be 0.7836.
- Rotterdam has fewer reporting areas than Stockholm (204 vs 223), so switching would also change which country-years are complete.

Question for methodology review:
- Should `UNSDG_ROTDAM` select `SG_HAZ_CMRROTDAM`? If so, the change alters scores and the golden fixtures must be regenerated with the decision recorded.

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unsdg/unsdg_rotdam.py` (`idcode_map`)
- `sspi_flask_app/api/core/sspi/sus/lnd/chmpol.py` (`compute_chmpol`)
- `datasets/unsdg/unsdg_rotdam/documentation.md`, `methodology/sus/lnd/chmpol/methodology.md`

Relevant new-backend files:
- `src/sspi/metadata/data/datasets/UNSDG_ROTDAM.yaml`, `src/sspi/metadata/data/PROVENANCE.yaml`
- `src/sspi/indicators/chmpol.py`
- `tests/golden/unsdg_rotdam_cases.json`, `tests/golden/chmpol_cases.json`, `tests/unit/test_chmpol.py`

---

## CHMPOL-2 — Methodology text, indicator goalposts and executable formula disagree

Status: unresolved

Current executable behavior:
- `(STKHLM + MINMAT + MONTRL + BASELA + ROTDAM) / 5 / 100`. No `goalpost` call, no clamping.

Conflicting evidence:
- `methodology/sus/lnd/chmpol/methodology.md` `ScoreFunction`: `average(goalpost(x, 0, 1), ...)` for the five datasets. The inputs are percentages in [0, 100], so that text, taken literally, would clamp every score to 1.
- The same file gives indicator goalposts `LowerGoalpost: 0.0`, `UpperGoalpost: 100.0`, which the executable route never reads.
- The executable `/ 100` equals `goalpost(x, 0, 100)` only while inputs stay inside [0, 100], which they do today.

Implementation decision in the new backend:
- Keep the executable formula verbatim. No goalposts are declared on the definition, because the executable formula applies none.

Reason:
- Executable behaviour is unambiguous; the text is internally inconsistent.

Potential impact:
- None on today's data. Latent: an input outside [0, 100] would not be clamped.

Question for methodology review:
- Is the intended formula the mean of five `goalpost(x, 0, 100)` terms? If so the text should be corrected and the definition should declare (0, 100) so the runtime check covers it.

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/chmpol.py`, `methodology/sus/lnd/chmpol/methodology.md`

Relevant new-backend files:
- `src/sspi/indicators/chmpol.py`, `src/sspi/metadata/data/indicators/CHMPOL.yaml`

---

## WATMAN-1 — Change-in-water-use-efficiency goalposts: (−25, 50) in static metadata, (−20, 50) executable

Status: unresolved

Current executable behavior:
- `(goalpost(UNSDG_CWUEFF, −20, 50) + goalpost(UNSDG_WTSTRS, 100, 0)) / 2`, identical in the compute and impute routes.
- `UNSDG_CWUEFF` is the percent change of water-use efficiency from the country's 2000–2005 mean, from 2006 on (derived in `sspi.ingestion.derived`).

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv` and `local/IntermediateDetailsStatic.csv`: CWUEFF goalposts (−25, 50), with the intermediate marked "Inverted: TRUE" and the indicator "Inverted: true".
- `methodology/sus/lnd/watman/methodology.md` and the executable route: (−20, 50), not inverted; the description also says "2018 compared with 2010-2015 average" while the executable baseline is 2000–2005.
- The status note ("Temporarily finalized") questions whether a 5- or 10-year lag should replace the level-based change.

Implementation decision in the new backend:
- Preserve (−20, 50) and the 2000–2005 baseline.

Reason:
- Executable route and current methodology file agree; the static files are retired.

Potential impact:
- Moving the lower goalpost from −20 to −25 changes every CWUEFF component by up to 0.067 of its [0, 1] range, and the WATMAN score by half of that.

Question for methodology review:
- Confirm (−20, 50) and the 2000–2005 baseline; correct the description text.

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/watman.py`, `sspi_flask_app/api/core/datasets/unsdg/unsdg_cwueff.py`
- `methodology/sus/lnd/watman/methodology.md`, `local/IndicatorDetailsStatic.csv`, `local/IntermediateDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/ingestion/derived.py`, `src/sspi/metadata/data/datasets/UNSDG_CWUEFF.yaml`
- `tests/golden/watman_cases.json`, `tests/golden/test_golden_watman.py`

---

## WATMAN-2 — Imputation recipients are hard-coded lists and the synthetic CWUEFF method is undocumented

Status: unresolved

Current executable behavior (legacy impute route):
- CWUEFF and WTSTRS are extrapolated backward to 2000 and forward to 2023 (no interpolation).
- For twelve hard-coded countries (`AUS, BGD, CAN, CHE, CHL, DEU, ISL, LVA, PER, PHL, SVN, THA`) a synthetic CWUEFF series is built from `UNSDG_WUSEFF`: extrapolate and interpolate WUSEFF over 2000–2023, then apply the same 2000–2005 baseline-change transform, this time including the baseline years themselves.
- Singapore (`SGP`) receives the mean of every clean CWUEFF observation (all countries and years).
- Which countries get which treatment is a literal list in the route, not a rule derived from a group or from missing data.

Conflicting evidence:
- No methodology text describes any of this. The comment in the route says the twelve "miss CWUEFF but have WUSEFF", which is a property of the data at the time the list was written, not a rule.

Implementation decision in the new backend:
- Reproduced exactly, lists included, in `WatmanImputation` (`src/sspi/indicators/watman.py`). Parity with the legacy impute route is exact on the committed fixture variant where it runs (78 imputed scores).

Reason:
- Reproducing a hard-coded list is the only faithful option; deriving the list from the data would change results whenever the source changes.

Potential impact:
- Thirteen SSPI67 countries receive imputed WATMAN scores for every year 2000–2023. In current UN data the twelve listed countries are exactly the SSPI67 members that report water-use efficiency without any 2000–2005 value, so the list still describes the data; Singapore no longer does (WATMAN-3).

Question for methodology review:
- Should recipients be derived from a rule (SSPI67 members without CWUEFF data), and is the synthetic-from-WUSEFF method the intended one?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/watman.py` (`impute_watman`, `create_synthetic_cwueff`)

Relevant new-backend files:
- `src/sspi/indicators/watman.py`, `src/sspi/metadata/data/datasets/UNSDG_WUSEFF.yaml`
- `tests/golden/watman_cases.json`, `tests/golden/test_golden_watman.py`, `tests/unit/test_watman.py`

---

## WATMAN-3 — The legacy impute route fails on current source data: Singapore now has a derived CWUEFF series

Status: unresolved

Current executable behavior (literal legacy):
- The impute route adds a reference-class CWUEFF series for `SGP` unconditionally (the mean of every canonical CWUEFF value, all countries and years, for 2000–2023), on top of extrapolating every canonical CWUEFF series backward to 2000 and forward to 2023.
- When the route was written, Singapore had water-use-efficiency rows but none in 2000–2005, so no canonical CWUEFF existed for it and the two never met.

Conflicting evidence:
- Why it now fails: Singapore's series at the UN source now starts in 2005. The 2000–2005 baseline therefore exists (one value), the derived `UNSDG_CWUEFF` includes SGP from 2006, and its backward extrapolation reaches 2000. The reference-class series collides with it for every year 2000–2023, and the legacy `score_indicator` raises `InvalidDocumentFormatError: Duplicate dataset document found`.
- Verified by running the legacy `impute_watman` function itself on the committed fixture (`tests/golden/watman_cases.json`, variant `fixture_as_committed`, field `legacy_impute_error`).

Potential impact:
- Magnitude of the competing Singapore values, committed fixture. Canonical CWUEFF, SGP 2006: +17.75% (change from the single baseline year 2005); by 2023 the canonical series reaches +1281.7%, which goalposts to 1.0 either way.
- Reference-class mean of every canonical CWUEFF value in the fixture: +127.2% (+64.3% excluding Singapore's own rows), which goalposts to 1.0 for every year.
- Under the adopted rule Singapore's 2000–2006 WATMAN scores are 0.2696; under the reference-class rule they would be 0.5 (CWUEFF component 1.0, water-stress component 0.0). From 2010 on the two rules agree because the canonical change already exceeds the +50 goalpost.

Implementation decision in the new backend:
- Implementation policy adopted, decided by the project owner on 2026-10-01 as a required resolution, not as proven historical methodology:
- Canonical observed/derived CWUEFF takes precedence over the reference-class imputation.
- For SGP: if a canonical CWUEFF series can be derived from the available canonical WUSEFF observations, it is used (and extrapolated like every other series); the hard-coded reference-class series is **not** created in addition.
- The legacy reference-class fallback applies only when no canonical CWUEFF row exists for SGP. On the data the legacy route was written against this is exactly the legacy result, and the `sgp_without_2005` fixture variant holds that exact parity.
- The current-source case is registered as an intentional divergence (`INTENTIONAL_DIVERGENCES` in `tests/golden/parity.py`); the migration gate requires that every such registration correspond to a recorded legacy failure and cite this entry.
- The twelve synthetic-series countries have no such policy. If one of them gains canonical CWUEFF, the strategy raises rather than choosing.

Reason:
- The literal route cannot run, so some choice was unavoidable; preferring the source's own data over a constructed fallback is the smallest departure and coincides with legacy behaviour wherever legacy could run.

Question for methodology review:
- Still open. Confirm that a canonical series should always supersede a hard-coded reference-class fallback, and decide the same question for the synthetic-series list. Decide whether the lists should become a rule (SSPI67 members without a 2000–2005 baseline).

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/watman.py` (`impute_watman`)
- `sspi_flask_app/api/resources/utilities.py` (`score_indicator`, duplicate detection)

Relevant new-backend files:
- `src/sspi/indicators/watman.py` (`WatmanImputation.impute`)
- `tests/golden/watman_cases.json`, `tests/golden/test_golden_watman.py`, `tests/golden/parity.py`, `tests/unit/test_watman.py`, `tests/db/test_land_end_to_end.py`

---

## DEFRST-1 — Imputation of indicator scores for a hard-coded country list

Status: unresolved

In plain terms:
- The old methodology always gives Belgium, the United Arab Emirates and Luxembourg an imputed deforestation score, because at the time it was written the FAO reported no naturally-regenerating-forest data for them.
- Current FAO data now contains real forest data for the United Arab Emirates, so a real DEFRST score can be computed for it.
- The old rule therefore now produces both a real score and an imputed score for the same country and year (the Emirates, 2000–2022), and for 2023 two different imputed scores.
- The new backend currently **stops** when this happens, with an error naming this entry, instead of choosing between the two. Nothing is written. Until the methodology team decides, DEFRST does not run on current FAO data.

Current executable behavior (legacy impute route, `impute_defrst`):
- Indicator **scores** (not inputs) are extrapolated forward to 2023 per country: the latest scored document is deep-copied with the new year, `Imputed: True`, `ImputationMethod: "Forward Extrapolation"` and its distance.
- `BEL, ARE, LUX` receive, for every year 2000–2023, the mean of every other country's observed **score** (`impute_reference_class_average(..., "Indicator", ...)` over `sspi_indicator_data` minus the three countries), unconditionally: the route does not check whether the recipient already has scores.
- On current FAO data the United Arab Emirates has a naturally-regenerating-forest series (310.97 thousand ha, constant 1990–2025, FAO flag I), so the compute route scores ARE for 2000–2022 and the impute route still writes 24 reference-class scores for ARE plus a forward-extrapolated ARE 2023. The two legacy collections then hold an observed and an imputed score for ARE 2000–2022 and two imputed scores for ARE 2023. On the committed fixture (`tests/golden/defrst_cases.json`, variant `fixture_as_committed`): 23 identities both observed and imputed, 1 imputed twice. Legacy readers disagree on precedence (BIODIV-4); no reader resolves two imputed rows for one identity.

Conflicting evidence:
- Every other migrated indicator imputes inputs and then scores. No methodology text describes score-level imputation or names the three countries.
- The recipient list encodes a data state (no FAO forest series for Belgium, Luxembourg and the Emirates) that no longer holds for ARE. Belgium and Luxembourg still have no 1990s values (FAO reports Belgium-Luxembourg before 2000), so they still have no observed score.

Implementation decision in the new backend:
- `DefrstImputation` (`src/sspi/indicators/defrst.py`) reproduces the legacy route exactly where its output is consistent: forward extrapolation of scores (provenance `imputed`, `imputation_method: "Forward Extrapolation"`, `source_year`, `imputation_distance`; the anchor year's inputs are kept, no observation is fabricated) and reference-class scores for the three countries (provenance `imputed`, `imputation_method: "ImputeReferenceClassAverage"`, `reference_score_count`, `requested_years`; no inputs). Exact parity on the `without_are_source_rows` fixture variant, the source state the rule was written against.
- When a listed recipient already has observed scores, the strategy raises `ImputationError` naming this entry and selects no result. This is not a methodology choice and no precedence rule exists in the code (in particular, "skip imputation when observed data exists" is **not** implemented). The committed-fixture variant is registered in `PENDING_METHODOLOGY_DECISIONS` in `tests/golden/parity.py`, not as a divergence.
- The canonical-first policy approved for WATMAN (WATMAN-3) applies to WATMAN only and is deliberately not generalized here.

Reason:
- The legacy output for ARE is two different numbers for one identity (0.3333 observed from a constant series; 0.3453 reference mean on the fixture). Choosing one is a methodology change, which has not been approved; one row per identity cannot store both.

Potential impact:
- Today: DEFRST cannot be run on current FAO data (live run stops). On the fixture, the three countries receive a constant global-mean score for all 24 years (0.34525 from 184 reference scores). Figures from the committed fixture (18 areas), not the full source.

Question for methodology review:
- Which of the following should the SSPI adopt? Neither is adopted today.
  - Potential direction A: preserve the hard-coded legacy recipient lists exactly as written (the Emirates keep receiving the imputed score; a rule is then still needed for the years that also have a real score, and for the duplicated 2023 row).
  - Potential direction B: only impute when sufficient observed data is unavailable (the Emirates would score from their own data, 1/3 for 2000–2022 and an extrapolated 1/3 for 2023; Belgium and Luxembourg would keep the imputed score). This is the rule approved for WATMAN-3, but it has not been approved for DEFRST.
- Is score-level imputation intended for DEFRST at all, and what rule should select recipients now that the hard-coded list no longer matches the data?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py` (`impute_defrst`)
- `sspi_flask_app/api/resources/utilities.py` (`extrapolate_forward`, `impute_reference_class_average`)

Relevant new-backend files:
- `src/sspi/indicators/defrst.py`, `src/sspi/indicators/strategy.py` (`extrapolate_scores_forward`, `reference_class_average_scores`)
- `tests/golden/defrst_cases.json`, `tests/golden/test_golden_defrst.py`, `tests/golden/generate_fao_land_cases.py`, `tests/unit/test_defrst.py`, `tests/golden/parity.py` (`PENDING_METHODOLOGY_DECISIONS`)

---
## DEFRST-2 — The 1990s-average datasets behave differently and the methodology text drops the ×100

Status: unresolved

Current executable behavior:
- `UNFAO_FRSTAV` repeats each country's 1990–1999 mean for years 1990–2022 only (`range(1990, 2023)`), so `UNFAO_FRSTLV` values for 2023 and later can never form a complete group. On the committed fixture every country's 2023–2025 level rows are incomplete and DEFRST's observed scores stop at 2022; the impute route then extrapolates the 2022 score to 2023 (distance 1).
- `UNFAO_CRBNAV` repeats the mean for every year present anywhere in the source (currently 1990–2025), so CARBON has observed scores through 2025.
- Both routes score `goalpost((level − average) / average × 100, lg, ug)` with a zero-average guard returning 0, and keep only level years ≥ 2000.
- The derived units are labelled `hectares (1990s Average)` and `millions of kilograms (1990s Average)` while the level series are in `1000 ha` and `million t`; the values are unconverted means, so the labels are wrong by a factor of 1000 and the scores, a ratio, are unaffected (recorded in `src/sspi/metadata/data/PROVENANCE.yaml`).

Conflicting evidence:
- `methodology/sus/lnd/defrst/methodology.md` `ScoreFunction` omits the `× 100`; the 2018 static scores match the executable percent form.
- Status notes for both indicators question whether a 5- or 10-year lag should replace the 1990s baseline.

Implementation decision in the new backend:
- Both roll-forward rules are reproduced as they are, as `Derivation`s in `src/sspi/ingestion/derived.py` (`mean_1990_1999_repeated_1990_2022`, `mean_1990_1999_repeated_over_source_years`), with the legacy unit labels; the ×100 and the zero guard are reproduced in `score_defrst` and `score_carbon`. Exact parity for all four datasets and both indicators.

Reason:
- The asymmetry is executable behaviour; harmonizing it would change DEFRST coverage (observed scores for 2023–2025).

Potential impact:
- DEFRST has no observed scores after 2022 while CARBON does; DEFRST 2023 is always an extrapolation of 2022. Figures from the committed fixture.

Question for methodology review:
- Should the forest average roll forward to all years like the carbon one? Should the baseline remain the 1990s? Should the derived unit labels be corrected (a representation change that would alter the committed parity evidence but no score)?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unfao/unfao_frstav.py`, `sspi_flask_app/api/core/datasets/unfao/unfao_crbnav.py`
- `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py`, `methodology/sus/lnd/defrst/methodology.md`

Relevant new-backend files:
- `src/sspi/ingestion/derived.py`, `src/sspi/indicators/defrst.py`, `src/sspi/indicators/carbon.py`
- `tests/golden/unfao_frstav_cases.json`, `tests/golden/unfao_crbnav_cases.json`, `tests/golden/test_golden_fao_datasets.py`

---

## CARBON-1 — Reference-class imputation of both inputs for a hard-coded country list

Status: unresolved

In plain terms:
- The old methodology always gives Kuwait, Belgium and Luxembourg an imputed carbon-capture result, built from the average of every country's carbon-stock data, because at the time it was written the FAO reported no usable carbon data for them.
- Current FAO data now contains real carbon-stock data for Kuwait, with 1990s values, so a real CARBON score can be computed for it.
- The old rule therefore now produces both a real result and an imputed result for Kuwait for every year 2000–2023.
- The new backend currently **stops** when this happens, with an error naming this entry, instead of choosing between the two. Nothing is written. Until the methodology team decides, CARBON does not run on current FAO data.

Current executable behavior (legacy impute route, `impute_carbon`):
- `KWT, BEL, LUX` receive, for 2000–2023, the mean of every clean `UNFAO_CRBNLV` value and the mean of every clean `UNFAO_CRBNAV` value (all countries, all years including the 1990s, the recipients' own rows included where present), then are scored with the ordinary formula. No extrapolation.
- The rule is unconditional. On current FAO data Kuwait has a carbon-stock series with 1990s values (0.13–0.22 million t), so the compute route scores KWT for 2000–2025 and the impute route still writes 24 imputed KWT scores. On the committed fixture (`tests/golden/carbon_cases.json`, variant `fixture_as_committed`): 24 identities both observed and imputed. Belgium and Luxembourg have level rows from 2000 but no 1990s mean, hence no observed score and no conflict; their level rows enter the reference mean.

Conflicting evidence:
- No methodology text names the countries or the method. The same three-country idea appears in DEFRST-1 with a different mechanism (scores there, inputs here) and a different third country (ARE there, KWT here).

Implementation decision in the new backend:
- `CarbonImputation` (`src/sspi/indicators/carbon.py`) reproduces the legacy route exactly where its output is consistent: `reference_class_average` of both inputs over every canonical row, scored with `score_carbon`. Exact parity on the `without_kwt_source_rows` fixture variant, the source state the rule was written against.
- When a listed recipient already has observed scores, the strategy raises `ImputationError` naming this entry and selects no result. No precedence rule exists in the code ("skip imputation when observed data exists" is **not** implemented). The committed-fixture variant is registered in `PENDING_METHODOLOGY_DECISIONS` in `tests/golden/parity.py`, not as a divergence.
- The canonical-first policy approved for WATMAN (WATMAN-3) applies to WATMAN only and is deliberately not generalized here.

Reason:
- As DEFRST-1: two different numbers for one identity (committed fixture: KWT observed 2000 = 0.3842, 2023 = 0.8534 from its own series; imputed 0.1761 for every year from the two global means). Choosing one is a methodology change that has not been approved.

Potential impact:
- Today: CARBON cannot be run on current FAO data (live run stops). On the fixture, the three countries receive one constant score for all 24 years, equal to the goalposted change between two global means (0.17609 with Kuwait's rows in the means; parity variant without them: 0.15862). Figures from the committed fixture (18 areas), not the full source. See also CARBON-2 for what else enters those means.

Question for methodology review:
- Which of the following should the SSPI adopt? Neither is adopted today.
  - Potential direction A: preserve the hard-coded legacy recipient lists exactly as written (Kuwait keeps receiving the imputed result; a rule is then still needed for the years that also have a real score).
  - Potential direction B: only impute when sufficient observed data is unavailable (Kuwait would score from its own data; Belgium and Luxembourg would keep the imputed result). This is the rule approved for WATMAN-3, but it has not been approved for CARBON.
- Should CARBON and DEFRST use the same imputation mechanism and the same recipient rule?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/carbon.py` (`impute_carbon`)

Relevant new-backend files:
- `src/sspi/indicators/carbon.py`, `src/sspi/imputation.py` (`reference_class_average`)
- `tests/golden/carbon_cases.json`, `tests/golden/test_golden_carbon.py`, `tests/golden/generate_fao_land_cases.py`, `tests/unit/test_carbon.py`, `tests/golden/parity.py` (`PENDING_METHODOLOGY_DECISIONS`)

---
## NITROG-1 — The current EPI edition may not be methodologically identical to the historical EPI source

Status: unresolved

Current executable behavior:
- The legacy collector downloaded `https://epi.yale.edu/downloads/epi2024indicators.zip` and the cleaner read `SNM_ind_na.csv` (the 2024 EPI's Sustainable Nitrogen Management Index indicator scores, 1995–2024, 194 of 220 listed countries with values); the route scores `goalpost(EPI_NITROG, 0, 100)`.
- That URL now serves an HTML page. The current official distribution is the 2026 EPI (`https://epi.yale.edu/2026/downloads`): `epi2026_indicators_na_2026-08-31.zip`, `SNM_ind_na.csv`, 1996–2025. Production ingestion reads it (`EPI_NITROG.source.query_code`, PROVENANCE.yaml edit).

Conflicting evidence:
- The two files report different numbers for the same country-years (2024 file: Afghanistan 2000 = 29.4; 2026 file: 28.70833919), so the 2026 edition is a recomputation, not a vintage extension of the 2024 series.
- The 2026 methods workbook (`epi2026methods.xlsx`, sheet "Variable attributes") defines SNM as a `negative`-polarity indicator with `Raw_Target_Good = 0` and `Raw_Target_Bad = 1.30835882` set at the 99th percentile of the 2026 data (`Nominal_Target_Bad = 0.99`), baseline year 2013, most recent year 2023; precursors NTI, NCR, NRY (yield relative to 90 kg/ha), NUE. A percentile-based bad target makes the 0–100 indicator scale depend on the edition's own data distribution even if the underlying SNMI construct were unchanged. No 2024 methods workbook is available to confirm whether the construct, targets or precursor sources match.
- The dataset description still describes the "2022 EPI" use of the SNMI.

Implementation decision in the new backend:
- The committed 2024 fixture (`tests/fixtures/epi/epi2024indicators_P5_Indicator_SNM_ind_na.csv`, recovered from the Internet Archive capture of the legacy URL) is the integrity and parity reference: exact parity of the cleaner and of the scores against the legacy backend.
- Live EPI 2026 is the production source; the adapter is edition-agnostic. No parity claim is made across editions, and live figures are illustrative only.
- Comparisons of NITROG scores computed from the 2024 and 2026 editions must not be read as changes in country performance without first establishing that the editions are methodologically equivalent.

Reason:
- The available evidence cannot establish equivalence; the differing values and the percentile-based target argue against assuming it.

Potential impact:
- Every NITROG score changes with the edition. Malaysia 2020: 0.625 (2024 file) vs 0.6268 (2026 file); Austria 2020: 0.639 vs 0.6451; United States 2020: 0.771 vs 0.7698; Afghanistan 2020: 0.303 vs 0.2851 (illustrative, two editions, not parity). Country rankings on NITROG may shift for reasons internal to the EPI's normalization.

Question for methodology review:
- Does the SSPI intend to follow the latest EPI edition (and accept edition-driven score shifts), pin one edition, or re-normalize the raw SNMI itself with SSPI goalposts?

Relevant legacy files:
- `sspi_flask_app/api/datasource/epi.py`, `sspi_flask_app/api/core/datasets/epi/epi_nitrog.py`, `sspi_flask_app/api/core/sspi/sus/lnd/nitrog.py`
- `datasets/epi/epi_nitrog/documentation.md`

Relevant new-backend files:
- `src/sspi/ingestion/epi.py`, `src/sspi/indicators/nitrog.py`, `src/sspi/metadata/data/datasets/EPI_NITROG.yaml`
- `tests/golden/epi_nitrog_cases.json`, `tests/golden/nitrog_cases.json`, `tests/golden/test_golden_nitrog.py`, `tests/golden/generate_epi_nitrog_cases.py`

---

## CARBON-2 — Historic FAO entities enter the legacy reference-class means; canonical M49 geography skips them

Status: unresolved

Current executable behavior:
- The legacy collector asked the FAOSTAT API for `area_cs=ISO3` codes and the cleaner kept every area whose code is three characters with no digit. FAOSTAT's area list assigns ISO3-style codes to dissolved entities (USSR, Yugoslav SFR, Czechoslovakia, Serbia and Montenegro, Belgium-Luxembourg, Ethiopia PDR, Pacific Islands Trust Territory, Sudan (former)); the legacy cleaner would have kept those as countries, and `impute_carbon` averages every clean row, so their rows (USSR 1990–1991: 36,500 million t of carbon against a country mean of ~1,400) entered the `UNFAO_CRBNLV` and `UNFAO_CRBNAV` reference means for KWT, BEL and LUX.
- The exact codes the API returned cannot be re-checked: the API now requires authentication, and the bulk file carries M49 codes only. This entry records the behaviour FAOSTAT's published area definitions imply, not a verified legacy output.

Conflicting evidence:
- The project decision for the bulk source (2026-10-01) is canonical M49 geography: an area is a country iff its M49 code has an ISO 3166-1 entry today. Dissolved entities have none and are skipped and reported, together with FAO's broader "China" (M49 159) and the regional aggregates.
- On the live bulk file (2026-09-16) the CARBON reference means are 1399.61 (level) and 1427.11 (average) over mapped countries, giving the three recipients an imputed score of 0.0559; with the eight historic entities included as the legacy filter would have, 1402.37 and 1560.96, giving 0.0000. Illustrative live figures, not parity.
- The committed parity fixture does not exercise this: the generator presents unmapped areas to the legacy cleaner with FAO's numeric area code (dropped by the legacy filter), because the API's codes for them are unknown, so legacy and new agree on the fixture by construction for those areas.

Implementation decision in the new backend:
- Canonical M49 geography as decided; skipped areas are reported by `ingest()` and recorded here rather than mapped by name. No ISO3 code is invented for a dissolved entity.

Reason:
- The decision was taken explicitly; the magnitude is recorded so the methodology review can weigh it. Reproducing the legacy means would require asserting codes the legacy API may or may not have returned.

Potential impact:
- Imputed CARBON scores for KWT, BEL, LUX (0.0559 vs 0.0000 on live data). Observed scores of current countries are unaffected. Also see DEFRST-3.

Question for methodology review:
- Should reference-class means be restricted to current countries (the new behaviour), and should they be restricted further, for example to the SSPI67 or to the imputation years, rather than every row of the dataset?

Relevant legacy files:
- `sspi_flask_app/api/datasource/unfao.py` (`format_fao_data_series`), `sspi_flask_app/api/core/sspi/sus/lnd/carbon.py`

Relevant new-backend files:
- `src/sspi/ingestion/fao.py`, `src/sspi/ingestion/geo.py`, `src/sspi/indicators/carbon.py`, `tests/golden/generate_fao_land_cases.py`

---

## DEFRST-3 — Historic FAO entities and the Sudan series under canonical M49 geography

Status: unresolved

Current executable behavior:
- As CARBON-2, the legacy cleaner would have kept FAOSTAT's dissolved entities as countries. For DEFRST two of them have level rows from 2000 and a 1990s mean, so they would have been scored and entered the reference mean of scores given to BEL, ARE and LUX: Serbia and Montenegro (rows 1992–2005) and Sudan (former) (rows 1990–2011).
- If, as FAOSTAT's area list suggests, Sudan (former) carried the same code as today's Sudan (`SDN`), the legacy backend saw one merged Sudan series 1990–2025 and scored SDN from 2000 against a 1990s baseline that is the former Sudan's. Under canonical M49 geography Sudan (former) (M49 736) is skipped, today's Sudan (M49 729) has rows from 2012 only, no 1990s mean exists, and SDN has no DEFRST or CARBON score at all. Sudan is not an SSPI67 member.

Conflicting evidence:
- Project decision (2026-10-01): canonical M49 geography, no name-based mapping, differences recorded. Whether the legacy API labelled Sudan (former) `SDN` cannot be re-checked (API authenticated, bulk file M49 only).

Implementation decision in the new backend:
- Canonical M49 geography; Sudan (former) and the other dissolved entities are skipped and reported by `ingest()`.

Reason:
- As CARBON-2.

Potential impact:
- The BEL/ARE/LUX reference mean of scores shifts by the contribution of up to 18 historic-entity scores among ~4,700 (live data; small). SDN has no DEFRST/CARBON scores in the new backend; it may have had them in legacy. Not parity evidence.

Question for methodology review:
- Should a successor state inherit a predecessor's baseline (Sudan)? Which areas may contribute to a reference mean?

Relevant legacy files:
- `sspi_flask_app/api/datasource/unfao.py` (`format_fao_data_series`), `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py`

Relevant new-backend files:
- `src/sspi/ingestion/fao.py`, `src/sspi/ingestion/geo.py`, `src/sspi/indicators/defrst.py`

---

## GINIPT-1 — The World Bank Gini series mixes income-based and consumption-based surveys and is not specifically "after taxes"

Status: unresolved

Summary for the methodology team:
- Problem: the indicator is called "Gini-coefficient After Taxes" and described as the Gini "for post-tax-and-transfer income distribution", but the data it uses is the World Bank's general Gini index (`SI.POV.GINI`). That series comes from household surveys that measure income in some countries and consumption spending in others, and it is not restricted to post-tax-and-transfer income. A Gini computed from consumption is usually lower than one computed from income for the same country, so countries are not all measured on the same basis.
- Potential direction A: keep the World Bank series as it is (the current and legacy behaviour) and change the indicator's name and description so they say what is measured.
- Potential direction B: keep the "after taxes" concept and move to a source that measures post-tax-and-transfer income consistently (for example a harmonized disposable-income Gini), accepting different country and year coverage.
- Potential direction C: keep the World Bank series but record, per observation, whether it is income-based or consumption-based, and decide whether both kinds may be scored on the same goalposts.

Current executable behavior:
- The legacy collector requests `SI.POV.GINI` ("Gini index") from the World Bank API for all economies; the cleaner keeps every recognized country and year; the compute route scores `goalpost(WB_GINIPT, 70, 20)`. The new backend does the same.
- The API response carries no field saying whether an observation is income-based or consumption-based.

Conflicting evidence:
- `methodology/ms/neq/ginipt/methodology.md` and `datasets/wb/wb_ginipt/documentation.md`: name "Gini-coefficient After Taxes", description "GINI Coefficient for post-tax-and-transfer income distribution."
- The World Bank defines `SI.POV.GINI` as measuring the distribution of "income (or, in some cases, consumption expenditure)" among individuals or households, from primary household survey data.

Implementation decision in the new backend:
- Source selection unchanged: `WB_GINIPT` is `SI.POV.GINI`, every country and year the legacy cleaner kept. The name and description are migrated as they are.

Reason:
- The executable behaviour is unambiguous and reproducible. Which inequality concept the SSPI intends is a methodology question.

Potential impact:
- Cross-country comparability of every GINIPT score: income-based and consumption-based observations are scored on one scale. Not quantified here; the source does not label the observations.

Question for methodology review:
- Is the World Bank Gini index the intended measure, and if so should the indicator still be described as "after taxes"? Should income-based and consumption-based observations be distinguished?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/wb/wb_ginipt.py`, `sspi_flask_app/api/datasource/worldbank.py`, `sspi_flask_app/api/core/sspi/ms/neq/ginipt.py`
- `methodology/ms/neq/ginipt/methodology.md`, `datasets/wb/wb_ginipt/documentation.md`

Relevant new-backend files:
- `src/sspi/ingestion/worldbank.py`, `src/sspi/indicators/ginipt.py`, `src/sspi/metadata/data/datasets/WB_GINIPT.yaml`, `src/sspi/metadata/data/indicators/GINIPT.yaml`

---

## GINIPT-2 — The 2018 static GINIPT values for some countries do not come from the World Bank series

Status: unresolved

Summary for the methodology team:
- Problem: the published 2018 SSPI gave Singapore, Saudi Arabia, New Zealand and Kuwait a Gini value. The World Bank series the code uses today has no Gini for any of these four countries in any year, so those 2018 numbers must have come from somewhere else (the old static metadata points to the CIA World Factbook). Today the code instead predicts these countries' GINIPT scores from their ISHRAT scores with a regression. The two approaches give different scores.
- Potential direction A: keep the current executable rule (World Bank data only; countries with no World Bank Gini get the regression prediction from ISHRAT).
- Potential direction B: use a documented second source for the countries the World Bank does not cover, as the 2018 edition apparently did, and say which source and which year.

Current executable behavior:
- Observed GINIPT scores come only from `WB_GINIPT`. A country with no row at all gets a predicted score for each year it has an ISHRAT score (the regression fallback of the legacy impute route).
- On the committed fixture and on the live World Bank data of 2026-10-05, the countries with no Gini row among the SSPI67 members are Kuwait, New Zealand, Saudi Arabia and Singapore.

Conflicting evidence:
- `local/SSPIStaticData2018.csv` (historical static values, not read by any executable route): Singapore 45.9 (year 2013, score 0.482), Saudi Arabia 45.9 (2013, 0.482), New Zealand 36.2 (1997, 0.676), Kuwait 35.36 (2018, 0.693). None of these is in `SI.POV.GINI`.
- `local/IndicatorDetailsStatic.csv` lists the GINIPT source as "World Bank" with the source URL `https://www.cia.gov/the-world-factbook/` and years "1997-2018".
- The 2018 static scores of the 48 countries that have both values do satisfy `goalpost(raw, 70, 20)`; the goalposts are not in question.

Implementation decision in the new backend:
- The executable behaviour is reproduced. The 2018 static values are evidence only: they are not ingested, not stored as observations and not used as scores.

Reason:
- The legacy executable route never reads the static file. Adopting its values would be a source decision nobody has taken.

Potential impact:
- Committed fixture, regression predictions for 2018 against the 2018 static scores: Singapore 0.617 vs 0.482; Saudi Arabia 0.523 vs 0.482; New Zealand 0.862 vs 0.676; Kuwait 0.617 vs 0.693. These compare a prediction with a historical static value, two different things; they show magnitude only.

Question for methodology review:
- For countries the World Bank does not cover, should GINIPT be predicted from ISHRAT, taken from a named second source, or left missing?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/neq/ginipt.py` (`impute_ginipt`), `sspi_flask_app/api/resources/utilities.py` (`regression_imputation`)
- `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/ginipt.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/ginipt_cases.json`, `tests/golden/test_golden_ginipt.py`

---

## GINIPT-3 — GINIPT imputation and prediction cover more years than the usual 2000–2023 window

Status: unresolved

Summary for the methodology team:
- Problem: most SSPI imputation fills the years 2000 to 2023 and nothing else. GINIPT does not follow that convention in three ways. (1) Gaps inside a country's Gini series are filled by interpolation wherever they are, including gaps before 2000. (2) Observed scores exist for every year the World Bank reports, from the 1960s to the latest year. (3) The regression fallback predicts a score for every year the country has an ISHRAT score, and ISHRAT runs to 2024, so those countries get a 2024 GINIPT score while series-filled countries stop at 2023. The series fill also runs for every country in the World Bank data, not only the SSPI67 members.
- Potential direction A: keep the current executable behaviour (all of the above); readers restrict to the years and countries they need.
- Potential direction B: restrict GINIPT imputation and prediction to 2000–2023 and to the SSPI67 members, as other indicators do.

Current executable behavior:
- `impute_ginipt` calls `extrapolate_forward(..., 2023)`, `extrapolate_backward(..., 2000)` and `interpolate_linear(...)` on every `WB_GINIPT` series, each on the observed rows. Forward and backward fills are bounded by 2023 and 2000; interpolation fills every missing year between a series' first and last observation, with no year bound.
- The regression fallback predicts for every (country, year) with an observed ISHRAT score where the country has no Gini row. ISHRAT covers 2000–2024.
- The new backend reproduces all of it; the score rows carry the imputation method in their inputs (series fill) or in their own provenance (regression).

Conflicting evidence:
- Other legacy impute routes hard-code 2000–2023 and the SSPI67 group; legacy readers window to 2000–2023 at read time, so the extra years were stored but mostly not shown.
- No methodology text describes the GINIPT imputation at all.

Implementation decision in the new backend:
- Executable behaviour preserved exactly: no truncation of years, no country-group restriction.

Reason:
- Truncating would change which scores exist; that is a methodology decision.

Potential impact:
- Committed fixture: 1,727 observed scores (440 before 2000, 19 after 2023); 1,371 series-filled scores (1,122 interpolated, 169 carried forward, 80 carried backward), of which 551 are before 2000 and none after 2023; 100 regression-predicted scores for four countries, 2000–2024 (four of them for 2024).
- Live World Bank data of 2026-10-05 (*live, illustrative*): 2,413 observations for 170 countries, 1963–2025; 3,101 series-filled scores (2,216 interpolated, 569 carried forward, 316 carried backward), 837 of them for years before 2000; 100 regression-predicted scores for the same four countries, 2000–2024.

Question for methodology review:
- Should GINIPT imputation be limited to 2000–2023 and to the SSPI67 members? Should the regression fallback stop at 2023?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/neq/ginipt.py`, `sspi_flask_app/api/resources/utilities.py` (`extrapolate_forward`, `extrapolate_backward`, `interpolate_linear`, `regression_imputation`)

Relevant new-backend files:
- `src/sspi/indicators/ginipt.py`, `src/sspi/imputation.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/ginipt_cases.json`, `tests/golden/test_golden_ginipt.py`

---

## Template for a new entry

```
## CODE-n — Short title

Status: unresolved

Current executable behavior:
- ...

Conflicting evidence:
- ...

Implementation decision in the new backend:
- ...

Reason:
- ...

Potential impact:
- ... (state the data the figures come from)

Question for methodology review:
- ...

Relevant legacy files:
- ...

Relevant new-backend files:
- ...
```
