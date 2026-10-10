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

## Decisions recorded on 2026-10-08

On 2026-10-08 the project owner answered every open question in a review quiz. Six entries received a decision, each shown in a **✅ DECISION** box under that entry's status line.

A decision that needs a code change keeps its status until the code and the golden tests implement it. DEFRST-1 and CARBON-1 are implemented and resolved; the others keep their status.

| ID | Decision | Code change needed |
|---|---|---|
| BIODIV-1 | When the source has no series for a component, average the remaining two; the rule is "no series at the source" | yes, scores change |
| BIODIV-4 | Observed always supersedes imputed for one indicator, country and year | no, already enforced |
| DEFRST-1 | Direction B: impute only when observed data is unavailable (ARE scores from its own data) | done: resolved |
| CARBON-1 | Direction B: impute only when observed data is unavailable (KWT scores from its own data) | done: resolved |
| DEFRST-2 | Forest 1990s average rolls forward to every year like carbon; keep the 1990s baseline; correct the unit labels | yes, scores change |
| NITROG-1 | Follow the latest EPI edition and accept the score shifts a new edition causes | no, production already does |

The owner answered "I'm not sure" for every other entry, which leaves it open: BIODIV-2, BIODIV-3, BIODIV-5, REDLST-1, CHMPOL-1, CHMPOL-2, WATMAN-1, WATMAN-2, WATMAN-3, CARBON-2, DEFRST-3, GINIPT-1, GINIPT-2, GINIPT-3, EMPLOY-1, EMPLOY-2, COLBAR-1, COLBAR-2, NRGINT-1, AIRPOL-1, AIRPOL-2, ALTNRG-1, ALTNRG-2.

Entries added after the quiz (BEEFMK-1, BEEFMK-2, BEEFMK-3, COALPW-1, GTRANS-1, from the Greenhouse Gases port; MSWGEN-1, RECYCL-1, STCONS-1, from the Waste characterization; PUPTCH-1, ENRPRI-1, ENRSEC-1, YRSEDU-1, YRSEDU-2, from the Education port) have not been reviewed.

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
| DEFRST-1 | Imputation of indicator scores for a hard-coded country list | resolved |
| DEFRST-2 | The 1990s-average datasets behave differently and the methodology text drops the ×100 | unresolved |
| CARBON-1 | Reference-class imputation of both inputs for a hard-coded country list | resolved |
| NITROG-1 | The current EPI edition may not be methodologically identical to the historical EPI source | unresolved |
| CARBON-2 | Historic FAO entities enter the legacy reference-class means; canonical M49 geography skips them | unresolved |
| DEFRST-3 | Historic FAO entities and the Sudan series under canonical M49 geography | unresolved |
| GINIPT-1 | The World Bank Gini series mixes income-based and consumption-based surveys and is not specifically "after taxes" | unresolved |
| GINIPT-2 | The 2018 static GINIPT values for some countries do not come from the World Bank series | unresolved |
| GINIPT-3 | GINIPT imputation and prediction cover more years than the usual 2000–2023 window | unresolved |
| EMPLOY-1 | The indicator is described as ages 25–54 (and was labour force participation); the executable series is employment-to-population, ages 15–64 | unresolved |
| EMPLOY-2 | Imputed EMPLOY scores carry the unit label "Tax Rate" | unresolved |
| COLBAR-1 | Country-by-country imputations are listed in the methodology file but not implemented | unresolved |
| COLBAR-2 | COLBAR unit labels disagree: "Proportion" on the dataset, "%" on observed scores, "Tax Rate" on imputed scores | unresolved |
| NRGINT-1 | The source now reports energy intensity in 2021 dollars; the description and the goalposts date from the 2017-dollar series | unresolved |
| AIRPOL-1 | "Urban Air Pollution, PM2.5 and PM10 in cities" is computed from whole-country PM2.5 | unresolved |
| AIRPOL-2 | The source starts in 2010, so every 2000–2009 AIRPOL score is the 2010 score | unresolved |
| ALTNRG-1 | ALTNRG is described as World Bank and IEA shares of final energy consumption; the code uses IEA total energy supply, and its "geothermal" input is solar, wind and other renewables | unresolved |
| ALTNRG-2 | Most ALTNRG scores come from the impute route, which treats a missing energy type as zero | unresolved |
| BEEFMK-1 | The production half of BEEFMK divides thousand tonnes by people, so it scores 1.0 for every country | unresolved |
| BEEFMK-2 | The Food Balances start in 2010, so every 2000–2009 BEEFMK score is the 2010 score | unresolved |
| BEEFMK-3 | Japan is no longer in the Food Balances; the hard-coded recipient list names only Singapore | unresolved |
| COALPW-1 | A country that uses no coal is never scored from data; its imputed score is a perfect 1.0, and a country with no energy data at all also scores 1.0 | unresolved |
| GTRANS-1 | GTRANS is described in tonnes per inhabitant; the code computes kilograms per person | unresolved |
| MSWGEN-1 | MSWGEN applies a 100 → 0 goalpost to an EPI score that already rewards less waste, reversing its direction | unresolved |
| RECYCL-1 | RECYCL's executable goalposts are 0 → 100; the 2018 static scores use 0 → 70 | unresolved |
| STCONS-1 | STCONS is described as the top 10 % share of CO2 emissions; the formula is an estimated ecological footprint per person of the top decile | unresolved |
| PUPTCH-1 | PUPTCH's source series ends in 2019 and is no longer produced; the impute route carries each country's last value, however old, to 2023 | unresolved |
| ENRPRI-1 | ENRPRI and ENRSEC are described as net enrolment rates; the series requested are UIS *total* net enrolment rates | unresolved |
| ENRSEC-1 | ENRSEC gives China and Nigeria the mean of every country's every year | unresolved |
| YRSEDU-1 | YRSEDU drops the zeros UIS reports for countries without compulsory schooling, and backward extrapolation gives those years a later law's value | unresolved |
| YRSEDU-2 | The 2018 static SSPI used compulsory education only inside child labour (CHILDW), with goalposts 5 → 12; the executable indicator is a separate Education indicator scored 6 → 12 | unresolved |

---

## BIODIV-1 — Countries with no marine or freshwater series: omit the component or impute it

Status: unresolved

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: "If a series is missing, divide by 2 instead."
> - Score a country on the components it has a series for: when the source has no series for one component, average the other two instead of filling it with the reference-class average.
> - The criterion is "no series at the source", not "landlocked". It therefore also covers KWT and SGP, which have no freshwater series.
> - Status is unchanged: this records the decision, and the code does not implement it yet.

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

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: yes, observed wins.
> - An observed score always supersedes an imputed score for the same indicator, country and year. The new backend already enforces this in the database write, so no code change is needed.
> - Status is unchanged: this records the decision, and the code does not implement it yet.

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

Status: resolved

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: direction B, "impute only if no data" (decided together with CARBON-1).
> - Impute only when sufficient observed data is unavailable. The United Arab Emirates scores from its own data; Belgium and Luxembourg keep the imputed score.
> - CARBON and DEFRST use the same recipient rule, the one approved for WATMAN-3.
> - Implemented on 2026-10-08; see Resolution evidence below.

In plain terms:
- The old methodology always gives Belgium, the United Arab Emirates and Luxembourg an imputed deforestation score, because at the time it was written the FAO reported no naturally-regenerating-forest data for them.
- Current FAO data now contains real forest data for the United Arab Emirates, so a real DEFRST score can be computed for it.
- The old rule therefore now produces both a real score and an imputed score for the same country and year (the Emirates, 2000–2022), and for 2023 two different imputed scores.
- Decided 2026-10-08 (direction B): a listed country that has observed scores of its own is not imputed. The Emirates now score from their own data; Belgium and Luxembourg keep the imputed score. DEFRST runs on current FAO data again.

Current executable behavior (legacy impute route, `impute_defrst`):
- Indicator **scores** (not inputs) are extrapolated forward to 2023 per country: the latest scored document is deep-copied with the new year, `Imputed: True`, `ImputationMethod: "Forward Extrapolation"` and its distance.
- `BEL, ARE, LUX` receive, for every year 2000–2023, the mean of every other country's observed **score** (`impute_reference_class_average(..., "Indicator", ...)` over `sspi_indicator_data` minus the three countries), unconditionally: the route does not check whether the recipient already has scores.
- On current FAO data the United Arab Emirates has a naturally-regenerating-forest series (310.97 thousand ha, constant 1990–2025, FAO flag I), so the compute route scores ARE for 2000–2022 and the impute route still writes 24 reference-class scores for ARE plus a forward-extrapolated ARE 2023. The two legacy collections then hold an observed and an imputed score for ARE 2000–2022 and two imputed scores for ARE 2023. On the committed fixture (`tests/golden/defrst_cases.json`, variant `fixture_as_committed`): 23 identities both observed and imputed, 1 imputed twice. Legacy readers disagree on precedence (BIODIV-4); no reader resolves two imputed rows for one identity.

Conflicting evidence:
- Every other migrated indicator imputes inputs and then scores. No methodology text describes score-level imputation or names the three countries.
- The recipient list encodes a data state (no FAO forest series for Belgium, Luxembourg and the Emirates) that no longer holds for ARE. Belgium and Luxembourg still have no 1990s values (FAO reports Belgium-Luxembourg before 2000), so they still have no observed score.

