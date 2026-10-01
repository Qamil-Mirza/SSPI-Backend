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
| DEFRST-1 | Imputation of indicator scores for a hard-coded country list | unresolved |
| DEFRST-2 | The 1990s-average datasets behave differently and the methodology text drops the ×100 | unresolved |
| CARBON-1 | Reference-class imputation of both inputs for a hard-coded country list | unresolved |

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
- `tests/golden/watman_cases.json`, `tests/golden/test_golden_watman_compute.py`

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
- Not implemented yet. The WATMAN definition is registered only after the imputation-strategy interface is approved; the behaviour will then be reproduced exactly, lists included.

Reason:
- Reproducing a hard-coded list is the only faithful option; deriving the list from the data would change results whenever the source changes.

Potential impact:
- Thirteen SSPI67 countries receive imputed WATMAN scores for every year; a country that later gains source data keeps being imputed until the list changes.

Question for methodology review:
- Should recipients be derived from a rule (SSPI67 members without CWUEFF data), and is the synthetic-from-WUSEFF method the intended one?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/watman.py` (`impute_watman`, `create_synthetic_cwueff`)

Relevant new-backend files:
- none yet; `src/sspi/metadata/data/datasets/UNSDG_WUSEFF.yaml` is the imputation input

---

## DEFRST-1 — Imputation of indicator scores for a hard-coded country list

Status: unresolved

Current executable behavior (legacy impute route):
- Scores (not inputs) are extrapolated forward to 2023 per country.
- `BEL, ARE, LUX` receive the mean of every other country's **scores** for 2000–2023.

Conflicting evidence:
- Every other migrated indicator imputes inputs and then scores. No methodology text describes score-level imputation or names the three countries.

Implementation decision in the new backend:
- Not implemented yet (FAO source and imputation-strategy interface pending). When implemented, the executable behaviour will be reproduced.

Reason:
- Faithful reproduction first; the methodology question is separate.

Potential impact:
- The three countries receive a constant global-mean score for all 24 years.

Question for methodology review:
- Is score-level imputation intended for DEFRST, and what rule should select recipients?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py` (`impute_defrst`)

Relevant new-backend files:
- none yet

---

## DEFRST-2 — The 1990s-average datasets behave differently and the methodology text drops the ×100

Status: unresolved

Current executable behavior:
- `UNFAO_FRSTAV` repeats each country's 1990–1999 mean for years 1990–2022 only (`range(1990, 2023)`), so `UNFAO_FRSTLV` values for 2023 and later can never form a complete group.
- `UNFAO_CRBNAV` repeats the mean for every year present in the source.
- Both routes score `goalpost((level − average) / average × 100, lg, ug)` with a zero-average guard returning 0, and keep only level years ≥ 2000.

Conflicting evidence:
- `methodology/sus/lnd/defrst/methodology.md` `ScoreFunction` omits the `× 100`; the 2018 static scores match the executable percent form.
- Status notes for both indicators question whether a 5- or 10-year lag should replace the 1990s baseline.

Implementation decision in the new backend:
- Not implemented yet (FAO source pending). Both roll-forward rules will be reproduced as they are.

Reason:
- The asymmetry is executable behaviour; harmonizing it would change DEFRST coverage.

Potential impact:
- DEFRST has no observed scores after 2022 while CARBON does.

Question for methodology review:
- Should the forest average roll forward to all years like the carbon one? Should the baseline remain the 1990s?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unfao/unfao_frstav.py`, `sspi_flask_app/api/core/datasets/unfao/unfao_crbnav.py`
- `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py`, `methodology/sus/lnd/defrst/methodology.md`

Relevant new-backend files:
- none yet

---

## CARBON-1 — Reference-class imputation of both inputs for a hard-coded country list

Status: unresolved

Current executable behavior (legacy impute route):
- `KWT, BEL, LUX` receive, for 2000–2023, the mean of every clean `UNFAO_CRBNLV` value and the mean of every clean `UNFAO_CRBNAV` value (all countries, all years), then are scored with the ordinary formula. No extrapolation.

Conflicting evidence:
- No methodology text names the countries or the method. The same three-country idea appears in DEFRST-1 with a different mechanism (scores there, inputs here).

Implementation decision in the new backend:
- Not implemented yet (FAO source pending). Will be reproduced exactly.

Reason:
- As DEFRST-1.

Potential impact:
- The three countries receive one constant score for all 24 years, equal to the goalposted change between two global means.

Question for methodology review:
- Should CARBON and DEFRST use the same imputation mechanism and the same recipient rule?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/carbon.py` (`impute_carbon`)

Relevant new-backend files:
- none yet

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