Implementation decision in the new backend:
- `DefrstImputation` (`src/sspi/indicators/defrst.py`) reproduces the legacy route exactly where its output is consistent: forward extrapolation of scores (provenance `imputed`, `imputation_method: "Forward Extrapolation"`, `source_year`, `imputation_distance`; the anchor year's inputs are kept, no observation is fabricated) and reference-class scores for the three countries (provenance `imputed`, `imputation_method: "ImputeReferenceClassAverage"`, `reference_score_count`, `requested_years`; no inputs). Exact parity on the `without_are_source_rows` fixture variant, the source state the rule was written against.
- Since 2026-10-08 (direction B): a listed country with any observed DEFRST score is not a reference-class recipient. It is scored from its own data and, like every country, its latest score is carried forward to 2023. The rule is per country, not per year.
- The reference class is unchanged: the observed scores of every country not on the legacy list. Who may contribute to a reference mean is still open (CARBON-2, DEFRST-3).
- The score-level mechanism (forward extrapolation of scores, reference-class mean of scores) is unchanged. Whether DEFRST should impute scores rather than inputs was not part of the decision.
- On data where no listed country has observed scores, the result is exactly the legacy result. The committed-fixture variant is registered in `RESOLVED_METHODOLOGY_DECISIONS` in `tests/golden/parity.py`.

Reason:
- The legacy output for ARE is two different numbers for one identity (0.3333 observed from a constant series; 0.3453 reference mean on the fixture). One row per identity cannot store both. Before 2026-10-08 the backend raised instead of choosing; the decision selects the observed score.

Potential impact:
- Committed fixture as committed (18 areas, not the full source): 207 observed and 57 imputed scores. ARE keeps its observed 0.3333 for 2000–2022 and an extrapolated 0.3333 for 2023, where legacy also stored 24 reference-class scores of 0.34525. BEL and LUX receive 0.34525, the mean of 184 reference scores, for all 24 years, exactly as in legacy.

Question for methodology review:
- Which of the following should the SSPI adopt? Direction B was adopted on 2026-10-08.
  - Potential direction A: preserve the hard-coded legacy recipient lists exactly as written (the Emirates keep receiving the imputed score; a rule is then still needed for the years that also have a real score, and for the duplicated 2023 row).
  - Potential direction B: only impute when sufficient observed data is unavailable (the Emirates would score from their own data, 1/3 for 2000–2022 and an extrapolated 1/3 for 2023; Belgium and Luxembourg would keep the imputed score). This is the rule approved for WATMAN-3; it was adopted for DEFRST on 2026-10-08.
- Is score-level imputation intended for DEFRST at all, and what rule should select recipients now that the hard-coded list no longer matches the data?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/defrst.py` (`impute_defrst`)
- `sspi_flask_app/api/resources/utilities.py` (`extrapolate_forward`, `impute_reference_class_average`)

Relevant new-backend files:
- `src/sspi/indicators/defrst.py`, `src/sspi/indicators/strategy.py` (`extrapolate_scores_forward`, `reference_class_average_scores`)
- `tests/golden/defrst_cases.json`, `tests/golden/test_golden_defrst.py`, `tests/golden/generate_fao_land_cases.py`, `tests/unit/test_defrst.py`, `tests/golden/parity.py` (`RESOLVED_METHODOLOGY_DECISIONS`)

Resolution evidence:
- Decision: the project owner chose direction B in the methodology review quiz on 2026-10-08 (decision box above; summary in "Decisions recorded on 2026-10-08").
- Code: `DefrstImputation.impute` in `src/sspi/indicators/defrst.py` selects recipients as the listed countries without observed scores.
- Evidence: `tests/golden/test_golden_defrst.py` (`test_current_source_case_is_resolved_by_imputing_only_without_observed_data`) requires exact equality with the legacy output of variant `fixture_as_committed` minus ARE's reference-class rows. `tests/unit/test_defrst.py` and `tests/db/test_land_fao_epi_end_to_end.py` cover the rule and the stored result.

---
## DEFRST-2 — The 1990s-average datasets behave differently and the methodology text drops the ×100

Status: unresolved

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: yes, match carbon.
> - The forest 1990s average rolls forward to every source year, like the carbon average, so DEFRST gains observed scores after 2022.
> - The 1990s baseline stays, and the mislabelled derived units are corrected.
> - Status is unchanged: this records the decision, and the code does not implement it yet.

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

Status: resolved

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: direction B, "impute only if no data" (decided together with DEFRST-1).
> - Impute only when sufficient observed data is unavailable. Kuwait scores from its own data; Belgium and Luxembourg keep the imputed result.
> - CARBON and DEFRST use the same recipient rule, the one approved for WATMAN-3.
> - Implemented on 2026-10-08; see Resolution evidence below.

In plain terms:
- The old methodology always gives Kuwait, Belgium and Luxembourg an imputed carbon-capture result, built from the average of every country's carbon-stock data, because at the time it was written the FAO reported no usable carbon data for them.
- Current FAO data now contains real carbon-stock data for Kuwait, with 1990s values, so a real CARBON score can be computed for it.
- The old rule therefore now produces both a real result and an imputed result for Kuwait for every year 2000–2023.
- Decided 2026-10-08 (direction B): a listed country that has observed scores of its own is not imputed. Kuwait now scores from its own data; Belgium and Luxembourg keep the imputed result. CARBON runs on current FAO data again.

Current executable behavior (legacy impute route, `impute_carbon`):
- `KWT, BEL, LUX` receive, for 2000–2023, the mean of every clean `UNFAO_CRBNLV` value and the mean of every clean `UNFAO_CRBNAV` value (all countries, all years including the 1990s, the recipients' own rows included where present), then are scored with the ordinary formula. No extrapolation.
- The rule is unconditional. On current FAO data Kuwait has a carbon-stock series with 1990s values (0.13–0.22 million t), so the compute route scores KWT for 2000–2025 and the impute route still writes 24 imputed KWT scores. On the committed fixture (`tests/golden/carbon_cases.json`, variant `fixture_as_committed`): 24 identities both observed and imputed. Belgium and Luxembourg have level rows from 2000 but no 1990s mean, hence no observed score and no conflict; their level rows enter the reference mean.

Conflicting evidence:
- No methodology text names the countries or the method. The same three-country idea appears in DEFRST-1 with a different mechanism (scores there, inputs here) and a different third country (ARE there, KWT here).

Implementation decision in the new backend:
- `CarbonImputation` (`src/sspi/indicators/carbon.py`) reproduces the legacy route exactly where its output is consistent: `reference_class_average` of both inputs over every canonical row, scored with `score_carbon`. Exact parity on the `without_kwt_source_rows` fixture variant, the source state the rule was written against.
- Since 2026-10-08 (direction B): a listed country with any observed CARBON score receives no imputed inputs and is scored from its own data only. The rule is per country, not per year. CARBON has no extrapolation, so that country's unscored years stay unscored.
- The reference means are unchanged: every clean row of each dataset, the recipient's own rows included, as in legacy. Their composition is still open (CARBON-2).
- DEFRST and CARBON now use the same recipient rule; their mechanisms (scores there, inputs here) are unchanged.
- On data where no listed country has observed scores, the result is exactly the legacy result. The committed-fixture variant is registered in `RESOLVED_METHODOLOGY_DECISIONS` in `tests/golden/parity.py`.

Reason:
- As DEFRST-1: two different numbers for one identity (committed fixture: KWT observed 2000 = 0.3842, 2023 = 0.8534 from its own series; imputed 0.1761 for every year from the two global means). Before 2026-10-08 the backend raised instead of choosing; the decision selects the observed score.

Potential impact:
- Committed fixture as committed (18 areas, not the full source): 309 observed and 48 imputed scores. KWT keeps its own scores (2000 = 0.3842, 2023 = 0.8534), where legacy also stored 24 imputed scores of 0.1761. BEL and LUX receive one constant score for all 24 years, exactly as in legacy, equal to the goalposted change between two global means (0.17609 with Kuwait's rows in the means; parity variant without them: 0.15862). See also CARBON-2 for what else enters those means.

Question for methodology review:
- Which of the following should the SSPI adopt? Direction B was adopted on 2026-10-08, for CARBON and DEFRST alike.
  - Potential direction A: preserve the hard-coded legacy recipient lists exactly as written (Kuwait keeps receiving the imputed result; a rule is then still needed for the years that also have a real score).
  - Potential direction B: only impute when sufficient observed data is unavailable (Kuwait would score from its own data; Belgium and Luxembourg would keep the imputed result). This is the rule approved for WATMAN-3; it was adopted for CARBON on 2026-10-08.
- Should CARBON and DEFRST use the same imputation mechanism and the same recipient rule?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/lnd/carbon.py` (`impute_carbon`)

Relevant new-backend files:
- `src/sspi/indicators/carbon.py`, `src/sspi/imputation.py` (`reference_class_average`)
- `tests/golden/carbon_cases.json`, `tests/golden/test_golden_carbon.py`, `tests/golden/generate_fao_land_cases.py`, `tests/unit/test_carbon.py`, `tests/golden/parity.py` (`RESOLVED_METHODOLOGY_DECISIONS`)

Resolution evidence:
- Decision: the project owner chose direction B in the methodology review quiz on 2026-10-08 (decision box above; summary in "Decisions recorded on 2026-10-08").
- Code: `CarbonImputation.impute` in `src/sspi/indicators/carbon.py` selects recipients as the listed countries without observed scores.
- Evidence: `tests/golden/test_golden_carbon.py` (`test_current_source_case_is_resolved_by_imputing_only_without_observed_data`) requires exact equality with the legacy output of variant `fixture_as_committed` minus KWT's imputed rows. `tests/unit/test_carbon.py` and `tests/db/test_land_fao_epi_end_to_end.py` cover the rule and the stored result.

---
## NITROG-1 — The current EPI edition may not be methodologically identical to the historical EPI source

Status: unresolved

> **✅ DECISION — project owner, 2026-10-08**
>
> - Answer: follow the latest EPI edition.
> - NITROG follows each new EPI edition, and score shifts caused by a new edition are accepted. Production already reads the latest edition (EPI 2026), so no code change is needed. NITROG scores from different editions are still not comparable as changes in country performance.
> - Status is unchanged: this records the decision, and the code does not implement it yet.

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
- Imputed CARBON scores for BEL and LUX (0.0559 vs 0.0000 on live data; KWT is scored from its own data since CARBON-1 was resolved). Observed scores of current countries are unaffected. Also see DEFRST-3.

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
- The BEL/LUX reference mean of scores shifts by the contribution of up to 18 historic-entity scores among ~4,700 (live data; small). SDN has no DEFRST/CARBON scores in the new backend; it may have had them in legacy. Not parity evidence.

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

## EMPLOY-1 — The indicator is described as ages 25–54 (and was labour force participation); the executable series is employment-to-population, ages 15–64

Status: unresolved

Summary for the methodology team:
- Problem: the indicator now called EMPLOY ("Participation in Paid Employment") was called LFPART (labour force participation) until 2025. Its description still says "employed workers ages 25-54", and the 2018 published values are in the range of a prime-age participation rate. What the code actually scores is the ILO employment-to-population ratio for ages 15–64, both sexes. That is a different measure (it counts only the employed, and includes ages 15–24 and 55–64) and it is much lower: Austria 2017 is 71.9 on the executable series and 88.66 in the 2018 published data.
- Potential direction A: keep the executable series (employment-to-population, 15–64) and correct the description and static documentation to match.
- Potential direction B: return to a prime-age (25–54) series, either the employment-to-population ratio for that age group or the labour force participation rate the legacy `ILO_EMPLOY` dataset still collects, and keep the description.

Current executable behavior:
- `compute_employ` and `impute_employ` read `ILO_EMPLOY_TO_POP` and score it with `goalpost(ILO_EMPLOY_TO_POP, 50, 95)`.
- `ILO_EMPLOY_TO_POP` is ILO dataflow `DF_EMP_DWAP_SEX_AGE_RT`, key `.A..SEX_T.AGE_YTHADULT_Y15-64`, requested from 2000 on.
- The new backend reproduces this exactly. There is no indicator called LFPART at the pinned commit, in code or in metadata.

Conflicting evidence:
- `methodology/ms/wen/employ/methodology.md`: "Sum of all employed workers ages 25-54 divided by the total number of people in that age group."
- `local/IndicatorDetailsStatic.csv` names the source series `DF_EAP_DWAP_SEX_AGE_RT` (labour force participation rate) and links an OECD labour-force-participation page.
- A second legacy dataset, `ILO_EMPLOY` (`DF_EAP_DWAP_SEX_AGE_RT`, key `.A...AGE_AGGREGATE_Y25-54`, described with the same 25–54 sentence), has a collector and a cleaner but no indicator reads it.
- Legacy history: commits `f6abcb1b4` and `29dc75073` rename LFPART to EMPLOY everywhere.
- `local/SSPIStaticData2018.csv`: EMPLOY raw values Austria 88.66 (2017), United States 81.69 (2017), India 77.66 (2018). The executable series gives 71.919, 70.11 and 46.171 for the same country-years (committed fixture).

Implementation decision in the new backend:
- Executable behaviour preserved: `EMPLOY` reads `ILO_EMPLOY_TO_POP` (15–64) with goalposts (50, 95). `ILO_EMPLOY` is not ingestible and nothing reads it. No `LFPART` code exists.

Reason:
- Choosing the age group or the measure is a methodology decision; the executable route is the only complete legacy implementation.

Potential impact:
- Every EMPLOY score. With goalposts (50, 95), Austria 2017 scores 0.487 on the executable series; the 2018 published score was 0.859. India 2018: 0.0 (46.171 is below the lower goalpost) against 0.615 published.
- The goalposts (50, 95) were set for the older measure; on the 15–64 employment ratio the committed fixture ranges from 24.46 to 93.76.

Question for methodology review:
- Which measure and which age group define EMPLOY? If the executable 15–64 employment ratio stays, should the goalposts be revisited?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wen/employ.py`, `sspi_flask_app/api/core/datasets/ilo/ilo_employ_to_pop.py`, `sspi_flask_app/api/core/datasets/ilo/ilo_employ.py`
- `methodology/ms/wen/employ/methodology.md`, `datasets/ilo/ilo_employ_to_pop/documentation.md`, `datasets/ilo/ilo_employ/documentation.md`, `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/employ.py`, `src/sspi/ingestion/ilo.py`, `src/sspi/metadata/data/datasets/ILO_EMPLOY_TO_POP.yaml`
- `tests/golden/employ_cases.json`, `tests/golden/ilo_employ_to_pop_cases.json`, `tests/golden/test_golden_worker_engagement.py`

---

## EMPLOY-2 — Imputed EMPLOY scores carry the unit label "Tax Rate"

Status: unresolved

Summary for the methodology team:
- Problem: an observed EMPLOY score is labelled with the unit "Percentage"; an imputed EMPLOY score (carried forward, carried backward or interpolated) is labelled "Tax Rate". The numbers are computed the same way; only the label differs, and "Tax Rate" has nothing to do with employment. It looks like a line copied from a tax indicator.
- Potential direction A: keep both labels as they are (current behaviour).
- Potential direction B: use one label for all EMPLOY scores ("Percentage", or the "Index" most indicators use). This changes no score.

Current executable behavior:
- `compute_employ` passes `unit="Percentage"` to `score_indicator`; `impute_employ` passes `unit="Tax Rate"`.
- The new backend reproduces both: the definition's unit is `Percentage` and its imputation strategy writes `Tax Rate`.

Conflicting evidence:
- The dataset's unit is `Rate`; the indicator is not a tax measure. The same `unit="Tax Rate"` literal appears in the impute route of COLBAR (COLBAR-2).

Implementation decision in the new backend:
- Preserved exactly, so that stored scores match the legacy records field for field.

Reason:
- The label is part of the legacy record and parity is exact. Correcting it is a small representation decision, but it is not ours to make silently.

Potential impact:
- No score changes. On the committed fixture 2,576 of 5,266 EMPLOY scores are imputed and carry "Tax Rate". A reader who groups or filters by unit will split the indicator in two.

Question for methodology review:
- Which single unit label should EMPLOY scores carry?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wen/employ.py`

Relevant new-backend files:
- `src/sspi/indicators/employ.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore.unit`)
- `tests/golden/employ_cases.json`, `tests/golden/test_golden_worker_engagement.py`, `tests/unit/test_series_fill_strategy.py`

---

## COLBAR-1 — Country-by-country imputations are listed in the methodology file but not implemented

Status: unresolved

Summary for the methodology team:
- Problem: the ILO collective-bargaining series has no data for ten SSPI countries: Algeria, Ecuador, India, Iran, Iraq, Kuwait, Nigeria, Pakistan, Saudi Arabia and the United Arab Emirates. The methodology file lists exactly these ten under "Imputations", each as a heading with no text, and the code has a comment where the imputations were going to go. Nothing was written. These countries have no COLBAR score in any year.
- Potential direction A: leave them unscored until values are supplied (current behaviour).
- Potential direction B: supply a value and a source for each of the ten countries, as the headings intended. The 2018 published data did carry values for four of them (India 0.08, Kuwait 0.00, Saudi Arabia 0.00, United Arab Emirates 0.00).

Current executable behavior:
- `impute_colbar` carries each country's observed series forward to 2023 and backward to 2000 and interpolates gaps, then scores. A country with no observation gets nothing. The route contains the comment `## Implement Country by Country Calue Imputations Here` followed by no code.
- The new backend does the same: no score for a country the dataset does not cover.

Conflicting evidence:
- `methodology/ms/wen/colbar/methodology.md` has an "Imputations" section with ten empty country headings (ECU, IRN, PAK, DZA, NGA, ARE, IND, IRQ, KWT, SAU).
- `local/SSPIStaticData2018.csv` has COLBAR values for India (0.08, 2011), Kuwait (0.00, 2010), Saudi Arabia (0.00, 2012) and the United Arab Emirates (0.00, 2014); the ILO series has none of them.

Implementation decision in the new backend:
- Executable behaviour preserved: no imputation for uncovered countries, no invented values.

Reason:
- The values and their sources were never recorded. Supplying them is a methodology task.

Potential impact:
- Ten of the 66 SSPI67 members have no COLBAR score, so any category score built on COLBAR is missing an input for them (committed fixture, which is the ILO response of 2026-10-05).
- The ILO series also ends in 2020 for every country, so every 2021–2023 COLBAR score is the latest observed value carried forward (583 scores on the committed fixture).

Question for methodology review:
- What values, from what sources, should the ten countries receive, and for which years?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wen/colbar.py`, `methodology/ms/wen/colbar/methodology.md`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/colbar.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/colbar_cases.json`, `tests/golden/test_golden_worker_engagement.py`, `tests/golden/test_golden_ilo_datasets.py`

---

## COLBAR-2 — COLBAR unit labels disagree: "Proportion" on the dataset, "%" on observed scores, "Tax Rate" on imputed scores

Status: unresolved

Summary for the methodology team:
- Problem: three different unit labels describe the same quantity. The ILO publishes collective bargaining coverage as a percentage (0 to 100) and the goalposts (0, 100) treat it that way. The dataset is labelled "Proportion", which would mean 0 to 1. Observed scores are labelled "%". Imputed scores are labelled "Tax Rate", which is unrelated. The 2018 published data did store proportions (Austria 0.98) with the same (0, 100) goalposts written next to them.
- Potential direction A: keep the three labels as they are (current behaviour).
- Potential direction B: label the dataset as a percentage and use one label for all COLBAR scores. This changes no score.

Current executable behavior:
- `clean_ilo_colbar` passes `unit_label="Proportion"`; values are the source's percentages, unconverted (Austria 2019: 98.0).
- `compute_colbar` passes `unit="%"`; `impute_colbar` passes `unit="Tax Rate"`.
- The new backend reproduces all three.

Conflicting evidence:
- The ILO response declares `UNIT_MEASURE` `PT` (percent).
- `local/SSPIStaticData2018.csv` stores COLBAR raw values as proportions (Austria 0.98, United States 0.12) while `local/IndicatorDetailsStatic.csv` gives goalposts (0, 100); the published 2018 scores equal the proportion.
- The same `unit="Tax Rate"` literal appears in the impute route of EMPLOY (EMPLOY-2).

Implementation decision in the new backend:
- Preserved exactly: dataset unit `Proportion`, observed score unit `%`, imputed score unit `Tax Rate`.

Reason:
- The labels are part of the legacy records and parity is exact. The values and the goalposts agree with each other, so no score is affected.

Potential impact:
- No score changes. On the committed fixture 1,511 of 2,376 COLBAR scores are imputed and carry "Tax Rate". A reader who takes "Proportion" literally would misread a stored 98.0.

Question for methodology review:
- Which labels should the dataset and the scores carry?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wen/colbar.py`, `sspi_flask_app/api/core/datasets/ilo/ilo_colbar.py`, `datasets/ilo/ilo_colbar/documentation.md`

Relevant new-backend files:
- `src/sspi/indicators/colbar.py`, `src/sspi/metadata/data/datasets/ILO_COLBAR.yaml`
- `tests/golden/colbar_cases.json`, `tests/golden/ilo_colbar_cases.json`, `tests/golden/test_golden_ilo_datasets.py`

---

## NRGINT-1 — The source now reports energy intensity in 2021 dollars; the description and the goalposts date from the 2017-dollar series

Status: unresolved

Summary for the methodology team:
- Problem: NRGINT is megajoules of primary energy per dollar of GDP, and "dollar" means constant purchasing-power-parity dollars of a base year. The indicator description says 2017 dollars. The UN SDG database now publishes the same series in 2021 dollars. The goalposts (15 worst, 0 best) were set for the earlier series and are applied unchanged, so every country's score moved when the source was rebased.
- Potential direction A: keep the goalposts and accept the rebased values (current behaviour), and update the description to say 2021 dollars.
- Potential direction B: restate the goalposts for 2021 dollars so that scores keep the meaning they had.

Current executable behavior:
- The cleaner keeps every value of SDG 7.3.1 series `EG_EGY_PRIM`. The compute route scores each with `goalpost(value, 15, 0)`. Nothing in the code refers to a base year.
- The new backend does the same.

Conflicting evidence:
- `methodology/sus/nrg/nrgint/methodology.md` and `datasets/unsdg/unsdg_nrgint/documentation.md`: "megajoules per constant 2017 purchasing power parity GDP".
- The live source (2026-10-05) titles the series "Energy intensity level of primary energy (megajoules per constant 2021 purchasing power parity GDP)".
- `local/SSPIStaticData2018.csv`: Austria 2.81, United States 4.61, India 4.40 for 2018. The live source gives 2.41, 4.17 and 3.63 for the same year.

Implementation decision in the new backend:
- Executable behaviour preserved: the series as published, goalposts (15, 0). The legacy description is kept as imported.

Reason:
- Which base year the index means, and whether the goalposts follow it, is a methodology decision. This is a change in the source, not in the migration.

Potential impact:
- For the 49 countries in the 2018 static file, the current value for the static year is lower than the static value by 14% at the median (ratios from 0.72 to 1.17; live source, 2026-10-05, illustrative). Lower intensity scores better, so current scores are generally higher than the 2018 ones.
- 186 of 6,955 current country-year values are above the lower goalpost of 15 and score 0.

Question for methodology review:
- Should the goalposts be restated for the 2021-dollar series?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/nrg/nrgint.py`, `sspi_flask_app/api/core/datasets/unsdg/unsdg_nrgint.py`, `methodology/sus/nrg/nrgint/methodology.md`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/nrgint.py`, `src/sspi/metadata/data/datasets/UNSDG_NRGINT.yaml`
- `tests/golden/nrgint_cases.json`, `tests/golden/test_golden_energy.py`

---

## AIRPOL-1 — "Urban Air Pollution, PM2.5 and PM10 in cities" is computed from whole-country PM2.5

Status: unresolved

Summary for the methodology team:
- Problem: the indicator is named Urban Air Pollution and described as PM2.5 and PM10 in cities. The code uses one series, PM2.5 only, and of the five location breakdowns the source publishes it takes the one for the whole country ("all areas"), not the one for cities or for urban areas.
- Potential direction A: keep the whole-country PM2.5 figure (current behaviour) and correct the name and description.
- Potential direction B: use the cities or urban breakdown, which is what the name and description say. Values are higher there, so scores would fall.

Current executable behavior:
- The cleaner selects SDG 11.6.2 series `EN_ATM_PM25` and passes `location="ALLAREA"`. The source also publishes `URBAN`, `RURAL`, `TSUB` (towns and suburbs) and `CITY`. The compute route scores with `goalpost(value, 40, 0)`.
- The new backend does the same; the `location: ALLAREA` selection is now written in the dataset's canonical metadata.

Conflicting evidence:
- `methodology/sus/nrg/airpol/methodology.md`: name "Urban Air Pollution"; description "Annual mean levels of fine particulate matter (PM2.5 and PM10) in cities (population weighted)".
- The source describes the series as "Annual mean levels of fine particulate matter (population-weighted), by location". There is no PM10 series under 11.6.2.
- `local/2025-06-25-indicator-status.json` calls the indicator "Air Pollution".
- `local/SSPIStaticData2018.csv` (2016 values) is closer to the cities breakdown for some countries: India 65.2 (live source: all areas 59.4, urban 60.3, cities 65.0); Austria 12.43 (11.72, 12.23, 13.02).

Implementation decision in the new backend:
- Executable behaviour preserved: `EN_ATM_PM25`, `ALLAREA`.

Reason:
- Which population the indicator is about is a methodology decision.

Potential impact:
- Every AIRPOL score. For 2016 the cities figure is higher than the all-areas figure by 0.3 (United States), 1.3 (Austria) and 5.6 (India) micrograms per cubic metre (live source, 2026-10-05, illustrative); with goalposts (40, 0) each microgram is 0.025 of score.

Question for methodology review:
- Should AIRPOL measure the whole population or the urban population, and should its name and description change?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unsdg/unsdg_airpol.py`, `sspi_flask_app/api/core/sspi/sus/nrg/airpol.py`, `methodology/sus/nrg/airpol/methodology.md`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/airpol.py`, `src/sspi/metadata/data/datasets/UNSDG_AIRPOL.yaml`, `src/sspi/metadata/data/PROVENANCE.yaml`
- `tests/golden/unsdg_airpol_cases.json`, `tests/golden/airpol_cases.json`, `tests/golden/test_golden_energy.py`

---

## AIRPOL-2 — The source starts in 2010, so every 2000–2009 AIRPOL score is the 2010 score

Status: unresolved

Summary for the methodology team:
- Problem: the UN series has data for 2010–2023 only. The impute route copies each country's 2010 score into 2000–2009. Ten of the 24 years of every country's AIRPOL series are therefore one repeated value. The team's own status note says a new data source is needed.
- Potential direction A: keep the copied 2010 score for 2000–2009 (current behaviour).
- Potential direction B: find a source that covers 2000–2009, as the status note asks.
- Potential direction C: leave 2000–2009 unscored until such a source exists.

Current executable behavior:
- `impute_airpol` carries each country's earliest score back to 2000 and its latest forward to 2023. It then gives every SSPI67 country with no score at all the average of every observed score, of every country and every year, for 2000–2023.
- The new backend does the same, on scores, and marks each such score imputed with its method and source year.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json`: "Attention Required, New Data Source Needed. The current SDG data source only goes back to 2010."
- `local/SSPIStaticData2018.csv` used 2016 values, inside the source's range.

Implementation decision in the new backend:
- Executable behaviour preserved.

Reason:
- Replacing the source or dropping the years is a methodology decision.

Potential impact:
- On the live source (2026-10-05, illustrative): 237 countries, 3,318 observed scores for 2010–2023 and 2,370 imputed scores for 2000–2009. Every SSPI67 country has data, so the average-of-everything rule gives no score today. On the committed fixture it gives 1,272 scores, because the fixture holds only 14 countries.
- The average-of-everything rule would use all countries in the source, not only SSPI countries, and all years at once.

Question for methodology review:
- Should 2000–2009 keep the 2010 value, come from another source, or be left empty?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/nrg/airpol.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/airpol.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/airpol_cases.json`, `tests/golden/test_golden_energy.py`

---

## ALTNRG-1 — ALTNRG is described as World Bank and IEA shares of final energy consumption; the code uses IEA total energy supply, and its "geothermal" input is solar, wind and other renewables

Status: unresolved

Summary for the methodology team:
- Problem: the 2018 documentation describes ALTNRG as a World Bank renewable share of final energy consumption minus half an IEA biofuel share. The code instead uses IEA total energy supply for seven fuel groups. The current description says "total energy supply" in one place and "final energy supply" in another. And the fuel group the code stores as "Geothermal" is the one the IEA calls "Solar, wind and other renewables".
- Potential direction A: keep the seven-fuel total-energy-supply formula (what the code does) and correct the descriptions and the dataset name.
- Potential direction B: return to the 2018 definition (World Bank renewable share and IEA biofuel share of final consumption).

Current executable behavior:
- Each of seven datasets is one product of IEA indicator `TESbySource`, in terajoules: `IEA_TLCOAL` = `COAL`, `IEA_NATGAS` = `NATGAS`, `IEA_NCLEAR` = `NUCLEAR`, `IEA_HYDROP` = `HYDRO`, `IEA_GEOPWR` = `GEOTHERM`, `IEA_BIOWAS` = `COMRENEW`, `IEA_FSLOIL` = `MTOTOIL`.
- Percentage: `((NCLEAR + HYDROP + GEOPWR + BIOWAS) − 0.5 × BIOWAS) / (TLCOAL + NATGAS + NCLEAR + HYDROP + GEOPWR + BIOWAS + FSLOIL) × 100`. Score: `goalpost(percentage, 0, 60)`.
- The new backend does the same, with the same dataset names.

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv`: "Percentage of total final energy consumption generated from renewable sources (RS, collected from WorldBank ...) minus half the percentage of total final energy consumption generated from biofuel sources (BIO, collected from IEA)".
- `methodology/sus/nrg/altnrg/methodology.md`: "Total energy supply ... minus half of total final energy supply from biofuel sources".
- The seven dataset files describe each dataset as "Percentage of total final energy consumption generated from ..." with unit TJ; the values are terajoules of total energy supply.
- The IEA labels product `GEOTHERM` "Solar, wind and other renewables" and `COMRENEW` "Biofuels and waste".

Implementation decision in the new backend:
- Executable behaviour preserved exactly: IEA `TESbySource`, the seven products, the legacy dataset names and descriptions.
- Source interface (a decision of 2026-10-05, not part of this question): the same endpoint the legacy backend used, `https://api.iea.org/stats/indicator/TESbySource`. It is not documented by the IEA as a stable public API and is treated as fragile; replacing it with another IEA product needs its own characterization and parity review.

Reason:
- Which quantity ALTNRG measures is a methodology decision.

Potential impact:
- Every ALTNRG score. Total energy supply and final consumption differ by conversion losses, which are large for nuclear and fossil power, so the two definitions rank countries differently.

Question for methodology review:
- Is the seven-fuel total-energy-supply formula the intended definition, and should the "Geothermal" dataset be renamed?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/nrg/altnrg.py`, `sspi_flask_app/api/datasource/iea.py`, `sspi_flask_app/api/core/datasets/iea/iea_geopwr.py`, `methodology/sus/nrg/altnrg/methodology.md`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/altnrg.py`, `src/sspi/ingestion/iea.py`, `src/sspi/metadata/data/datasets/IEA_GEOPWR.yaml`
- `tests/golden/altnrg_cases.json`, `tests/golden/iea_geopwr_cases.json`, `tests/golden/test_golden_altnrg.py`

---

## ALTNRG-2 — Most ALTNRG scores come from the impute route, which treats a missing energy type as zero

Status: unresolved

Summary for the methodology team:
- Problem: the first pass scores a country-year only when all seven fuel groups have a value. Most countries have no nuclear row, so most country-years are not scored there. A second pass fills every gap: a fuel group a country never reports becomes zero for 2000–2023, and other gaps are filled from the country's nearest reported value. The result is scored and stored as imputed. So for most countries the ALTNRG score is flagged imputed even though it is ordinary data with "no nuclear" read as zero. The filling also has side effects listed below.
- Potential direction A: keep it (what the code does).
- Potential direction B: treat an absent fuel group, and a reported zero, as a true zero in the first pass, so that these scores are not flagged imputed and closed plants are not carried forward.

Current executable behavior:
- The cleaner drops a row whose value is empty or zero. `compute_altnrg` needs all seven datasets for a country-year.
- `impute_altnrg`, for each dataset on its own: every SSPI67 country with no row at all gets 0.0 for 2000–2023, labelled with unit `PJ` (the data are in `TJ`); every country with some rows has its series carried back to 2000, forward to 2023 and interpolated across gaps. All rows are then scored with the same percentage; a total of zero scores 0. Scores with any filled input are stored as imputed.
- Side effects of that order: a series that is zero and then starts (solar and wind in many countries) is carried back from its first non-zero year instead of staying zero; a series that ends is carried forward (Lithuania's nuclear plant closed in 2009 and its 2009 output is used through 2023); a single reported zero inside a series is interpolated (Japan's nuclear in 2014).
- A country outside SSPI67 with no nuclear row is never scored. For SSPI67 countries, years before 2000 and after 2023 are not zero-filled and stay unscored.
- If a dataset has no rows at all, every SSPI67 country is zero-filled for it and scores are still produced.
- The new backend reproduces all of this exactly.

Conflicting evidence:
- `methodology/sus/nrg/altnrg/methodology.md` gives the formula only and does not mention any filling.
- `local/2025-06-25-indicator-status.json`: "Computations are done but nicer data housekeeping needs to be done on the backend."

Implementation decision in the new backend:
- Executable behaviour preserved, including the `PJ` label on zero-filled inputs and the imputed flag.

Reason:
- Whether an unreported fuel is a zero or a gap is a methodology decision.

Potential impact:
- On the IEA response of 2026-10-05 (illustrative): of the 1,584 SSPI67 country-years in 2000–2023, 628 are scored from complete data and 956 by the impute route. 29 of the 66 SSPI67 countries have a nuclear row in some year; 37 have none, and their nuclear input is zero-filled in 888 country-years. 653 of the 956 are imputed only because of the nuclear input.

Question for methodology review:
- Should an unreported fuel group, and a reported zero, count as zero in the observed score?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/nrg/altnrg.py`, `sspi_flask_app/api/datasource/iea.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/altnrg.py`, `src/sspi/indicators/strategy.py`, `src/sspi/ingestion/iea.py`
- `tests/golden/altnrg_cases.json`, `tests/golden/test_golden_altnrg.py`, `tests/unit/test_altnrg.py`

---

## BEEFMK-1 — The production half of BEEFMK divides thousand tonnes by people, so it scores 1.0 for every country

Status: unresolved

Summary for the methodology team:
- Problem: BEEFMK is the average of a production part and a consumption part, each scored against goalposts of 50 and 0. The description says production is "kilograms per person". The code divides FAO production, which is in thousand tonnes, by population without converting. That gives numbers around 0.00001, so the production part is 1.0 (to six decimal places) for every country, and BEEFMK effectively becomes (1 + consumption part) / 2: no score can fall meaningfully below one half.
- Potential direction A: keep it (what the code does).
- Potential direction B: convert production to kilograms per person (multiply by 1,000,000) before scoring it against 50 and 0, as the description reads.

Current executable behavior:
- `compute_beefmk` scores `(goalpost(UNFAO_BFPROD / WB_POPULN, 50, 0) + goalpost(UNFAO_BFCONS, 50, 0)) / 2`, with both goalpost pairs hard-coded in the route. `UNFAO_BFPROD` is FAOSTAT Food Balances item 2731 (Bovine Meat), element Production, unit `1000 t`; `WB_POPULN` is World Bank total population (persons).
- The quotient is thousand tonnes per person: about 3.7e-5 for the United States in 2023. `goalpost(3.7e-5, 50, 0)` is 0.99999927.
- The new backend reproduces this exactly.

Conflicting evidence:
- `methodology/sus/ghg/beefmk/methodology.md` and `datasets/unfao/unfao_bfprod/documentation.md`: "beef and buffalo meat produced in kilograms per person".
- The same description says "UN population estimates were used"; the executable divides by World Bank population (`WB_POPULN`, `SP.POP.TOTL`).

Implementation decision in the new backend:
- Executable behaviour preserved: no unit conversion, World Bank population.

Reason:
- Converting the unit changes every BEEFMK score; that is a methodology change.

Potential impact:
- Fixture (`tests/golden/beefmk_cases.json`): the production part is within 1e-6 of 1.0 for all 114 observed scores, and every score lies between 0.61 and 0.96.
- Live, illustrative (FAOSTAT Food Balances bulk file of 2025-10-14, World Bank population of 2026-07-13, read 2026-10-08): scores range from 0.4999993 to 0.9985; the lowest are countries whose consumption reaches the 50 kg goalpost.

Question for methodology review:
- Should production be scored in kilograms per person, as described? If so, are 50 and 0 still the right goalposts for production?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/ghg/beefmk.py`, `sspi_flask_app/api/core/datasets/unfao/unfao_bfprod.py`, `methodology/sus/ghg/beefmk/methodology.md`

Relevant new-backend files:
- `src/sspi/indicators/beefmk.py`, `src/sspi/metadata/data/datasets/UNFAO_BFPROD.yaml`
- `tests/golden/beefmk_cases.json`, `tests/golden/test_golden_beefmk.py`

---

## BEEFMK-2 — The Food Balances start in 2010, so every 2000–2009 BEEFMK score is the 2010 score

Status: unresolved

Summary for the methodology team:
- Problem: the FAOSTAT Food Balances series the code reads starts in 2010. The impute route carries each country's earliest score back to 2000, so the 2000–2009 scores of every country are copies of its 2010 score. FAO publishes an older Food Balances series (to 2013) under another domain that the code does not read.
- Potential direction A: keep it (what the code does).
- Potential direction B: read the older Food Balances series for 2000–2009 as well, or leave 2000–2009 unscored.

Current executable behavior:
- The collectors request domain `FBS` (Food Balances, 2010 onwards). `impute_beefmk` carries each country's earliest observed score back to 2000 and its latest forward to 2023 (no interpolation), then gives Singapore the reference-class mean (see BEEFMK-3).
- The new backend reproduces this exactly.

Conflicting evidence:
- `methodology/sus/ghg/beefmk/methodology.md` does not mention imputation or the series' start year.

Implementation decision in the new backend:
- Executable behaviour preserved.

Reason:
- Choosing another source or leaving years unscored is a methodology decision.

Potential impact:
- Live, illustrative (as in BEEFMK-1): of the 1,560 SSPI67 country-years scored in 2000–2023, 664 are imputed, and 650 of those are 2000–2009 copies of a 2010 score (64 countries plus Singapore's reference-class rows).

Question for methodology review:
- Should 2000–2009 BEEFMK scores come from the older Food Balances series, stay carried back from 2010, or stay unscored?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/ghg/beefmk.py`, `sspi_flask_app/api/core/datasets/unfao/unfao_bfprod.py`, `sspi_flask_app/api/core/datasets/unfao/unfao_bfcons.py`

Relevant new-backend files:
- `src/sspi/indicators/beefmk.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/test_golden_beefmk.py`

---

## BEEFMK-3 — Japan is no longer in the Food Balances; the hard-coded recipient list names only Singapore

Status: unresolved

Summary for the methodology team:
- Problem: the impute route gives the reference-class mean of scores to a hard-coded list of countries "with no observations", which holds only Singapore. The current Food Balances bulk file has no rows for Japan either, so Japan, an SSPI67 country, gets no BEEFMK score at all.
- Potential direction A: keep it (what the code does): Japan is unscored.
- Potential direction B: give every SSPI67 country without Food Balances data the reference-class mean, found from the data rather than from a list (Japan and Singapore today).

Current executable behavior:
- `impute_beefmk` imputes `countries_no_data = ["SGP"]` for 2000–2023 with the flat mean of every observed score of every other country, every year. The list is applied whatever the data hold.
- If Singapore ever had observed scores the legacy route would store an observed and an imputed score for the same country-years. The new backend stops the run with an `ImputationError` instead, without choosing either (no precedence has been decided; see DEFRST-1 for how that was settled for DEFRST and CARBON).
- The new backend otherwise reproduces this exactly. Japan has World Bank population but no beef rows, so no BEEFMK score.

Conflicting evidence:
- The route's own comment: "From coverage report, SGP has no observations". The current source also lacks Japan: `FoodBalanceSheets_E_AreaCodes.csv` in the bulk artifact of 2025-10-14 lists neither.

Implementation decision in the new backend:
- Executable behaviour preserved: the list stays `["SGP"]`.

Reason:
- Adding a recipient changes which countries are scored; that is a methodology decision.

Potential impact:
- Live, illustrative (as in BEEFMK-1): Japan is the only SSPI67 country with no BEEFMK score; 24 of the 1,584 SSPI67 country-years in 2000–2023 are unscored, all Japan's.

Question for methodology review:
- Should Japan receive the reference-class mean like Singapore, and should the recipients be found from the data instead of a list?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/ghg/beefmk.py`

Relevant new-backend files:
- `src/sspi/indicators/beefmk.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/test_golden_beefmk.py`

---

## COALPW-1 — A country that uses no coal is never scored from data; its imputed score is a perfect 1.0, and a country with no energy data at all also scores 1.0

Status: unresolved

Summary for the methodology team:
- Problem: COALPW reuses the ALTNRG data and impute route (ALTNRG-2). The cleaner drops zero values, so a country with no coal has no coal row, and the first pass cannot score it in any year. The impute route then fills its coal with zero for 2000–2023 and scores it 1.0, flagged imputed. A country absent from the IEA data altogether gets zero for every fuel; the impute route scores a zero total as 1.0, a "perfect score", where ALTNRG scores the same case 0.0.
- Potential direction A: keep it (what the code does).
- Potential direction B: treat an absent or zero coal row as an observed zero (score 1.0, not flagged imputed), and leave a country with no energy data unscored rather than perfect.

Current executable behavior:
- `compute_coalpw` scores `goalpost(TLCOAL / (TLCOAL + NATGAS + NCLEAR + HYDROP + GEOPWR + BIOWAS + FSLOIL), 0.4, 0)` when all seven datasets have a value.
- `impute_coalpw` is the ALTNRG impute route line for line: SSPI67 countries with no row in a dataset get 0.0 there for 2000–2023 (labelled `PJ`), every series is carried back to 2000, forward to 2023 and interpolated, and only scores with a filled input are kept. Its formula returns 1.0 when the total is zero.
- The new backend reproduces this exactly.

Conflicting evidence:
- `methodology/sus/ghg/coalpw/methodology.md` gives the formula only and does not mention filling. Its prose writes the goalposts as `goalpost(..., 0, 0.4)` and, in the next sentence, as lower 0.40 and upper 0.0; the frontmatter and the code use 0.4 and 0.
- `api/core/sspi/sus/nrg/altnrg.py` scores the same all-zero case 0.0 ("worst score").

Implementation decision in the new backend:
- Executable behaviour preserved, including the 1.0 for a zero total.

Reason:
- Whether a missing fuel is a zero, and how a country with no data scores, are methodology decisions.

Potential impact:
- Fixture (`tests/golden/coalpw_cases.json`): the 59 SSPI67 countries absent from the sample score 1.0 for 2000–2023 (a fixture artefact that shows the rule).
- Live, illustrative (IEA `TESbySource`, read 2026-10-08): Ecuador, Iraq and Kuwait have no coal row; each scores 1.0, imputed, for all 24 years (72 country-years). No SSPI67 country is absent from every dataset today. Of the 1,584 SSPI67 country-years in 2000–2023, 956 are imputed.

Question for methodology review:
- Should no coal count as an observed zero, and should a country with no energy data be unscored instead of scoring 1.0?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/ghg/coalpw.py`, `sspi_flask_app/api/core/sspi/sus/nrg/altnrg.py`, `sspi_flask_app/api/datasource/iea.py`, `methodology/sus/ghg/coalpw/methodology.md`

Relevant new-backend files:
- `src/sspi/indicators/coalpw.py`, `src/sspi/indicators/strategy.py`
- `tests/golden/coalpw_cases.json`, `tests/golden/test_golden_coalpw.py`

---

## GTRANS-1 — GTRANS is described in tonnes per inhabitant; the code computes kilograms per person

Status: unresolved

Summary for the methodology team:
- Problem: the description and the dataset's unit label say "tonnes per inhabitant". The code multiplies the IEA's million-tonne figures by 10^9, which gives kilograms, and divides by population, so the scored quantity is kilograms per person. The goalposts, 7000 and 0, only make sense in kilograms (7 tonnes per person). Scores are consistent with that reading; the labels are not.
- Potential direction A: keep the labels as they are (what the code does).
- Potential direction B: relabel the dataset and the description as kilograms of transport CO2 (a national total) and the indicator as kilograms per person; scores do not change.

Current executable behavior:
- `clean_iea_tco2em` keeps the `CO2BySector` rows whose `seriesLabel` is "Transport Sector", multiplies the value (unit `MtCO2`) by 10^9 and labels it "Tonnes C02 per inhabitant". The cleaner drops zero values.
- `compute_gtrans` scores `goalpost(IEA_TCO2EM / WB_POPULN, 7000, 0)`. `impute_gtrans` carries the CO2 series forward to 2023 within 2000–2023 and divides by that year's population.
- The new backend reproduces this exactly, keeping the legacy label; the conversion is declared in canonical metadata (`source.published_unit`, `source.value_multiplier`).

Conflicting evidence:
- `methodology/sus/ghg/gtrans/methodology.md`: "CO2 emissions from transport in tonnes per inhabitant, tonnes referring to thousands of kilograms".
- The dataset label "Tonnes C02 per inhabitant" describes neither the stored national total nor its unit.

Implementation decision in the new backend:
- Executable behaviour and labels preserved.

Reason:
- The label is part of the legacy parity evidence; changing documented units is for the methodology team.

Potential impact:
- No score changes under either direction. Live, illustrative (IEA `CO2BySector` and World Bank population, read 2026-10-08): the United States emitted about 5,050 kg of transport CO2 per person in 2023 (GTRANS 0.28).

Question for methodology review:
- Should the description and unit labels say kilograms per person?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/iea/iea_tco2em.py`, `sspi_flask_app/api/core/sspi/sus/ghg/gtrans.py`, `methodology/sus/ghg/gtrans/methodology.md`

Relevant new-backend files:
- `src/sspi/indicators/gtrans.py`, `src/sspi/ingestion/units.py`, `src/sspi/metadata/data/datasets/IEA_TCO2EM.yaml`
- `tests/golden/test_golden_gtrans.py`, `tests/golden/test_golden_ghg_datasets.py`

---

## MSWGEN-1 — MSWGEN applies a 100 → 0 goalpost to an EPI score that already rewards less waste, reversing its direction

Status: unresolved

Summary for the methodology team:
- Problem: `EPI_MSWGEN` is not kilograms of waste per person. It is the 2024 EPI's waste-per-capita *indicator score* (series `WPC`, 0–100), on which the EPI already gives lower waste a higher score: the United States scores 13.3, Pakistan 64.2. The SSPI code then scores it with `goalpost(EPI_MSWGEN, 100, 0)`, i.e. 1 − EPI/100, a "lower is better" goalpost meant for a raw quantity. Applied to a score where higher is already better, it turns the ranking upside down: the most waste-intensive countries get the best MSWGEN scores. The 2018 static SSPI instead scored raw kilograms per person (What a Waste 2.0) against a 750 → 0 goalpost, which ranks countries the other way round.
- Potential direction A: preserve the executable legacy behaviour (what the new backend does).
- Potential direction B: restore the apparent intended waste-per-capita interpretation, either by scoring the EPI score in its own direction (for example `goalpost(EPI_MSWGEN, 0, 100)`) or by scoring a raw kilograms-per-person series as the 2018 SSPI did. Either changes every MSWGEN score; the second also needs a source (see `docs/indicator-migration.md`).

Current executable behavior:
- `clean_epi_nitrog` in `epi_mswgen.py` (registered for `EPI_MSWGEN`) stores the `WPC_ind_na.csv` values of `epi2024indicators.zip` unchanged, labelled `Index`; NaN and negative values are dropped, zeros kept.
- `compute_mswgen` scores `goalpost(EPI_MSWGEN, 100, 0)` for every row; there is no impute route.
- The new backend reproduces this exactly on the committed 2024 fixture.

Conflicting evidence:
- `datasets/epi/epi_mswgen/documentation.md`: "Currently, this dataset pulls the indicator index value. Ideally we would change this to look at the underlying data instead". `methodology/sus/wst/mswgen/methodology.md`: "Current goalposts are set to take in index data from EPI. TODO: Pull Raw EPI Data for Indicators to Get Actual Values."
- The canonical description (from the methodology file) is "Annual amount of per capita Municipal Solid Waste (kg/capita/year)"; the dataset's unit is `Index`.
- In the EPI file a higher score means less waste per person (fixture, 2018: United States 13.3, Austria 23.0, Malaysia 32.3, Pakistan 64.2).
- `local/SSPIStaticData2018.csv` and `local/IndicatorDetailsStatic.csv`: MSWGEN_RAW is kilograms per person (United States 811.86, Austria 588.00) scored with goalposts "(0,750) V", i.e. `goalpost(raw, 750, 0)`: United States 0.000, Austria 0.216. The static file lists the lower goalpost as 50, which its own scores do not use.

Implementation decision in the new backend:
- Executable behaviour preserved; no direction adopted.

Reason:
- Changing the direction or the input is a methodology change.

Potential impact:
- Every MSWGEN score. From the committed 2024 fixture, 2018: United States 0.867, Austria 0.77, Malaysia 0.677, Pakistan 0.358 under the legacy formula; under `goalpost(EPI_MSWGEN, 0, 100)` they would be 0.133, 0.23, 0.323, 0.642. The 2018 static scores (a different source and year) were United States 0.000, Austria 0.216.
- The 53 reported EPI zeros (the worst EPI score) receive a perfect 1.0 under the legacy formula.

Question for methodology review:
- Should MSWGEN keep the executable goalpost, score the EPI score in its own direction, or return to a raw kilograms-per-person series?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/wst/mswgen.py`, `sspi_flask_app/api/core/datasets/epi/epi_mswgen.py`, `sspi_flask_app/api/datasource/epi.py`
- `methodology/sus/wst/mswgen/methodology.md`, `datasets/epi/epi_mswgen/documentation.md`, `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/mswgen.py`, `src/sspi/metadata/data/indicators/MSWGEN.yaml`, `src/sspi/metadata/data/datasets/EPI_MSWGEN.yaml`
- `tests/golden/test_golden_mswgen.py`, `tests/fixtures/epi/epi2024indicators_P5_Indicator_WPC_ind_na.csv`

---

## RECYCL-1 — RECYCL's executable goalposts are 0 → 100; the 2018 static scores use 0 → 70

Status: unresolved

Summary for the methodology team:
- Problem: the code scores the recycling rate with `goalpost(WB_RECYCL, 0, 100)`, so only a country recycling everything scores 1.0. The 2018 static SSPI scored the same quantity against 0 → 70, so 70 % recycling already scored 1.0.
- Potential direction A: preserve the executable 0 → 100 goalposts.
- Potential direction B: use the 0 → 70 goalposts of the 2018 static SSPI.

Current executable behavior:
- `compute_recycl` scores `goalpost(WB_RECYCL, 0, 100)`; `impute_recycl` carries each country's scores back to 2000 and forward to 2023 and gives SSPI67 members with no score the reference-class average.
- `WB_RECYCL` has no collector or cleaner at the pinned commit, so the legacy backend produced no RECYCL scores. RECYCL is not ported (source decision pending, see `docs/indicator-migration.md`).

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv`: GoalpostString "(0,70)", not inverted; its LowerGoalpost and UpperGoalpost columns are both 0.
- `local/SSPIStaticData2018.csv`: RECYCL_SCORE = RECYCL_RAW / 70 (Austria 25.66 -> 0.367, Singapore 61.00 -> 0.871, United States 34.60 -> 0.494).

Implementation decision in the new backend:
- None yet; RECYCL is not executable. A port would preserve 0 → 100.

Reason:
- The executable goalposts are the legacy methodology; the static file is evidence.

Potential impact:
- Every RECYCL score below 70 %. 2018 static raw values: Austria 0.257 under 0 → 100 against 0.367 published; Singapore 0.61 against 0.871.

Question for methodology review:
- Which goalposts should RECYCL use?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/wst/recycl.py`, `methodology/sus/wst/recycl/methodology.md`, `datasets/wb/wb_recycl/documentation.md`, `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/RECYCL.yaml`, `src/sspi/metadata/data/datasets/WB_RECYCL.yaml`, `docs/indicator-migration.md`

---

## STCONS-1 — STCONS is described as the top 10 % share of CO2 emissions; the formula is an estimated ecological footprint per person of the top decile

Status: unresolved

Summary for the methodology team:
- Problem: the description says "Proportion of CO2 Emissions attributable to the Top 10% of earners". The formula multiplies the Global Footprint Network's ecological footprint per person (global hectares) by the ratio of the top decile's average carbon footprint to the national average (WID), which estimates global hectares per person in the top decile, not a proportion. The methodology text leaves the upper goalpost as "TODO: SET GOALPOST" although 1.6 is in the metadata.
- Potential direction A: keep the executable formula and goalposts (30 → 1.6) and correct the description.
- Potential direction B: score what the description says, the top decile's share of emissions.

Current executable behavior:
- `compute_stcons` scores `goalpost(FPI_ECOFPT_PER_CAP * WID_CARBON_TOT_P90P100 / WID_CARBON_TOT_P0P100, 30, 1.6)`; `impute_stcons` extrapolates and interpolates each input over 2000–2023 and gives SSPI67 members with no input the reference-class average.
- STCONS is not ported (the footprint source needs an access decision, see `docs/indicator-migration.md`).

Conflicting evidence:
- `methodology/sus/wst/stcons/methodology.md`: description "Proportion of CO2 Emissions attributable to the Top 10% of earners"; "we set the Goalpost at TODO: SET GOALPOST"; the interpretation section describes the footprint of the top decile.
- `datasets/wid/wid_carbon_tot_p90p100/documentation.md`: `lpfghgi999` is average per capita group emissions (tCO2e per person), not a share.

Implementation decision in the new backend:
- None yet; STCONS is not executable.

Reason:
- The executable formula is the legacy methodology; the description is evidence.

Potential impact:
- No score change under direction A (labels only); direction B is a different indicator.

Question for methodology review:
- Is STCONS the top decile's estimated footprint, as computed, or a share of emissions, as described?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/sus/wst/stcons.py`, `methodology/sus/wst/stcons/methodology.md`, `sspi_flask_app/api/datasource/fpi.py`, `datasets/wid/wid_carbon_tot_p90p100/documentation.md`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/STCONS.yaml`, `docs/indicator-migration.md`

---

## PUPTCH-1 — PUPTCH's source series ends in 2019 and is no longer produced; the impute route carries each country's last value, however old, to 2023

Status: unresolved

Summary for the methodology team:
- Problem: the World Bank's `SE.PRM.ENRL.TC.ZS` ("Pupil-teacher ratio, primary", all teachers) has values up to 2018 for most countries and 2019 for four. The UNESCO Institute for Statistics, which WDI republishes, now publishes primary pupil–teacher ratios only for trained or qualified teachers (`PTRHC.1.TRAINED`, `PTRHC.1.QUALIFIED`). The impute route carries every country's last value forward to 2023 with no limit on distance, so most 2019–2023 PUPTCH scores are carried values, and some reach back decades (Venezuela's 1987 value fills 1988–2023; Australia's 1999 value fills 2000–2023).
- Potential direction A: preserve the series and the unbounded carry-forward.
- Potential direction B: bound the carry-forward, or change the source series (a trained- or qualified-teacher ratio is a different measure).

Current executable behavior:
- `compute_puptch` scores every clean `WB_PUPTCH` row with `goalpost(WB_PUPTCH, 40, 9)`, all years.
- `impute_puptch` carries each country's series forward to 2023 and backward to 2000 and interpolates interior gaps (`impute_only=True`), then scores; no reference class.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json`, PUPTCH: "Moderate Data Issues, Attention Required. Coverage seems to stop between 2015 and 2020 not sure why. Will need to examine the UNESCO documentation to see why this is no longer reported."
- `local/SSPIStaticData2018.csv`: United States 15.2 for 2018; the current series has no United States value after 2017 (14.2). The 49 static raw/score pairs all agree with the 40 → 9 goalposts.
- World Bank indicator metadata (`https://api.worldbank.org/v2/indicator/SE.PRM.ENRL.TC.ZS`): source organization the UIS bulk data download service. UIS indicator list (`https://api.uis.unesco.org/api/public/definitions/indicators`, 2026-10-08): no all-teacher primary pupil–teacher ratio.

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(score_puptch, (2000, 2023))` reproduces both routes; exact parity on the committed fixture.

Reason:
- Executable legacy behavior is preserved until a decision.

Potential impact:
- Every PUPTCH score after each country's last observation. On the live series of 2026-10-08, 2019–2023 scores are imputed for every country except the four with a 2019 value, and those four are imputed for 2020–2023.

Question for methodology review:
- Should PUPTCH keep a series that is no longer updated, and should carried values be limited in distance?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/edu/puptch.py`, `sspi_flask_app/api/core/datasets/wb/wb_puptch.py`, `datasets/wb/wb_puptch/documentation.md`, `methodology/pg/edu/puptch/methodology.md`, `local/2025-06-25-indicator-status.json`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/puptch.py`, `tests/golden/test_golden_puptch.py`, `tests/fixtures/wb/README.md`

---

## ENRPRI-1 — ENRPRI and ENRSEC are described as net enrolment rates; the series requested are UIS *total* net enrolment rates

Status: unresolved

Summary for the methodology team:
- Problem: the descriptions say children of official primary (secondary) age "enrolled in primary (secondary) education". The collectors request `NERT.1.CP` and `NERT.2.CP`, which UIS names "Total net enrolment rate, primary / lower secondary, both sexes (%)": a total net rate also counts children of that age enrolled at a higher level. ENRSEC's description says "secondary"; its series and name are lower secondary. The 2018 static file describes ENRSEC as lower-secondary-age students enrolled in lower secondary "or in any lower grade (primary education)", and gives the source as UN SDG 4.1.1.
- Potential direction A: keep the total net enrolment series and correct the descriptions.
- Potential direction B: request the series the descriptions describe.

Current executable behavior:
- `collect_uis_enrpri` / `collect_uis_enrsec` request `NERT.1.CP` / `NERT.2.CP`; the cleaners label them "Net enrollment in primary school (%)" and "Net enrollment in lower secondary school (%)"; scores are `goalpost(UIS_ENRPRI, 80, 100)` and `goalpost(UIS_ENRSEC, 70, 100)`.

Conflicting evidence:
- `methodology/pg/edu/enrpri/methodology.md`, `methodology/pg/edu/enrsec/methodology.md`, `datasets/uis/uis_enrpri/documentation.md`, `datasets/uis/uis_enrsec/documentation.md`: the descriptions above.
- `local/IndicatorDetailsStatic.csv`: ENRSEC described as "enrolled in lower secondary or in any lower grade (primary education)"; source UN SDG, 4.1.1, for both.
- UIS indicator definitions (`https://api.uis.unesco.org/api/public/definitions/indicators`, 2026-10-08): the names above.
- The 2018 static raw/score pairs agree with the executable goalposts (49 of 49 for each).

Implementation decision in the new backend:
- Direction A's executable half: `NERT.1.CP` and `NERT.2.CP` are kept (`UIS_ENRPRI`, `UIS_ENRSEC`, read by `sspi.ingestion.uis`); the descriptions are unchanged. Exact parity on the committed fixtures.

Reason:
- The executable series is the legacy methodology; the descriptions are evidence.

Potential impact:
- None under direction A (labels only). Under direction B, every ENRPRI and ENRSEC score.

Question for methodology review:
- Are ENRPRI and ENRSEC meant to be total net enrolment rates, and is ENRSEC lower secondary?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/uis/uis_enrpri.py`, `sspi_flask_app/api/core/datasets/uis/uis_enrsec.py`, `sspi_flask_app/api/datasource/uis.py`, the methodology and documentation files above, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/enrpri.py`, `src/sspi/indicators/enrsec.py`, `src/sspi/ingestion/uis.py`, `src/sspi/metadata/data/indicators/ENRPRI.yaml`, `src/sspi/metadata/data/indicators/ENRSEC.yaml`, `src/sspi/metadata/data/datasets/UIS_ENRPRI.yaml`, `src/sspi/metadata/data/datasets/UIS_ENRSEC.yaml`

---

## ENRSEC-1 — ENRSEC gives China and Nigeria the mean of every country's every year

Status: unresolved

Summary for the methodology team:
- Problem: `impute_enrsec` adds `impute_reference_class_average("CHN", 2000, 2023, "Dataset", "UIS_ENRSEC", clean_enrsec)` and the same for Nigeria. The "reference class" is every clean `UIS_ENRSEC` row: every country in the source (not SSPI67), every year from 1970 on (not 2000–2023). Both countries get that one value for every year 2000–2023. The recipients are hard-coded, and the rows are added whether or not the country has data. ENRPRI has the same line for China, commented out.
- Potential direction A: preserve the hard-coded recipients and the all-rows mean.
- Potential direction B: restrict the reference class (for example to SSPI67, or to the target years), or derive the recipients from the data.

Current executable behavior:
- As above. Neither China nor Nigeria has a `NERT.2.CP` row in the live UIS source (release `20260507-91260335`, read 2026-10-09), so today there is no observed/imputed collision; if either gains data, the legacy route would store both an observed score and imputed ones for the same years.
- With no `UIS_ENRSEC` row at all, the legacy impute route raised (`ValueError: Reference data cannot be empty.`).

Conflicting evidence:
- `sspi_flask_app/api/core/sspi/pg/edu/enrsec.py` against `enrpri.py` (the same line commented out) and against the SSPI67 reference classes the other ported routes use.
- `local/2025-06-25-indicator-status.json`, ENRSEC: "Finalization in Progress. Just need to run stock imputations and clean up a little bit."

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(score_enrsec, (2000, 2023), listed_recipients=("CHN", "NGA"))` reproduces the route (exact parity; the China and Nigeria value is the unweighted mean of every row). If China or Nigeria has any observed row, the strategy raises `ImputationError` before anything is scored or written, and no precedence is chosen. With no rows at all it raises, as legacy did.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Every ENRSEC score of China and Nigeria.

Question for methodology review:
- What should China's and Nigeria's ENRSEC values be when the source has none?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/edu/enrsec.py`, `sspi_flask_app/api/core/sspi/pg/edu/enrpri.py`, `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`)

Relevant new-backend files:
- `src/sspi/indicators/enrsec.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore`), `tests/golden/test_golden_enrollment.py`, `tests/unit/test_education_indicators.py`

---

## YRSEDU-1 — YRSEDU drops the zeros UIS reports for countries without compulsory schooling, and backward extrapolation gives those years a later law's value

Status: unresolved

Summary for the methodology team:
- Problem: `YEARS.FC.COMP.1T3` reports 0 years, with magnitude `NIL`, where a country had no compulsory primary or secondary schooling in law: 564 of 5,894 records in release `20260507-91260335`, 42 areas, including the SSPI67 members Malaysia (1998-2002), Indonesia (1998-2001), India (1998-2008), Nigeria (1998-2003) and Singapore (1998-1999). The shared UIS cleaner drops every falsy value, so a 0 never reaches scoring. The YRSEDU impute route then carries each country's *first* remaining value back to 2000, so the years without a law take the later law's value: India 2000-2008 scores as 8 years (0.333) instead of 0 years (0); Indonesia and Nigeria score 0.5 instead of 0; Oman, outside SSPI67, 0.667 for 2000-2014. A 0 before 2000 leaves no score, and a 0 after an earlier value leaves no score at all (St Helena after 1998); an area that reports only zeros has no YRSEDU score in any year (13 of the 214 areas, none in SSPI67). Because 6 years or fewer already score 0, Malaysia's result is unchanged (6 years carried, 0.0).
- Potential direction A: preserve the zero drop and the backward carry.
- Potential direction B: keep the reported zeros as observations (they would score 0), at least for this series.

Current executable behavior:
- `clean_uis_data` skips `value == "NaN" or value is None or not value`, which includes 0. `compute_yrsedu` scores `goalpost(UIS_YRSEDU, 6, 12)` on what remains; `impute_yrsedu` only calls `extrapolate_backward(..., 2000, impute_only=True)`: no forward extrapolation and no interpolation.

Conflicting evidence:
- UIS indicator definition (`https://api.uis.unesco.org/api/public/definitions/indicators`): "Number of years of compulsory primary and secondary education guaranteed in legal frameworks"; a 0 is a reported value, flagged `NIL`, not a missing one.
- The same falsy test is harmless for the enrolment series, which have no zeros; it was written for them and shared.

Implementation decision in the new backend:
- Direction A: the UIS adapter drops falsy values for every UIS dataset, as the shared legacy cleaner did, and `SeriesFillThenScore(score_yrsedu, (2000, 2023), steps=("backward",))` reproduces the route. Exact parity on the committed fixture, whose 52 zeros include all of the cases above.

Reason:
- Executable legacy behavior is preserved until a decision.

Potential impact:
- On the live release (2026-10-09), 2000-2023 SSPI67 country-years where the source reports 0 but YRSEDU scores a carried later value: India 9, Nigeria 4, Malaysia 3, Indonesia 2 (Singapore's zeros are before 2000); only Malaysia's scores are unaffected.
- Outside SSPI67, 264 country-years 2000-2023 that the source reports as 0 have no score at all (14 areas, for example Bhutan, Papua New Guinea, Mozambique).

Question for methodology review:
- Should a reported 0 years of compulsory schooling be scored (as 0) rather than dropped?

Relevant legacy files:
- `sspi_flask_app/api/datasource/uis.py` (`clean_uis_data`), `sspi_flask_app/api/core/datasets/uis/uis_yrsedu.py`, `sspi_flask_app/api/core/sspi/pg/edu/yrsedu.py`, `sspi_flask_app/api/resources/utilities.py` (`extrapolate_backward`)

Relevant new-backend files:
- `src/sspi/ingestion/uis.py`, `src/sspi/indicators/yrsedu.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore`), `tests/golden/test_golden_yrsedu.py`

---

## YRSEDU-2 — The 2018 static SSPI used compulsory education only inside child labour (CHILDW), with goalposts 5 → 12; the executable indicator is a separate Education indicator scored 6 → 12

Status: unresolved

Summary for the methodology team:
- Problem: in the 2018 static SSPI, years of compulsory education was not an Education indicator. It was the intermediate `YSCEDU` (also written `YRCEDU`) of `CHILDW`, Child Worker Engagement (Market Structure / Worker Engagement): a country whose child labour rate was statistically indistinguishable from zero scored between 0.50 and 1.00 on compulsory education, with goalposts 5 → 12. The pinned executable scores YRSEDU on its own, in Education, from 0 to 1 with goalposts 6 → 12. A note says CHILDW lost its dynamic data and YRSEDU was "moved back to Education". Two legacy structure files list Education without YRSEDU.
- Potential direction A: keep YRSEDU as an Education indicator with goalposts 6 → 12.
- Potential direction B: return to 5 → 12, or to the conditional child-labour construction.

Current executable behavior:
- `compute_yrsedu` scores `goalpost(UIS_YRSEDU, 6, 12)` (goalposts read from `methodology/pg/edu/yrsedu/methodology.md`); `methodology/pg/edu/methodology.md` and `sspi_flask_app/custom-sspi.json` list it under Education.

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv`, CHILDW: "If the child labor rate in a country is statistically indistinguishable from zero, a country scores between 0.50 and 1.00 based on years of compulsory education"; GoalpostString "(0, 10)V (5, 12)"; IntermediateCodes ["CHLDLB", "YRCEDU"].
- `local/IntermediateDetailsStatic.csv`, YSCEDU: LowerGoalpost 5, UpperGoalpost 12.
- `local/indicator-problems.json`: "CHILDW": "Dynamic Data is not available. Moving YRSEDU back to Education".
- `local/sspi-categories.json` and `local/sspi-structure.json`: Education is ENRPRI, ENRSEC, PUPTCH (no YRSEDU).
- `local/SSPIStaticData2018.csv` has CHILDW scores only, no compulsory-education raw values, so no raw/score pair can be checked.

Implementation decision in the new backend:
- Direction A: the executable indicator, goalposts and category, as at the pinned commit (the canonical catalog lists YRSEDU under Education).

Reason:
- The executable code is the legacy methodology; the static files are evidence.

Potential impact:
- Under 5 → 12, every country with 6 to 11 years would score higher (6 years: 0.143 instead of 0).

Question for methodology review:
- Is YRSEDU meant to be an Education indicator scored 6 → 12, and should the structure files list it?

Relevant legacy files:
- `methodology/pg/edu/yrsedu/methodology.md`, `methodology/pg/edu/methodology.md`, `local/IndicatorDetailsStatic.csv`, `local/IntermediateDetailsStatic.csv`, `local/indicator-problems.json`, `local/sspi-categories.json`, `local/sspi-structure.json`

Relevant new-backend files:
- `src/sspi/indicators/yrsedu.py`, `src/sspi/metadata/data/indicators/YRSEDU.yaml`

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
