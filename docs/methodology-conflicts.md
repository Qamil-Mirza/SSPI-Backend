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
| Licensing, redistribution rights or required attribution of source data | `docs/data-governance-review.md` (`GOV-n`); see below |

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

## Reviewed alongside this file: data-governance items

These open items are **DATA-GOVERNANCE / LICENSING REVIEW** questions, not
methodology decisions. No formula, source identifier, imputation or score
depends on them, so they are not entries here. They are listed so the
research team discusses them together with the open methodology questions.

| ID | Question | Where | Status |
|---|---|---|---|
| GOV-1 | WHO GHO data (ATBRTH, DPTCOV, PHYSPC): which WHO terms govern the GHO API; whether WHO extracts may be redistributed in the SSPI repository; whether ATBRTH's per-row third-party source credits impose further conditions; whether DPTCOV (WUENIC) needs separate UNICEF permission; what attribution is required | [`data-governance-review.md`](data-governance-review.md#gov-1--who-global-health-observatory-data-governing-terms-redistribution-of-extracts-third-party-credits-unicef-permission-attribution) | open |
| GOV-2 | WEF Historical Competitiveness Data (AQELEC's `WEF_QUELEC`): which terms govern the World Bank-hosted workbook (CC BY-NC-ND 4.0 per the WEF terms and the workbook itself); whether SSPI's use is non-commercial; whether extracts, the database or derived AQELEC scores may be shared; what attribution is required | [`data-governance-review.md`](data-governance-review.md#gov-2--wef-historical-competitiveness-data-governing-licence-non-commercial-use-redistribution-of-extracts-and-of-the-database-derived-scores-attribution) | open |
| GOV-3 | UNODC prisons workbook (PRISON's `UNODC_PRIPOP`): which terms govern data.unodc.org downloads; the UN website terms grant only personal, non-commercial use without redistribution or derivative works (a confirmed restriction if they apply); whether PRISON scores may be published; attribution | [`data-governance-review.md`](data-governance-review.md#gov-3--unodc-prisons-workbook-governing-terms-the-un-website-terms-bar-on-redistribution-and-derivative-works-derived-prison-scores-attribution) | open |
| GOV-4 | ITU Global Cybersecurity Index transcription (CYBSEC's `ITU_CYBSEC`): which terms govern each edition's scores (CC BY-NC-SA 3.0 IGO for 2024); whether the SSPI's hand transcription and CYBSEC scores are adaptations; redistribution; attribution | [`data-governance-review.md`](data-governance-review.md#gov-4--itu-global-cybersecurity-index-transcription-rights-in-the-sspis-hand-transcription-of-itu-report-tables-non-commercial-share-alike-terms-redistribution-attribution) | open |
| GOV-5 | Fragile States Index workbooks (SECAPP's `FSI_SECAPP`): no licence or terms of use found for the published data; whether extracts or SECAPP scores may be redistributed; attribution | [`data-governance-review.md`](data-governance-review.md#gov-5--fragile-states-index-workbooks-no-licence-or-terms-found-for-the-published-data-redistribution-of-extracts-derived-secapp-scores-attribution) | open |

Meanwhile the backend ingests and scores the real WHO data. The repository's
automated WHO parity tests run on synthetic fixtures, and the real-data
parity evidence is kept outside the repository for opt-in validation
(project-owner decision of 2026-10-19).

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

Entries added after the quiz (BEEFMK-1, BEEFMK-2, BEEFMK-3, COALPW-1, GTRANS-1, from the Greenhouse Gases port; MSWGEN-1, RECYCL-1, STCONS-1, from the Waste characterization; PUPTCH-1, ENRPRI-1, ENRSEC-1, YRSEDU-1, YRSEDU-2, from the Education port; CRPTAX-1, TAXREV-1, TAXREV-2, TAXREV-3, TXRDST-1, TXRDST-2, from the Tax port; UNEMPB-1, UNEMPB-2, UNEMPB-3, FATINJ-1, FATINJ-2, MATERN-1, SENIOR-1, SENIOR-2, SENIOR-3, from the Worker Wellbeing port; CSTUNT-1, CSTUNT-2, CSTUNT-3, ATBRTH-1, DPTCOV-1, FAMPLN-1, PHYSPC-1, from the Healthcare port) have not been reviewed.

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
| CRPTAX-1 | The executable source is the combined central and subnational statutory rate; the 2018 static values for 12 of 49 countries are central-government rates | unresolved |
| TAXREV-1 | TAXREV gives Vietnam, Nigeria, Venezuela and Algeria the mean of every country's every year | unresolved |
| TAXREV-2 | Pakistan has no tax revenue data and is not on the hard-coded list, so it never gets a TAXREV score | unresolved |
| TAXREV-3 | TAXREV is central-government tax revenue, and the impute route carries a country's last value forward however old (Japan from 1993) | unresolved |
| TXRDST-1 | The methodology's score function says goalposts −10 → −100; the executable reads −10 → 100 | unresolved |
| TXRDST-2 | "Induced by the tax code" is measured with post-tax national income, which includes transfers and public spending; the unit label is ISHRAT's | unresolved |
| UNEMPB-1 | Imputed UNEMPB scores carry the unit label "Tax Rate" | unresolved |
| UNEMPB-2 | UNEMPB gives Iceland the mean of every country's every year | unresolved |
| UNEMPB-3 | Most UNEMPB scores are filled from a few reported years; one value can stand for twenty-four years | unresolved |
| FATINJ-1 | FATINJ has no imputation; most countries report one year, and thirteen SSPI67 countries none | unresolved |
| FATINJ-2 | National fatal injury rates count different things and are compared without adjustment | unresolved |
| MATERN-1 | MATERN has no executable implementation and no identified source | unresolved |
| SENIOR-1 | The legacy SENIOR route cannot run, and its inputs never share a year | unresolved |
| SENIOR-2 | "Years in retirement" is computed as life expectancy at birth minus the retirement age | unresolved |
| SENIOR-3 | The poverty component rewards higher old-age poverty | unresolved |
| CSTUNT-1 | Series-filled CSTUNT scores carry the unit label "Coefficient" | unresolved |
| CSTUNT-2 | CSTUNT predicts stunting from nominal GDP per capita for every country without data, for every year since 1960, and gives eleven SSPI67 countries a perfect score | unresolved |
| CSTUNT-3 | The 2018 static CSTUNT values come from IHME, not the UN series the code reads | unresolved |
| ATBRTH-1 | ATBRTH gives five hard-coded countries the mean of every country's every year | unresolved |
| DPTCOV-1 | DPTCOV is described as survey coverage of children aged 12–23 months; the series is the WHO/UNICEF estimate for one-year-olds | unresolved |
| FAMPLN-1 | FAMPLN produces no score, and its description, data and goalposts describe three different measures | unresolved |
| PHYSPC-1 | PHYSPC scores WHO's workforce figures as published, including an implausible Austrian 2018 value, and the series has been revised since 2018 | unresolved |
| FSTABL-1 | FSTABL has no executable implementation: its IMF dataset was never defined, and a World Bank nonperforming-loans collector was added but never wired to a score | unresolved |
| FDEPTH-1 | The legacy FDEPTH impute route raises on every input, so no FDEPTH score was ever imputed, although the methodology describes imputation | unresolved |
| FDEPTH-2 | FDEPTH's executable goalposts are 0 → 200 (credit) and 0 → 100 (deposits); the 2018 static scores used 0 → 190 and 0 → 200 | unresolved |
| FDEPTH-3 | The "financial system deposits" input is the GFDD series of bank deposits only, from a database last updated in 2022 | unresolved |
| PUBACC-1 | PUBACC has no imputation; scores exist only in Findex survey years | unresolved |
| AQELEC-1 | AQELEC's quality input is a WEF survey series read from a spreadsheet no supported source covers, and it ends in 2017 | unresolved |
| SANSRV-1 | SANSRV's executable goalposts are 50 → 100; the 2018 static scores used 0 → 100 | unresolved |
| SANSRV-2 | SANSRV's impute route only extrapolates: a country's last value is carried to 2023 however old, and interior gaps are never filled | unresolved |
| DRKWAT-1 | DRKWAT has no imputation, so countries without a safely managed water estimate are never scored, and the 2018 static values differ from today's series | unresolved |
| INTRNT-1 | INTRNT's executable route reads datasets the metadata does not list, averages two raw values of different kinds, and the legacy database refused every such score | unresolved |
| TRNETW-1 | TRNETW has no executable implementation and no defined source | unresolved |
| MURDER-1 | The World Bank cleaner treats a reported zero homicide rate as missing, and the impute route then fills it | unresolved |
| MURDER-2 | MURDER's impute route carries every series to 2000 and 2023 and interpolates every gap, however far the nearest observation is | unresolved |
| CYBSEC-1 | The pinned CYBSEC ingestion cannot store the transcription: it reads a path that no longer exists, and five country names have no code | resolved |
| CYBSEC-2 | CYBSEC compares GCI editions built on different scales and methods, and dates each by its edition label | unresolved |
| CYBSEC-3 | Canada, an SSPI67 member, is missing from the GCI transcription | unresolved |
| SECAPP-1 | No FSI value was ever stored by the pinned legacy code: its collector, raw document shape, source query and cleaner all fail | resolved |
| SECAPP-2 | SECAPP's status note promises backward extrapolation that no route implements, and FSI editions are dated by their edition year | unresolved |
| SECAPP-3 | Israel's FSI unit of assessment changes in 2021, from "Israel and West Bank" to Israel alone | unresolved |
| PRISON-1 | The United Kingdom's prison rate is the unweighted mean of whichever jurisdictions reported that year | unresolved |
| PRISON-2 | China, with no UNODC series, gets the flat mean of every value in the workbook for 2000–2023; observed Chinese data would stop the route | unresolved |
| PRISON-3 | PRISON's series fill carries old or single values across the whole 2000–2023 window | unresolved |
| PRISON-4 | Iraq's sub-national prison rates are dropped, not combined, so a single national value is carried over 24 years | unresolved |

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

## CRPTAX-1 — The executable source is the combined central and subnational statutory rate; the 2018 static values for 12 of 49 countries are central-government rates

Status: unresolved

Summary for the methodology team:
- Problem: CRPTAX is described only as "Tax imposed on the net income of the company." The executable dataset `TF_CRPTAX` is the Tax Foundation's `rates_final.csv` (worldwide corporate tax rates, 1980–2024), which reports the *combined* statutory corporate income tax rate: central government plus the average subnational rate, including surtaxes. The 2018 static SSPI used the same number for 37 of its 49 countries but a central-government (federal) rate for the other 12: Canada 15 (Tax Foundation 26.8), Germany 15 (29.8), Switzerland 8.5 (21.1), United States 21 (25.8), Luxembourg 18 (26.0), Portugal 21 (31.5), Japan 23.2 (29.7), Italy 24 (27.8), India 30 (35.0), Korea 25 (27.5), France 33.33 (34.4), Belgium 29 (29.6). A higher rate scores higher (`goalpost(TF_CRPTAX, 0, 40)`); that direction agrees with the static scores (raw / 40 for all 49), and nothing in the methodology states it.
- Potential direction A: keep the combined statutory rate (the executable source).
- Potential direction B: use central-government statutory rates, as the 2018 static values did for federal and some other countries.

Current executable behavior:
- `clean_tax_foundation` melts the wide CSV (`iso_3` × year columns) to rows, drops `NA` cells only, so a reported 0 % rate (for example Bahrain, the United Arab Emirates until 2022: 536 zero cells) is kept and scores 0. There is no country or year filter: every `iso_3` in the file is kept, territories included.
- `compute_crptax` scores every row with `goalpost(TF_CRPTAX, 0, 40)`, unit "Tax Rate"; `impute_crptax` extrapolates backward to 2000 and interpolates interior gaps, with no forward extrapolation.

Conflicting evidence:
- `local/SSPIStaticData2018.csv` (`CRPTAX_RAW`) against `https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv` (year 2018), the file `sspi_flask_app/api/datasource/taxfoundation.py` downloads.
- `local/IndicatorDetailsStatic.csv`, CRPTAX: source "Tax Foundation", `https://taxfoundation.org/data/all/global/corporate-tax-rates-by-country-2023/`, goalposts (0, 40), not inverted.

Implementation decision in the new backend:
- Direction A: the executable source and formula, as at the pinned commit. The Tax Foundation adapter reads exactly the January 2025 edition the legacy collector downloaded (source approved 2026-10-09), and CRPTAX reproduces the compute and impute routes with exact parity. The static values are not used.

Reason:
- The executable code is the legacy methodology; the static values are evidence of a disagreement, not an instruction to change the formula.

Potential impact:
- Every CRPTAX score of the 12 countries above (Germany 2018: 0.746 under the executable source, 0.375 in the 2018 static SSPI).

Question for methodology review:
- Is CRPTAX the combined statutory rate, or the central-government rate? Should a higher corporate tax rate score higher?

Relevant legacy files:
- `sspi_flask_app/api/datasource/taxfoundation.py`, `sspi_flask_app/api/core/datasets/tf/tf_crptax.py`, `sspi_flask_app/api/core/sspi/ms/tax/crptax.py`, `methodology/ms/tax/crptax/methodology.md`, `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/crptax.py`, `src/sspi/ingestion/taxfoundation.py`, `src/sspi/metadata/data/datasets/TF_CRPTAX.yaml`, `tests/golden/test_golden_crptax.py`

---

## TAXREV-1 — TAXREV gives Vietnam, Nigeria, Venezuela and Algeria the mean of every country's every year

Status: unresolved

Summary for the methodology team:
- Problem: `impute_taxrev` adds `impute_reference_class_average(<country>, 2000, 2023, "Dataset", "WB_TAXREV", clean_taxrev)` for Vietnam, Nigeria, Venezuela and Algeria, hard-coded. The "reference class" is every clean `WB_TAXREV` row: every economy the World Bank reports (not SSPI67), every year from 1972 on (not 2000–2023), unweighted, outliers included (Sudan 1998–1999 at 620–639 % of GDP, Timor-Leste 2010–2013 above 90 %). The four countries get that one value for every year 2000–2023, whether or not they have data. The code comment says "each is missing all observations".
- Potential direction A: preserve the hard-coded recipients and the all-rows mean.
- Potential direction B: restrict the reference class (for example to SSPI67, or to the target years), or derive the recipients from the data.

Current executable behavior:
- As above. None of the four has a `GC.TAX.TOTL.GD.ZS` value in the live World Bank source (last updated 2026-10-08, read 2026-10-09), so today there is no observed/imputed collision; the live mean is 17.094 % of GDP over 4,708 rows (score 0.342 for all four, every year). If any of them gains data, the legacy route would store both an observed score and imputed ones for the same years.
- With no `WB_TAXREV` row at all, the legacy impute route raised (`ValueError: Reference data cannot be empty.`).

Conflicting evidence:
- `sspi_flask_app/api/core/sspi/ms/tax/taxrev.py` against the SSPI67 reference classes other ported routes use, and against ENRSEC's identical construction (ENRSEC-1).

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(score_taxrev, (2000, 2023), listed_recipients=("VNM", "NGA", "VEN", "DZA"))` reproduces the route (exact parity). If a listed country has any observed row, the strategy raises `ImputationError` before anything is scored or written, and no precedence is chosen. With no rows at all it raises, as legacy did.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Every TAXREV score of the four countries; the mean moves with every source revision and every economy the World Bank adds.

Question for methodology review:
- What should the four countries' TAXREV values be when the source has none, and should the reference class be SSPI67 in the target years?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/tax/taxrev.py`, `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`)

Relevant new-backend files:
- `src/sspi/indicators/taxrev.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore`), `tests/golden/test_golden_taxrev.py`

---

## TAXREV-2 — Pakistan has no tax revenue data and is not on the hard-coded list, so it never gets a TAXREV score

Status: unresolved

Summary for the methodology team:
- Problem: five SSPI67 members have no `GC.TAX.TOTL.GD.ZS` value in any year: Algeria, Nigeria, Pakistan, Venezuela and Vietnam. The legacy impute route names four of them; Pakistan is not named, so it has no TAXREV score in any year, observed or imputed.
- Potential direction A: preserve the list (Pakistan stays unscored).
- Potential direction B: add Pakistan, or derive the recipients from the data (every SSPI67 member with no row).

Current executable behavior:
- `impute_taxrev` imputes only the four listed countries; series fill cannot reach a country with no observation.

Conflicting evidence:
- The live World Bank source (2026-10-08) against the comment in `impute_taxrev` ("Handle VNM, NGA, VEN, DZA : each is missing all observations"), which suggests the list was meant to cover every country with no data at the time.

Implementation decision in the new backend:
- Direction A: the list is reproduced exactly. Pakistan has no TAXREV score.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Pakistan's Tax category, and any aggregate that requires every indicator.

Question for methodology review:
- Should Pakistan be imputed, and how?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/tax/taxrev.py`

Relevant new-backend files:
- `src/sspi/indicators/taxrev.py`, `tests/golden/test_golden_taxrev.py`

---

## TAXREV-3 — TAXREV is central-government tax revenue, and the impute route carries a country's last value forward however old (Japan from 1993)

Status: unresolved

Summary for the methodology team:
- Problem: the description says "Tax revenue as percentage of GDP". The series is WDI `GC.TAX.TOTL.GD.ZS`: compulsory transfers to the *central* government, excluding most social security contributions. Federal countries and countries financed by social contributions score low: United States 10.6 % (2023), Germany around 11.5 % (2017, the 2018 static value), Japan 11.1 %, far below their general-government tax ratios including social contributions. Separately, the series fill carries each country's last value to 2023 with no age limit: on the live source, eleven countries are carried from before 2015, Japan for thirty years from 1993 (11.14 %), Benin from 1979, Niger from 1980, Kuwait from 1998, Indonesia from 2009.
- Potential direction A: keep the central-government series and the unbounded carry-forward.
- Potential direction B: use a general-government tax ratio (for example the OECD or IMF series, including social contributions), and/or bound forward extrapolation.

Current executable behavior:
- `collect_wb_taxrev` requests `GC.TAX.TOTL.GD.ZS`; `impute_taxrev` calls `extrapolate_forward(clean_taxrev, 2023, ...)` with no maximum distance. The 2018 static SSPI used the same World Bank series (`local/IndicatorDetailsStatic.csv`; its 49 raw values score exactly raw / 50).

Conflicting evidence:
- WDI metadata for `GC.TAX.TOTL.GD.ZS` ("Tax revenue refers to compulsory transfers to the central government for public purposes"), against the indicator description.
- Live source (2026-10-08): Japan's last value is 1993.

Implementation decision in the new backend:
- Direction A: the series and the series fill are reproduced exactly (exact parity; Japan's 1993 value carried to 2023 is in the committed fixture).

Reason:
- The executable code is the legacy methodology.

Potential impact:
- Every TAXREV score of countries where a large share of tax is collected below the central government or as social contributions; every forward-extrapolated score of the eleven countries above.

Question for methodology review:
- Is central-government tax revenue the intended measure? Should forward extrapolation have a maximum distance?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/wb/wb_taxrev.py`, `sspi_flask_app/api/core/sspi/ms/tax/taxrev.py`, `methodology/ms/tax/taxrev/methodology.md`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/taxrev.py`, `tests/golden/test_golden_taxrev.py`

---

## TXRDST-1 — The methodology's score function says goalposts −10 → −100; the executable reads −10 → 100

Status: unresolved

Summary for the methodology team:
- Problem: `methodology/ms/tax/txrdst/methodology.md` gives `LowerGoalpost: -10`, `UpperGoalpost: 100`, and a `ScoreFunction` ending `* 100, -10, -100)`. `compute_txrdst` reads the goalposts from metadata (`-10`, `100`), so the executable scores a 10 % fall of the bottom-50/top-10 ratio as 0 and a doubling as 1. With −10 → −100 the direction would be reversed and almost every country would score 0.
- Potential direction A: −10 → 100, as executed (the `ScoreFunction` text is a typo).
- Potential direction B: another range; the text should then be the definition.

Current executable behavior:
- `goalpost((posttax_ratio - pretax_ratio) / pretax_ratio * 100, -10, 100)`. On the live WID archive (2026-09-09), 120 of 1,650 scores are 1.0 and one is 0 (Mexico).

Conflicting evidence:
- The `ScoreFunction` line against `LowerGoalpost`/`UpperGoalpost` in the same file. `local/SSPIStaticData2018.csv` has no TXRDST column, so no raw/score pair can be checked.

Implementation decision in the new backend:
- Direction A: the executable goalposts, declared in `src/sspi/indicators/txrdst.py` and checked against the catalog. The catalog keeps the legacy `score_function` text verbatim.

Reason:
- The executable code is the legacy methodology.

Potential impact:
- Every TXRDST score, if the intended range differs.

Question for methodology review:
- Confirm −10 → 100, and correct the `ScoreFunction` text.

Relevant legacy files:
- `methodology/ms/tax/txrdst/methodology.md`, `sspi_flask_app/api/core/sspi/ms/tax/txrdst.py`

Relevant new-backend files:
- `src/sspi/indicators/txrdst.py`, `src/sspi/metadata/data/indicators/TXRDST.yaml`, `tests/golden/test_golden_txrdst.py`

---

## TXRDST-2 — "Induced by the tax code" is measured with post-tax national income, which includes transfers and public spending; the unit label is ISHRAT's

Status: unresolved

Summary for the methodology team:
- Problem: TXRDST is described as "the percentage change in the income share ratio … induced by the tax code". It compares WID pre-tax national income shares (`sptincj992`) with post-tax *national* income shares (`sdiincj992`), both for equal-split adults aged 20+. WID defines post-tax national income as post-tax disposable income plus public spending (`[Post-tax national income]=[Post-tax disposable income]+[Public spending]`): it counts cash transfers and in-kind public services as well as taxes. The indicator therefore measures redistribution by the whole tax-and-transfer-and-spending system, not by the tax code. The two inputs also come from different WID dataset families (`WID_NINCSH_PRETAX_*` without "EQUALSPLIT" in the name, `WID_NINCSH_POSTTAX_EQUALSPLIT_*`), although both are equal-split series. The score unit is "Ratio of Bottom 50% Income Share to to Top 10% Income Share", copied from ISHRAT; the scored quantity is a percentage change.
- Potential direction A: keep post-tax national income and describe the indicator as tax-and-transfer redistribution.
- Potential direction B: use post-tax disposable income (`cainc`), which excludes public spending, or another measure of tax progressivity.

Current executable behavior:
- `compute_txrdst` (formula in `src/sspi/indicators/txrdst.py`); no impute route, so a country-year missing any of the four shares is unscored. A zero pre-tax ratio scores `goalpost(0, -10, 100)` with a warning; a zero top-10 % share raises `ZeroDivisionError`. Neither occurs in the live archive.

Conflicting evidence:
- `datasets/wid/wid_nincsh_posttax_equalsplit_p0p50/documentation.md` (the WID technical description) against `methodology/ms/tax/txrdst/methodology.md`.
- `local/2025-06-25-indicator-status.json` lists a "Tax Progressivity" (TAXPRG) indicator where TXRDST now is.

Implementation decision in the new backend:
- Direction A: the series, formula and unit literal are reproduced exactly (exact parity).

Reason:
- The executable code is the legacy methodology.

Potential impact:
- Countries with large in-kind public services score as strongly redistributive whatever their tax progressivity.

Question for methodology review:
- Is TXRDST meant to measure tax progressivity or total fiscal redistribution? Which WID post-tax concept should it use?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/tax/txrdst.py`, `sspi_flask_app/api/core/datasets/wid/wid_nincsh_posttax_equalsplit_p0p50.py`, `datasets/wid/wid_nincsh_posttax_equalsplit_p0p50/documentation.md`, `methodology/ms/tax/txrdst/methodology.md`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/txrdst.py`, `src/sspi/ingestion/wid.py`, `tests/golden/test_golden_txrdst.py`

---

## UNEMPB-1 — Imputed UNEMPB scores carry the unit label "Tax Rate"

Status: unresolved

Summary for the methodology team:
- Problem: observed UNEMPB scores are labelled "Benefits Coverage (%)"; imputed ones are labelled "Tax Rate", a label copied from another indicator's impute route. The dataset is labelled "PERCENT".
- Potential direction A: keep the labels (current behaviour).
- Potential direction B: one label for every UNEMPB score. This changes no score.

Current executable behavior:
- `compute_unempb` passes `unit="Benefits Coverage (%)"`; `impute_unempb` passes `unit="Tax Rate"`. The new backend reproduces both.

Conflicting evidence:
- The source unit (`PERCENT`) and the goalposts (0, 100) agree with each other; "Tax Rate" describes neither. The same literal appears in the EMPLOY and COLBAR impute routes (EMPLOY-2, COLBAR-2).

Implementation decision in the new backend:
- Preserved exactly: `SeriesFillThenScore(..., unit="Tax Rate")`.

Reason:
- The labels are part of the legacy records and parity is exact. No score is affected.

Potential impact:
- No score changes. On the live source (2026-10-18) 3,919 of 4,996 UNEMPB scores are imputed and carry "Tax Rate".

Question for methodology review:
- Which label should UNEMPB scores carry?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/unempb.py`

Relevant new-backend files:
- `src/sspi/indicators/unempb.py`, `tests/golden/unempb_cases.json`, `tests/golden/test_golden_unempb.py`

---

## UNEMPB-2 — UNEMPB gives Iceland the mean of every country's every year

Status: unresolved

Summary for the methodology team:
- Problem: `impute_unempb` adds `impute_reference_class_average("ISL", 2000, 2023, "Dataset", "UNSDG_BENFTS_UNEMP", clean_unempb)`, hard-coded. Iceland gets, for every year 2000–2023, the flat mean of every clean row: every country the UN reports (not SSPI67), every year, unweighted, the many reported zeros included. On the live source (2026-10-18) that is 26.20 % over 1,077 values (score 0.262) for every year; on the committed fixture, 35.53 % over 106. The 2018 static SSPI gave Iceland 100 % (score 1.0, as for Belgium, Finland, France, Germany and Ireland); the UN series no longer includes Iceland at all.
- Potential direction A: keep the hard-coded recipient and the all-rows mean.
- Potential direction B: restrict the reference class (for example to SSPI67 or to comparable countries), use another source for Iceland, or derive the recipients from the data.

Current executable behavior:
- As above. Iceland has no `SI_COV_UEMP` row on the live source (2026-10-18), so there is no observed/imputed collision. If Iceland gains data, the legacy route would store both an observed and an imputed score for the same years. With no row at all, the legacy impute route raised (`ValueError: Reference data cannot be empty.`).

Conflicting evidence:
- `local/SSPIStaticData2018.csv`: `UNEMPL_RAW` 100 for Iceland (2018).
- The same construction in TAXREV and ENRSEC (TAXREV-1, ENRSEC-1).

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(score_unempb, (2000, 2023), unit="Tax Rate", listed_recipients=("ISL",))` reproduces the route (exact parity). If Iceland has any observed row, the strategy raises `ImputationError` before anything is scored or written, and no precedence is chosen. With no rows at all it raises, as legacy did.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Every UNEMPB score of Iceland (0.262 on the live source, against 1.0 in 2018); the mean moves with every source revision and every country the UN adds.

Question for methodology review:
- What should Iceland's UNEMPB value be while the source has none, and should the reference class be SSPI67?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/unempb.py`, `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`), `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/unempb.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore`), `tests/golden/test_golden_unempb.py`

---

## UNEMPB-3 — Most UNEMPB scores are filled from a few reported years; one value can stand for twenty-four years

Status: unresolved

Summary for the methodology team:
- Problem: the UN series is reported in a few scattered years per country (the 2025 legacy status note calls it "a biannual dataset for many countries"). The impute route carries each country's first value back to 2000 and its last value forward to 2023, with no limit on distance, and interpolates between. On the live source (2026-10-18), of the 1,584 SSPI67 country-years 2000–2023 only 534 are observed; 490 are interpolated, 441 carried back, 95 carried forward and 24 are Iceland's mean. Twenty SSPI67 countries' 2000 scores come from a value of 2015 or later, twelve of them from 2019. Malaysia and Venezuela report a single year: Malaysia's 2019 value (10.4 %) is its score for every year 2000–2023. Only four SSPI67 countries have an observed 2023 value. Every value is itself an ILO estimate (`Nature` `E`).
- Potential direction A: keep the unbounded series fill.
- Potential direction B: bound extrapolation (a maximum distance), or leave years far from any observation unscored.

Current executable behavior:
- `extrapolate_backward(clean_unempb, 2000, ...)`, `extrapolate_forward(clean_unempb, 2023, ...)` and `interpolate_linear(...)`, all with `impute_only=True`; no distance limit. The input provenance of every filled score names its anchor year and distance.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json` (UNEMPL: "linear interpolation will be done to bridge between missing years"), which describes interpolation, not twenty-year extrapolation.

Implementation decision in the new backend:
- Direction A: reproduced exactly (exact parity; Malaysia's single 2019 value carried to 2000–2023 is in the committed fixture).

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Most UNEMPB scores; trends over 2000–2023 are mostly artefacts of the fill for countries that report once or twice.

Question for methodology review:
- Should extrapolation have a maximum distance for UNEMPB, and should a single observation stand for a whole series?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/unempb.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/unempb.py`, `tests/golden/test_golden_unempb.py`, `docs/indicator-migration.md`

---

## FATINJ-1 — FATINJ has no imputation; most countries report one year, and thirteen SSPI67 countries none

Status: unresolved

Summary for the methodology team:
- Problem: legacy FATINJ has a compute route only. A country is scored only in the years the ILO's SDG 8.8.1 series reports, and that series is thin: on the live source (2026-10-18) 61 of 103 areas report a single year, and 277 of the 1,584 SSPI67 country-years 2000–2023 have a score. Austria reports 2024 only, so it has no FATINJ score in 2000–2023; Malaysia reports 2022 only, the United States 2023 only. Thirteen SSPI67 countries have no FATINJ score at all: ARE, BGD, CHN, ETH, IDN, IRN, IRQ, KEN, KWT, NGA, PER, VEN, VNM. The 2025 legacy status note says "stock imputations" were still to be run ("linear interpolation will be done to bridge between missing years"); no impute route was ever written.
- Potential direction A: keep FATINJ unimputed.
- Potential direction B: add the series fill other indicators use (interpolation, and possibly bounded extrapolation), and decide what countries with no data receive.

Current executable behavior:
- `compute_fatinj` scores every clean row; there is no `impute_fatinj`. An aggregate requiring every indicator would be incomplete for most countries in most years.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json` (FATINJ: "Finalization in Progress ... Just need to run stock imputations").
- The 2018 static SSPI has a FATINJ value for all 49 countries, each from its latest available year (2001–2018).

Implementation decision in the new backend:
- Direction A: `imputation=None`, as for every legacy indicator with no impute route (exact parity).

Reason:
- No imputation methodology exists in the legacy code.

Potential impact:
- Coverage of every FATINJ-based aggregate.

Question for methodology review:
- Should FATINJ be imputed, and how? Is the SDG 8.8.1 dataflow the right series, given its coverage?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/fatinj.py`, `local/2025-06-25-indicator-status.json`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/fatinj.py`, `tests/golden/test_golden_fatinj.py`

---

## FATINJ-2 — National fatal injury rates count different things and are compared without adjustment

Status: unresolved

Summary for the methodology team:
- Problem: the ILO compiles SDG 8.8.1 from each country's own records, and the observation notes say what was counted: reported or compensated injuries; with or without commuting accidents and occupational disease; per 100,000 workers employed, employees or insured persons. On the live source (2026-10-18) the notes mix all of these. The legacy cleaner ignores the notes and scores every value on the same 25 → 0 scale. Some values are far outside the range the goalposts assume: South Africa 2024 556.99, India 2000–2007 51 to 133 per 100,000; they score 0.
- Potential direction A: keep every value as published.
- Potential direction B: restrict to one case definition, or flag non-comparable values.

Current executable behavior:
- `clean_ilo_fatinj` keeps `SEX_T` and `MIG_STATUS_TOTAL` and nothing else; notes are not read. The new backend keeps the notes in each observation's provenance (`NOTE_INDICATOR`, `NOTE_SOURCE`, `SOURCE`) and never filters on them.

Conflicting evidence:
- The ILO response's `NOTE_INDICATOR` and `NOTE_SOURCE` attributes against the indicator description ("Number of fatal injuries per 100,000 workers").

Implementation decision in the new backend:
- Direction A: reproduced exactly (exact parity).

Reason:
- The executable code is the legacy methodology.

Potential impact:
- Cross-country comparisons of FATINJ; countries with insurance-based records score better or worse for reasons of coverage, not safety.

Question for methodology review:
- Should FATINJ compare only like-for-like national figures?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/ilo/ilo_fatinj.py`, `sspi_flask_app/api/datasource/ilo.py`

Relevant new-backend files:
- `src/sspi/indicators/fatinj.py`, `src/sspi/ingestion/ilo.py`, `tests/golden/test_golden_fatinj.py`

---

## MATERN-1 — MATERN has no executable implementation and no identified source

Status: unresolved

Summary for the methodology team:
- Problem: at the pinned commit MATERN has a methodology file (`goalpost(OECD_MATERN, 0, 52)`, "paid parental leave available to mothers (full-rate equivalent) in weeks during the first year") but no route, and `OECD_MATERN` has no collector, no cleaner and no series code. The legacy backend never produced a MATERN score. The definition matches the OECD Family Database indicator PF2.1, but nothing records which table, edition or column was meant. OECD.Stat, the `base_url` in the metadata, is retired, and the OECD SDMX API has no parental-leave dataflow. The 2018 static values (49 countries, 0–52 weeks) are consistent with the definition.
- Potential direction A: leave MATERN unported until a source is chosen.
- Potential direction B: adopt the OECD Family Database PF2.1 (full-rate-equivalent weeks of paid leave available to mothers), with a named edition, and decide how countries outside the OECD and countries with no paid leave are recorded.

Current executable behavior:
- None: `sspi_flask_app/api/core/sspi/ms/wwb/matern.py` contains one import.

Conflicting evidence:
- `methodology/ms/wwb/matern/methodology.md` and `local/IndicatorDetailsStatic.csv` against the absence of any executable path; `local/2025-06-25-indicator-status.json` ("Data Collection Problems").

Implementation decision in the new backend:
- Not ported. MATERN is not in the indicator registry and `OECD_MATERN` is not ingestible; both raise a clear error.

Reason:
- There is no executable legacy methodology to preserve, and the source is a new organization (OECD) with no adapter.

Potential impact:
- No MATERN score; the Worker Wellbeing category is incomplete.

Question for methodology review:
- Which source, edition and measure should MATERN use, and which countries can it cover?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/matern.py`, `methodology/ms/wwb/matern/methodology.md`, `datasets/oecd/oecd_matern/documentation.md`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/MATERN.yaml`, `src/sspi/metadata/data/datasets/OECD_MATERN.yaml`, `docs/indicator-migration.md`

---

## SENIOR-1 — The legacy SENIOR route cannot run, and its inputs never share a year

Status: unresolved

Summary for the methodology team:
- Problem: `compute_senior` reads raw data with `sspi_raw_api_data.fetch_raw_data("SENIOR")`, which raises at the pinned commit (the method requires a source-info dictionary). Its collector is commented out and would have sent `"SENIOR"` as the query string; the three canonical datasets have no collector or cleaner; the route writes its scores to the clean-data collection rather than the indicator collection; `impute_senior` writes nothing. The legacy backend therefore produced no SENIOR score. Even with a working collector, the OECD Pensions at a Glance dataflow (`OECD.ELS.SPD,DSD_PAG@DF_PAG`, live 2026-10-18) publishes life expectancy and the normal retirement age for 2024 only, and old-age income poverty for 2014–2022 in even years, so no country-year has all five inputs and the route would score nothing.
- Potential direction A: leave SENIOR unported until its definition and data are settled.
- Potential direction B: redefine the inputs so they can be combined (for example, pair each poverty year with the latest retirement figures), with an OECD SDMX adapter.

Current executable behavior:
- `compute_senior` raises `InvalidQueryError` before scoring.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json` ("none of the different components have aligning time series (intersection is nearly empty)").

Implementation decision in the new backend:
- Not ported. SENIOR is not in the indicator registry and its three datasets are not ingestible; both raise a clear error.

Reason:
- There is no executable legacy behaviour to preserve, and the source is a new organization (OECD) with no adapter.

Potential impact:
- No SENIOR score; the Worker Wellbeing category is incomplete.

Question for methodology review:
- How should the retirement and poverty measures be combined across years?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/senior.py`, `sspi_flask_app/api/datasource/oecdstat.py`, `sspi_flask_app/models/database/sspi_raw_api_data.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/SENIOR.yaml`, `docs/indicator-migration.md`

---

## SENIOR-2 — "Years in retirement" is computed as life expectancy at birth minus the retirement age

Status: unresolved

Summary for the methodology team:
- Problem: the canonical datasets are the OECD's "expected years in retirement" for men and women (`PAG_PEN20A`, `PAG_PEN20B`): how long a person who reaches the normal pension age can expect to live after it. The legacy route instead subtracts the current normal retirement age (`CRPLF22`) from life expectancy *at birth* (`LE`, `AGE=BIRTH`), which counts deaths before retirement against the retiree. On the live OECD data (2026-10-18, men, 2024): Austria 79.8 − 65 = 14.8 years by the route, against about 18.7 from life expectancy at 65 (83.7) minus 65; the United States 10.3 against about 17.0; Mexico 7.4 against about 17.1. Countries with high mortality before 65 are penalized twice.
- Potential direction A: follow the route (life expectancy at birth).
- Potential direction B: follow the canonical datasets (remaining life expectancy at the pension age).

Current executable behavior:
- `score_senior(SENLEF, SENLEM, SENCRF, SENCRM, SENPVT)` with `YRSRTF = SENLEF - SENCRF`, `YRSRTM = SENLEM - SENCRM`, goalposts 0–20 (women) and 0–15 (men); the route keeps `LE` only where `AGE == "BIRTH"`. It never ran (SENIOR-1).

Conflicting evidence:
- `datasets/oecd/oecd_yrsrtm/documentation.md` and `datasets/oecd/oecd_yrsrtw/documentation.md` ("Expected years in retirement") and `local/IntermediateDetailsStatic.csv` against `sspi_flask_app/api/core/sspi/ms/wwb/senior.py`.

Implementation decision in the new backend:
- Not ported (SENIOR-1); recorded so the definition is settled before it is.

Reason:
- The route and the dataset definitions describe different quantities.

Potential impact:
- Every SENIOR score once ported.

Question for methodology review:
- Which definition of years in retirement should SENIOR use?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/senior.py`, `methodology/ms/wwb/senior/methodology.md`, `datasets/oecd/oecd_yrsrtm/documentation.md`, `local/IntermediateDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/datasets/OECD_YRSRTM.yaml`, `src/sspi/metadata/data/datasets/OECD_YRSRTW.yaml`

---

## SENIOR-3 — The poverty component rewards higher old-age poverty

Status: unresolved

Summary for the methodology team:
- Problem: the route and the methodology text score old-age income poverty with `goalpost(SENPVT, 0, 50)`: 0 % poverty scores 0 and 50 % scores 1, so more poverty is better. The static intermediate table marks the same measure inverted (goalposts 100 → 0). On the live OECD data, Korea's 39.7 % of people over 66 in relative poverty (2022) would score 0.79 on this component and Austria's 11.6 % would score 0.23.
- Potential direction A: keep 0 → 50 as written.
- Potential direction B: invert the component (for example 50 → 0 or 100 → 0), so less poverty scores higher.

Current executable behavior:
- `lg_SENPVT, ug_SENPVT = 0, 50` in `score_senior`, weight 0.50. It never ran (SENIOR-1).

Conflicting evidence:
- `local/IntermediateDetailsStatic.csv` (POVNRT: weight 0.50, inverted, goalposts 100 and 0) against `methodology/ms/wwb/senior/methodology.md` and `senior.py` (0, 50).

Implementation decision in the new backend:
- Not ported (SENIOR-1); recorded so the direction is settled before it is.

Reason:
- The executable code and the static metadata disagree on direction.

Potential impact:
- Half of every SENIOR score once ported.

Question for methodology review:
- Confirm that less old-age poverty should score higher, and the goalposts.

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/wwb/senior.py`, `methodology/ms/wwb/senior/methodology.md`, `local/IntermediateDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/SENIOR.yaml`

---

## CSTUNT-1 — Series-filled CSTUNT scores carry the unit label "Coefficient"

Status: unresolved

Summary for the methodology team:
- Problem: CSTUNT scores have three unit labels depending on how they were made. Observed scores say `%` (compute route), scores filled from a country's own series say `Coefficient` (the `unit` argument of the impute route's `score_indicator` call, a literal shared with GINIPT), and regression-predicted scores say `%` again (the unit of the first observed score). The score is the same 0–1 goalposted number in all three cases, so the labels say nothing about the value; `Coefficient` is not a description of a stunting share.
- Potential direction A: keep the three labels as the legacy routes wrote them.
- Potential direction B: give every CSTUNT score one label (for example `%`, or a label for goalposted scores).

Current executable behavior:
- `compute_cstunt`: `unit="%"`; `impute_cstunt`: `score_indicator(forward + backward + interpolated, ..., unit="Coefficient")`, then `regression_imputation(..., unit=clean_cstunt[0]["Unit"])`.

Conflicting evidence:
- The same compute-route formula is used for all three; the labels differ only by route.

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(..., unit="Coefficient")` for the series fill and the first observed score's unit for the predictions (exact parity on the committed fixtures).

Reason:
- The labels are part of the executable output.

Potential impact:
- None on any score. On the live source (2026-10-18) no CSTUNT score is series-filled (every country the UN covers has every year 2000–2024), so `Coefficient` appears only if the source develops gaps; the synthetic fixture exercises it.

Question for methodology review:
- Should every CSTUNT score carry the same unit label?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/hlc/cstunt.py`

Relevant new-backend files:
- `src/sspi/indicators/cstunt.py`, `tests/golden/test_golden_cstunt.py`

---

## CSTUNT-2 — CSTUNT predicts stunting from nominal GDP per capita for every country without data, for every year since 1960, and gives eleven SSPI67 countries a perfect score

Status: unresolved

Summary for the methodology team:
- Problem: a country with no stunting estimate at all gets a CSTUNT score predicted from World Bank GDP per capita in current US dollars. The GDP value is goalposted 0 → 100,000 dollars, one straight line is fitted over every country-year that has both a GDP score and an observed CSTUNT score, and the prediction is clipped to [0, 1]. On the live sources (2026-10-18; *live, illustrative*) this applies to 51 economies, 18 of them SSPI67 members (Austria, Canada, Denmark, France, Hungary, Iceland, Israel, Italy, Luxembourg, New Zealand, Norway, Russia, Slovakia, Slovenia, Spain, Sweden, Switzerland, the United Arab Emirates), plus 33 territories and small states outside SSPI67 (Bermuda, Hong Kong, Monaco, Puerto Rico and others). Four consequences:
  - Every year with a GDP value is predicted, 1960–2025: 2,586 predicted scores, 1,334 of them before 2000 and 75 after 2023. Observed scores run 2000–2024.
  - Eleven SSPI67 members get 1.0 in 2023 (implied stunting 0 %): Austria, Canada, Denmark, Iceland, Israel, Luxembourg, New Zealand, Norway, Sweden, Switzerland and the UAE. No observed country scores above 0.978 (Poland, 1.1 %), so a predicted country outranks every measured one.
  - The predictor is nominal: as prices rise, the predicted prevalence falls. Austria's implied stunting is 24.2 % in 1960, 11.4 % in 2000 and 0 % in 2023. Russia is predicted at 17.1 % in 2023 and Hungary at 12.6 %, against 9.9 % and 3.2 % in the 2018 static data.
  - The fit is pooled over countries and years with no other variable, so it describes the cross-country relation between GDP and stunting, not any one country's.
- Potential direction A: keep the regression fallback as executed.
- Potential direction B: use a measured or modelled stunting source for high-income countries (the 2018 static SSPI used IHME estimates), restrict predictions to 2000–2023 and to SSPI67, use real or PPP GDP, or leave a country without data unscored.

Current executable behavior:
- `impute_cstunt`: recipients are the countries in `WB_GDP_PERCAP_CURPRICE_USD` with neither an observed nor a series-filled CSTUNT score, derived from the data. `regression_imputation(gdp_data, clean_cstunt, prediction_input, "CSTUNT", unit, "CSTUNT ~ WB_GDP_PERCAP_CURPRICE_USD + y_0 + e", ...)` with `Score = goalpost(GDP, 0, 100000)` for the feature, sklearn `LinearRegression`, clip to [0, 1].
- Live fit (2026-10-18): coefficient 1.0892, intercept 0.5054 over 3,982 country-years. A country with a GDP of zero would be predicted at 0.505; a GDP score of 0.454 or more (45,400 dollars) gives 1.0.

Conflicting evidence:
- `local/SSPIStaticData2018.csv` and `local/IndicatorDetailsStatic.csv`: the 2018 values came from IHME and include all 18 predicted SSPI67 members (Austria 1.17 %, score 0.977; Russia 9.93 %, 0.801; UAE 10.56 %, 0.789); today's predictions give 1.0, 0.628 and 1.0 for 2018.
- The docstring of `compute_cstunt` describes WHO survey and modelled series (`NUTRITION_ANT_HAZ_NE2`, `NUTSTUNTINGPREV`) that the route does not read; the legacy `WHO_CSTUNT` dataset (GHO `NUTSTUNTINGPREV`) has a cleaner but no indicator uses it.

Implementation decision in the new backend:
- Direction A: `CstuntImputation` reproduces the route; the fit reuses `fit_centered_least_squares` (the GINIPT fit). Exact parity on the committed fixtures, the coefficient and intercept bit for bit; on the full live responses the legacy route and the new backend produce the same 6,636 scores (same digest). Each predicted score records the feature score, the GDP transform, the coefficient, intercept and training size in its provenance.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- The CSTUNT score of 18 SSPI67 members in every year, and the ranking of every high-income country against the measured ones.

Question for methodology review:
- Should countries without a stunting estimate be predicted from GDP at all, and if so with which GDP measure, over which years and for which countries?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/hlc/cstunt.py`, `sspi_flask_app/api/resources/utilities.py` (`regression_imputation`), `sspi_flask_app/api/core/datasets/wb/wb_gdp_curprice_usd.py`, `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/cstunt.py`, `src/sspi/indicators/strategy.py` (`regression_impute_scores`, `fit_centered_least_squares`), `tests/golden/test_golden_cstunt.py`

---

## CSTUNT-3 — The 2018 static CSTUNT values come from IHME, not the UN series the code reads

Status: unresolved

Summary for the methodology team:
- Problem: the executable source is the UN SDG series `SH_STA_STNT` (UNICEF/WHO/World Bank Joint Malnutrition Estimates, modelled, both sexes, under 5). The 2018 static SSPI took its values from IHME's child growth failure estimates. All 49 static scores agree with the executable goalposts (50 → 0), so the formula is unchanged, but the values differ: for the 31 static countries the UN covers, the 2018 static value and the current UN value for 2018 differ by 2.2 percentage points on average, at most 5.8 (Poland), leaving out Colombia. Colombia's static value is 66.9 % (score 0), against 11.6 % in the UN series; that static value looks like a data-entry error. The other 18 static countries have no UN value (CSTUNT-2).
- Potential direction A: keep the UN series.
- Potential direction B: use the IHME estimates, or record which source the methodology intends.

Current executable behavior:
- `collect_unsdg_cstunt` requests SDG indicator 2.2.1; the cleaner keeps `SH_STA_STNT`, `sex=BOTHSEX`, `age=<5Y`.

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv`: CSTUNT source organization IHME, `https://ghdx.healthdata.org/record/ihme-data/child-growth-failure-visualization-input-data`.

Implementation decision in the new backend:
- Direction A (exact parity).

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Comparisons with the 2018 SSPI.

Question for methodology review:
- Which stunting source does the methodology intend, and should Colombia's 2018 value be corrected?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unsdg/unsdg_cstunt.py`, `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/datasets/UNSDG_CSTUNT.yaml`, `tests/golden/test_golden_cstunt.py`

---

## ATBRTH-1 — ATBRTH gives five hard-coded countries the mean of every country's every year

Status: unresolved

Summary for the methodology team:
- Problem: `impute_atbrth` gives Switzerland, the United Kingdom, the Netherlands, Belgium and Sweden, hard-coded, the flat mean of every clean `WHO_ATBRTH` row (every country, every year, unweighted) for every year 2000–2023. On the live WHO data (2026-10-18; *live, illustrative*) that mean is 91.5 % over 2,567 values, a score of 0.575 on the 80 → 100 goalposts. None of the five has a WHO value today, so all five would score 0.575. The 2018 static SSPI gave four of them 98.91 % (score 0.946) and the Netherlands 100 %.
- Potential direction A: keep the hard-coded recipients and the all-rows mean.
- Potential direction B: use national statistics or another source for these countries, restrict the reference class (for example to comparable high-income countries), or derive the recipients from the data.

Current executable behavior:
- `impute_reference_class_average(<country>, 2000, 2023, "Dataset", "WHO_ATBRTH", atbrth_clean)` for each of `CHE`, `GBR`, `NLD`, `BEL`, `SWE`, after forward and backward extrapolation and interpolation of every country's series. If one of the five gains WHO data, the route would store an observed and an imputed value for the same years.

Conflicting evidence:
- `local/SSPIStaticData2018.csv`: `ATBRTH_RAW` 98.91 for Belgium, Sweden, Switzerland and the United Kingdom, 100 for the Netherlands.

Implementation decision in the new backend:
- Direction A: `SeriesFillThenScore(score_atbrth, (2000, 2023), listed_recipients=("CHE", "GBR", "NLD", "BEL", "SWE"))` reproduces the route (exact parity on the committed GHO fixture, whose reference mean is 89.94 % over 148 rows). If one of the five has any observed row, the strategy raises `ImputationError` before anything is scored or written, and no precedence is chosen. With no rows at all it raises, as legacy did (`ValueError: Reference data cannot be empty.`).

Reason:
- The executable route is the legacy methodology. The WHO source was approved on 2026-10-19 and ATBRTH is ported.

Potential impact:
- Every ATBRTH score of five SSPI67 countries (0.575 on the live data of 2026-10-19, instead of about 0.95), for all 24 years.

Question for methodology review:
- What value should these five countries get, and should the reference class be SSPI67 or comparable countries?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/hlc/atbrth.py`, `sspi_flask_app/api/resources/utilities.py` (`impute_reference_class_average`), `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/atbrth.py`, `src/sspi/indicators/strategy.py` (`SeriesFillThenScore`), `tests/golden/test_golden_who.py`

---

## DPTCOV-1 — DPTCOV is described as survey coverage of children aged 12–23 months; the series is the WHO/UNICEF estimate for one-year-olds

Status: unresolved

Summary for the methodology team:
- Problem: the description says "the estimated percentage of children aged 12–23 months who received three doses of the combined diphtheria, tetanus toxoid and pertussis vaccine time before the survey", a household-survey definition. The series requested, GHO `WHS4_100`, is "DTP3 immunization coverage among 1-year-olds (%) (WUENIC)": the WHO/UNICEF estimate, built from administrative reports and surveys and revised every year back through the whole series. The cleaner's own description says "DTP3 immunization coverage among one-year-olds (%)". The 2018 static metadata names another GHO view (`UHCIMMUNIZATION` or `vdvp`). The scores agree with the executable goalposts (75 → 100) for all 49 static countries.
- Potential direction A: keep `WHS4_100` and correct the description.
- Potential direction B: use survey-based coverage of children aged 12–23 months.

Current executable behavior:
- `collect_who_dptcov`: `https://ghoapi.azureedge.net/api/WHS4_100`; `compute_dptcov`: `goalpost(WHO_DPTCOV, 75, 100)`, unit `%`; no impute route, so a year without an estimate has no score.

Conflicting evidence:
- `methodology/pg/hlc/dptcov/methodology.md` (description) against `who_dptcov.py` and the GHO indicator name; `local/IndicatorDetailsStatic.csv` (source code `UHCIMMUNIZATION` or `vdvp`).

Implementation decision in the new backend:
- Direction A for the measure: `WHO_DPTCOV` is ingested from `WHS4_100` exactly as the legacy collector requested it and scored with `goalpost(WHO_DPTCOV, 75, 100)`, nothing imputed (exact parity on the committed GHO fixture; identical scores on the full live response). The description in the canonical metadata is left as imported; correcting it is part of this decision.

Reason:
- The executable route is the legacy methodology. The WHO source was approved on 2026-10-19 and DPTCOV is ported.

Potential impact:
- The description researchers read. WUENIC is revised every year back through the series: for 12 of the 49 static countries the current 2017 value differs from the 2018 static value (by up to 6 points: Indonesia 79 → 85, Brazil 89 → 83), so recomputed historical scores change with each round. WUENIC caps coverage at 99 %, so no DPTCOV score reaches 1.

Question for methodology review:
- Confirm WUENIC DTP3 coverage of one-year-olds as the measure, and the description.

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/who/who_dptcov.py`, `sspi_flask_app/api/core/sspi/pg/hlc/dptcov.py`, `methodology/pg/hlc/dptcov/methodology.md`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/indicators/dptcov.py`, `src/sspi/metadata/data/indicators/DPTCOV.yaml`, `src/sspi/metadata/data/datasets/WHO_DPTCOV.yaml`, `tests/golden/test_golden_who.py`

---

## FAMPLN-1 — FAMPLN produces no score, and its description, data and goalposts describe three different measures

Status: unresolved

Decision needed, in one table (no option is adopted):

| Source of the definition | Measure | Women counted | Direction and goalposts | What it gives today |
|---|---|---|---|---|
| Legacy collector (`who_fampln.py`) | GHO `SDGFPALL`: need for family planning satisfied with modern methods (modern-method users ÷ total demand), %, survey-based | 15–49; WHO's registry text says married or in-union, the rows say only female 15–49 | higher is better; executable goalposts 20 → 100 | 480 country rows (142 countries, 2000–2023; 34 SSPI67 members, none for Austria) |
| Canonical methodology description (`fampln/methodology.md`) | modelled unmet need for family planning, any modern method, % | married or in a union, reproductive age | lower is better (not stated in the score function) | no dataset or code names this measure |
| 2018 static SSPI (`IndicatorDetailsStatic.csv`, `SSPIStaticData2018.csv`) | GHO `MDG_0000000006_AGE1519`: unmet need among girls aged 15–19, % | 15–19 | lower is better; all 49 scores equal 1 − value / 100 (neither 20 → 0 nor 20 → 100) | the GHO code returns no rows today, so the 2018 values cannot be traced |
| Scoring route (`fampln.py`) | `lambda UNSDG_FAMPLN: goalpost(UNSDG_FAMPLN, 20, 100)` on `WHO_FAMPLN` rows | — | — | the argument names a dataset the route never reads: 0 scores stored |

Summary for the methodology team:
- Problem: three family-planning measures are mixed up, and the code scores none of them.
  - The executable route reads `WHO_FAMPLN` (GHO `SDGFPALL`, "Women of reproductive age (aged 15-49 years) who have their need for family planning satisfied with modern methods (%)": women using a modern method as a percentage of total demand, that is users of any method plus women with an unmet need; survey-based country values; higher is better) but its score function is `lambda UNSDG_FAMPLN: goalpost(UNSDG_FAMPLN, 20, 100)`. The legacy scorer binds arguments by dataset code, finds no `UNSDG_FAMPLN` value and skips every row: the compute route stores no score. Run on the live WHO data (2026-10-18), it cleaned 480 rows and stored 0 scores.
  - The description is "modeled unmet need for family planning, women married or in a union, any modern method", a measure where lower is better. The 2018 static SSPI scored unmet need (GHO `MDG_0000000006_AGE1519`, among girls aged 15–19) with `goalpost(x, 100, 0)`: all 49 static scores equal 1 − unmet need / 100. Neither the executable goalposts (20 → 100) nor the static metadata's (20 → 0) reproduce them.
  - A third dataset, `UNSDG_FAMPLN` (SDG 3.7.1, `SH_FPL_MTMM`, demand satisfied by modern methods, the UN modelled series), has a cleaner but is not in any indicator's datasets.
  - Which women `SDGFPALL` counts is itself unclear. WHO's metadata registry entry for the measure (IMR 4668) is titled "Married or in-union women of reproductive age who have their need for family planning satisfied with modern methods" and says "estimates are with respect to women who are married or in a union", with country values "extracted by WHO from World Contraceptive Use 2018"; the GHO rows of `SDGFPALL` carry only `SEX_FMLE` and `AGEGROUP_YEARS15-49`, no marital-status dimension, and the code's suffix suggests all women. Nothing in the API resolves it.
  - The GHO publishes several neighbouring measures that are not interchangeable with it: `fpsmo` (demand satisfied, modern methods), `fps` (demand satisfied, modern and traditional methods), `FAMILYPLANNINGUNPDUHC` (demand satisfied with modern methods, UN Population Division modelled estimates), `cpmo` and `cpmt` (contraceptive prevalence, modern; modern and traditional), `MDG_0000000005` (contraceptive prevalence) and `MDG_0000000006_AGE1519` (unmet need, girls 15–19). Contraceptive prevalence is users as a share of all (or married) women; demand satisfied divides the same users by demand only, so a country where few women want contraception can score high on one and low on the other.
- Potential direction A: score `WHO_FAMPLN` (demand satisfied with modern methods) as the dataset list says, with goalposts 20 → 100; that requires fixing the argument name, which changes legacy output (it produced nothing).
- Potential direction B: score unmet need (lower is better) as the description and the 2018 SSPI did, from a named source and age group.

Current executable behavior:
- `compute_fampln` stores nothing; there is no impute route. On the live WHO data, `SDGFPALL` covers 34 of the 66 SSPI67 members (none of Austria and 31 others), mostly with a few survey years.

Conflicting evidence:
- `methodology/pg/hlc/fampln/methodology.md` (description, `goalpost(UNSDG_FAMPLN, 20, 100)`, datasets `WHO_FAMPLN`), `datasets/who/who_fampln/documentation.md`, `datasets/unsdg/unsdg_fampln/documentation.md`, `local/IndicatorDetailsStatic.csv` ("Unmet Need for Family Planning", `MDG_0000000006_AGE1519`, goalposts 20 → 0), `local/SSPIStaticData2018.csv`.

Implementation decision in the new backend:
- Not ported. The WHO source is approved and the generic GHO adapter can read `SDGFPALL` (480 country rows, 142 countries, 2000–2023 on 2026-10-19), but `WHO_FAMPLN` is not ingestible and FAMPLN is not registered: the legacy route produces no score, so there is no executable output to hold parity against, and choosing the measure, population, goalposts and direction is the decision this entry asks for. Its canonical dataset also has no unit (the legacy cleaner wrote `Percent`).

Reason:
- Porting the route as written would publish an indicator with no scores; making it score anything is a methodology decision.

Potential impact:
- No FAMPLN score; the Healthcare category is incomplete.

Question for methodology review:
- Which measure is FAMPLN (unmet need, contraceptive prevalence, or demand satisfied; modern methods only or any method), for which women (all women or married and in-union women; 15–49 or 15–19), from which GHO or UN code (survey or modelled), and with which goalposts and direction?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/hlc/fampln.py`, `sspi_flask_app/api/core/datasets/who/who_fampln.py`, `sspi_flask_app/api/core/datasets/unsdg/unsdg_fampln.py`, `sspi_flask_app/api/resources/utilities.py` (`score_indicator_documents`), `methodology/pg/hlc/fampln/methodology.md`, `local/IndicatorDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/FAMPLN.yaml`, `src/sspi/metadata/data/datasets/WHO_FAMPLN.yaml`, `docs/indicator-migration.md`

---

## PHYSPC-1 — PHYSPC scores WHO's workforce figures as published, including an implausible Austrian 2018 value, and the series has been revised since 2018

Status: unresolved

Summary for the methodology team:
- Problem: the route scores every value of GHO `HWF_0001` ("Medical doctors (per 10,000)", National Health Workforce Accounts as reported by member states) without any check. Three consequences on the current source (2026-10-19; *live, illustrative*):
  - Austria's series reads 51.56 (2017), 95.42 (2018), 52.91 (2019). The 2018 value is exactly Cuba's 2021 value and is almost certainly a reporting error; PHYSPC scores it 1.0 for that year, against 0.74 for the neighbouring years.
  - Canada's series starts in 2018, so the impute route carries the 2018 value back to 2000 (eighteen years); San Marino has nothing from 2015 to 2021 and Monaco nothing from 1993 to 2010, both linearly interpolated.
  - The 2018 static values match no current value for their stated year (2017) in any of the 46 countries both cover: the workforce series has been revised heavily (China 36.25 static against 20.03 now, Chile 10.33 against 24.30). The static scores agree with the executable goalposts (0 → 70), so the formula is unchanged; the data are not.
- Potential direction A: keep scoring the published series as it is (the executable behaviour).
- Potential direction B: screen the series before scoring (for example flag a value far from both neighbours for review, or replace it), and record which WHO update a score was computed from.

Current executable behavior:
- `compute_physpc`: `goalpost(WHO_PHYSPC, 0, 70)` on every clean row, 1990 onward, unit `Rate`; `impute_physpc`: forward to 2023, backward to 2000, interpolation of every interior gap, each country in the dataset.

Conflicting evidence:
- The GHO rows themselves (Austria 2017–2019; their `Comments` name the "NHWA data portal, December 2025 update"); `local/SSPIStaticData2018.csv` (`PHYSPC_RAW`, year 2017) against the current series.

Implementation decision in the new backend:
- Direction A (exact parity on the committed GHO fixture, which keeps Austria's 2018 value; identical scores on the full live response). Each observation records WHO's change date (`source_date`) and comment in its provenance.

Reason:
- The executable route is the legacy methodology; correcting source values is a methodology decision.

Potential impact:
- Austria's 2018 PHYSPC score (1.0 instead of about 0.74); any comparison with the 2018 SSPI; scores move whenever WHO republishes the workforce accounts, since the GHO API serves no editions.

Question for methodology review:
- Should implausible source values be screened, and should PHYSPC record or pin the WHO update it was computed from?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/hlc/physpc.py`, `sspi_flask_app/api/core/datasets/who/who_physpc.py`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/physpc.py`, `src/sspi/ingestion/who.py`, `tests/golden/test_golden_who.py`

---

## FSTABL-1 — FSTABL has no executable implementation: its IMF dataset was never defined, and a World Bank nonperforming-loans collector was added but never wired to a score

Status: unresolved

Summary for the methodology team:
- Problem: the canonical metadata and `methodology/ms/fin/fstabl/methodology.md` define FSTABL as `goalpost(IMF_FSTABL, 10, 0)`: "the percentage of loans that are nonperforming", 10 % or more scoring 0 and 0 % scoring 1. At the pinned commit nothing computes it. `fstabl.py` holds one import and a commented-out collector stub naming an IMF API package; there is no compute or impute route, so the legacy backend never produced an FSTABL score. `IMF_FSTABL` has no definition: commit `9064c4052` (2025-11-29) deleted its documentation (organization IMF, series and query code `null`, a data.imf.org link) and added in its place a `WB_FSTABL` collector and cleaner for World Bank `FB.AST.NPER.ZS`, "Bank nonperforming loans to total gross loans (%)" (WDI, sourced from the IMF Financial Soundness Indicators), and a generic IMF DataMapper client that nothing calls. No route or methodology file reads `WB_FSTABL`.
- Evidence on the intended measure: the 2018 static SSPI scored FSTABL from an IMF raw value with the same goalposts (`FSTABL_SCORE` = (10 − `FSTABL_RAW`) / 10; `local/IndicatorDetailsStatic.csv`: source IMF, data.imf.org). Today's World Bank series is close to those values for most countries but not equal to them (2018 values, live 2026-10-19, *illustrative*: Austria 1.6 static against 2.9 now, Greece 38.5 against 43.4, India 8.8 against 9.5), so either the series was revised or the static source was a different IMF table. Four SSPI67 members have no World Bank value at all (Egypt, Iran, New Zealand, Venezuela). `local/2025-06-25-indicator-status.json` says "Data is available but there's some kink to work out in sourcing it"; `local/indicator-problems.json` asks "What is the status of this indicator?".
- Potential direction A: leave FSTABL unported until the source is chosen.
- Potential direction B: adopt `WB_FSTABL` (`FB.AST.NPER.ZS`) as the FSTABL input with the methodology goalposts (10 → 0), through the existing World Bank adapter, and decide whether and how the four members without data are imputed.
- Potential direction C: adopt the IMF Financial Soundness Indicators directly (a new source organization and adapter), with a named dataset, indicator and edition.

Current executable behavior:
- None: no compute or impute route exists for FSTABL; `WB_FSTABL` can be collected and cleaned but is never scored.

Conflicting evidence:
- `methodology/ms/fin/fstabl/methodology.md` (`IMF_FSTABL`) against `sspi_flask_app/api/core/datasets/wb/wb_fstabl.py` (`FB.AST.NPER.ZS`) and the deleted `datasets/imf/imf_fstabl/documentation.md`; `local/SSPIStaticData2018.csv` and `local/IndicatorDetailsStatic.csv` (an IMF source).

Implementation decision in the new backend:
- Not ported. FSTABL is not in the indicator registry and `IMF_FSTABL` (an unresolved catalog entry) is not ingestible; both raise a clear error. No golden scores exist, because there was no legacy computation. The World Bank adapter can already read `FB.AST.NPER.ZS` if direction B is chosen.

Reason:
- There is no executable legacy methodology to preserve, and substituting the World Bank series for an IMF measure is a research decision, not a migration step.

Potential impact:
- No FSTABL score; the Financial Sector category is incomplete.

Question for methodology review:
- Which source, series and edition should FSTABL use: the World Bank `FB.AST.NPER.ZS`, an IMF Financial Soundness Indicators table, or something else; and how should countries without data be treated?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/fin/fstabl.py`, `sspi_flask_app/api/core/datasets/wb/wb_fstabl.py`, `sspi_flask_app/api/datasource/imf.py`, `methodology/ms/fin/fstabl/methodology.md`, `datasets/wb/wb_fstabl/documentation.md`, `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/FSTABL.yaml`, `src/sspi/metadata/data/datasets/IMF_FSTABL.yaml`, `docs/indicator-migration.md`

---

## FDEPTH-1 — The legacy FDEPTH impute route raises on every input, so no FDEPTH score was ever imputed, although the methodology describes imputation

Status: unresolved

Summary for the methodology team:
- Problem: the methodology prose says missing credit or deposit values are imputed per input (backward and forward extrapolation, linear interpolation) and that the United Kingdom, which has no deposit series, gets a reference-class value. The legacy impute route was written for the data layout used before July 2025 and was not updated when the datasets were renamed (commit `f902f5979`, "Fixed DatasetCode IndicatorCode Issue"). On every input it:
  1. deletes every stored FDEPTH imputation;
  2. reads clean data with `IndicatorCode == "FDEPTH"`, which no clean row carries (they carry `DatasetCode` `WB_CREDIT` / `WB_DPOSIT`), so it gets nothing;
  3. slices intermediates named `CREDIT` and `DPOSIT` out of a `Datasets` list; clean rows have no such list, and the incomplete groups it also reads name `WB_CREDIT` / `WB_DPOSIT`, so every slice is empty;
  4. calls `impute_reference_class_average("GBR", 2000, 2023, "Intermediate", "DPOSIT", [])`, which raises `ValueError: Reference data cannot be empty.` (with reference data it would raise anyway: `"Intermediate"` is not a valid item type).
  Had it gone on, its score function `(CREDIT + DPOSIT) / 2` averages the raw percentages without goalposts, and its filter reads an `Intermediates` key the scored documents do not have. The legacy backend therefore stored observed FDEPTH scores only, from the compute route. The golden file records the failure on the fixture, on an empty dataset and on a probe of 447 documents written in the old layout (the query then matches, the slices still find nothing).
- Coverage consequence (live 2026-10-19, *illustrative*): of the 1,584 SSPI67 country-years 2000–2023, 324 have no FDEPTH score: the United Kingdom in every year (no deposit series), every member in 2022–2023 (the deposit database ends in 2021), and gaps in single inputs.
- Potential direction A: keep what legacy stored, observed scores only (the current behaviour).
- Potential direction B: implement the imputation the prose describes, deciding (i) the series fill per input and its window (forward to 2023 from a database that ends in 2021), (ii) the United Kingdom's deposit reference class (which countries and years; raw percentages, as the route intended), (iii) whether imputed scores use the compute route's goalposted formula rather than the route's raw average, and (iv) precedence over observed scores.

Current executable behavior:
- `compute_fdepth`: `goalpost(WB_CREDIT, 0, 200) / 2 + goalpost(WB_DPOSIT, 0, 100) / 2` on every country-year with both inputs, no year filter, unit `Index`; the others go to the incomplete collection. `impute_fdepth`: raises as above after deleting stored FDEPTH imputations.

Conflicting evidence:
- `methodology/ms/fin/fdepth/methodology.md` ("Data Coverage and Imputations"), `local/2025-06-25-indicator-status.json` ("Just need to run stock imputations"), against the route.

Implementation decision in the new backend:
- Direction A, approved by the project owner on 2026-10-19 as the migration treatment (the methodology question stays open). FDEPTH has no imputation strategy, so `run("FDEPTH")` stores exactly the scores the legacy compute route stored and never an imputed one; incomplete country-years are reported as unscored. The route's failure itself is not reproduced as an error, because it would also discard the observed scores legacy kept (they were written by a separate route). Registered in `INOPERATIVE_IMPUTE_ROUTES` (`tests/golden/parity.py`); exact parity on the compute route's scores and incomplete identities.

Reason:
- Preserving executable behaviour: the impute route never produced output, and writing one now would choose among the open questions above.

Potential impact:
- No FDEPTH score for the United Kingdom, for 2022–2023, or for a country-year missing either input; FDEPTH never reaches full SSPI67 × 2000–2023 coverage.

Question for methodology review:
- Should FDEPTH be imputed and, if so, with which per-input rules, which United Kingdom reference class, and which score formula?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/fin/fdepth.py`, `sspi_flask_app/api/resources/utilities.py` (`slice_dataset`, `impute_reference_class_average`), `methodology/ms/fin/fdepth/methodology.md`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/fdepth.py`, `tests/golden/generate_financial_cases.py`, `tests/golden/test_golden_fdepth.py`, `tests/golden/parity.py`

---

## FDEPTH-2 — FDEPTH's executable goalposts are 0 → 200 (credit) and 0 → 100 (deposits); the 2018 static scores used 0 → 190 and 0 → 200

Status: unresolved

Summary for the methodology team:
- Problem: the compute route hard-codes `goalpost(WB_CREDIT, 0, 200)` and `goalpost(WB_DPOSIT, 0, 100)`, as the methodology's score function does. `local/IntermediateDetailsStatic.csv` gives the 2018 goalposts as 0 → 190 for credit and 0 → 200 for deposits, and the 2018 static FDEPTH scores follow those: recomputed from today's World Bank values for the static year, the static goalposts reproduce the 45 comparable scores with a mean absolute difference of 0.017, the executable ones with 0.144 (live 2026-10-19, *illustrative*; the series have been revised since). With the executable pair, deposits above 100 % of GDP (Malaysia, the United States in 2020, Luxembourg up to 462 %) all score 1. The indicator-level metadata goalposts (0, 200) describe only the credit input and are not read by the route.
- Potential direction A: keep the executable goalposts.
- Potential direction B: restore the 2018 goalposts (0 → 190, 0 → 200).

Current executable behavior:
- `goalpost(WB_CREDIT, 0, 200) / 2 + goalpost(WB_DPOSIT, 0, 100) / 2`.

Conflicting evidence:
- `local/IntermediateDetailsStatic.csv`, `local/IndicatorDetailsStatic.csv` (`(0, 190)`, `(0, 200)`), `local/SSPIStaticData2018.csv` (`FDEPTH_SCORE`).

Implementation decision in the new backend:
- The executable goalposts, exactly; no goalposts are declared on the definition, since the metadata pair is the credit input's only.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Every FDEPTH score; comparisons with the 2018 SSPI.

Question for methodology review:
- Which goalposts should each FDEPTH input use, and should the metadata record both pairs?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/fin/fdepth.py`, `methodology/ms/fin/fdepth/methodology.md`, `local/IntermediateDetailsStatic.csv`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/fdepth.py`, `src/sspi/metadata/data/indicators/FDEPTH.yaml`

---

## FDEPTH-3 — The "financial system deposits" input is the GFDD series of bank deposits only, from a database last updated in 2022

Status: unresolved

Summary for the methodology team:
- Problem: `WB_DPOSIT` is named "Financial System Deposits" and described as "deposited money in banks and other financial institutions as a percentage of GDP". The series the collector requests, `GFDD.OI.02`, is "Bank deposits to GDP (%)": demand, time and saving deposits in deposit money banks only (IMF International Financial Statistics). The Global Financial Development database also publishes `GFDD.DI.08`, "Financial system deposits to GDP (%)", which matches the name. The 2018 static metadata already paired the name with `GFDD.OI.02`. The database (World Bank source 32) was last updated on 2022-09-23 and ends in 2021, so no FDEPTH score can exist after 2021, while the credit series runs to 2025. It has no United Kingdom series. It also serves Serbia, DR Congo, Yemen, Timor-Leste, West Bank and Gaza and Taiwan with a two-letter id and no ISO3 code, which the legacy cleaner does not recognize (none of them is an SSPI67 member).
- Potential direction A: keep `GFDD.OI.02` and correct the name and description to bank deposits.
- Potential direction B: switch to `GFDD.DI.08` (financial-system deposits), with the same coverage limits.
- Potential direction C: choose a maintained source for deposits.

Current executable behavior:
- `collect_wb_data("GFDD.OI.02")`; values kept as published, unit `Percent`.

Conflicting evidence:
- `datasets/wb/wb_dposit/documentation.md` (name, description) against the World Bank API's indicator metadata for `GFDD.OI.02` and `GFDD.DI.08` (2026-10-19).

Implementation decision in the new backend:
- `GFDD.OI.02` exactly, through the existing World Bank adapter; the canonical name and description are left as imported.

Reason:
- The series is the executable source; renaming the dataset or changing the series is a methodology decision.

Potential impact:
- What FDEPTH measures; FDEPTH coverage after 2021 and for the United Kingdom.

Question for methodology review:
- Which deposit measure should FDEPTH use, and from which maintained source?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/wb/wb_dposit.py`, `datasets/wb/wb_dposit/documentation.md`, `local/IntermediateDetailsStatic.csv`

Relevant new-backend files:
- `src/sspi/metadata/data/datasets/WB_DPOSIT.yaml`, `src/sspi/ingestion/worldbank.py`, `tests/golden/test_golden_fdepth.py`

---

## PUBACC-1 — PUBACC has no imputation; scores exist only in Findex survey years

Status: unresolved

Summary for the methodology team:
- Problem: `FX.OWN.TOTL.ZS` comes from the Global Findex survey, published for 2011, 2014, 2017, 2021 and 2024 (and 2022 for countries surveyed late). PUBACC has no impute route, so a country is scored only in those years. Live 2026-10-19 (*illustrative*): 256 of the 1,584 SSPI67 country-years 2000–2023 have a score, every member in at least one wave, none before 2011. The legacy aggregation used only indicators with full SSPI67 × 2000–2023 coverage, so PUBACC could never have entered a category score as executed. `local/2025-06-25-indicator-status.json` notes "Coverage seems to start in 2011 and is only biannual. Will need to examine the documentation." The 2018 static values equal today's World Bank 2017 figures to the two decimals the static file keeps for 46 of 48 countries, with the same goalposts.
- Potential direction A: keep survey-year scores only (the executable behaviour).
- Potential direction B: fill between and around waves (for example carry the nearest wave, or interpolate between waves and extrapolate to 2000–2023), as other indicators do.

Current executable behavior:
- `compute_pubacc`: `goalpost(WB_PUBACC, 0, 100)` (goalposts read from metadata) on every clean row, unit `Percent`; no impute route.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json`; the coverage rule of the legacy aggregation.

Implementation decision in the new backend:
- Direction A: no imputation, exact parity with the compute route.

Reason:
- The executable route is the legacy methodology; filling survey gaps is a methodology decision.

Potential impact:
- PUBACC scores exist only in survey years; any aggregate that needs every year cannot use it as it stands.

Question for methodology review:
- Should PUBACC be filled between survey waves and, if so, how?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/ms/fin/pubacc.py`, `sspi_flask_app/api/core/datasets/wb/wb_pubacc.py`, `local/2025-06-25-indicator-status.json`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/pubacc.py`, `tests/golden/test_golden_pubacc.py`

---

## AQELEC-1 — AQELEC's quality input is a WEF survey series read from a spreadsheet no supported source covers, and it ends in 2017

Status: unresolved

Summary for the methodology team:
- Problem: AQELEC averages `goalpost(WB_AVELEC, 0, 100)` (World Bank `EG.ELC.ACCS.ZS`, access to electricity, % of population) and `goalpost(WEF_QUELEC, 1, 7)`. `WEF_QUELEC` is `WEF.GCIHH.EOSQ064`, "Quality of electricity supply, 1-7 (best)", an answer to the World Economic Forum's Executive Opinion Survey ("In your country, how would you assess the reliability of the electricity supply?"). The legacy collector downloads one Excel workbook, the "WEF Global Competitiveness Index - Historical Dataset", from `https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx`. The file is hosted by the World Bank but is WEF data, not a WDI series. Checked 2026-10-19 (*live, illustrative*): it is still served (HTTP 200, last modified 2024-02-16, 3,476,362 bytes, SHA-256 `a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451`; dataset "Last Updated" 2023-07-17). The series covers 2007–2017 only, for 152 economies (128 to 148 per year). The WEF replaced that index in 2018 with a new methodology and has published no comparable series since. The workbook's terms are a Creative Commons non-commercial, no-derivatives licence. So AQELEC can have an observed score only in 2007–2017 and only where both inputs exist; it has no impute route. `local/2025-06-25-indicator-status.json` says "Complete coverage from 2007 to 2017 but issues outside of that period. Investigate imputation strategies and alternate sources."
- Potential direction A: approve a source adapter for the pinned WEF workbook (historical only, 2007–2017; a checksum-pinned file, an Excel reader dependency, and a decision on redistributing extracts under its licence) and port AQELEC as executed.
- Potential direction B: choose a maintained electricity-reliability source; that is a methodology change.
- Potential direction C: leave AQELEC unported.

Current executable behavior:
- `compute_aqelec`: `0.5 * goalpost(WB_AVELEC, 0, 100) + 0.5 * goalpost(WEF_QUELEC, 1, 7)` on every country-year with both inputs, unit `Index`; others are incomplete. No impute route.

Conflicting evidence:
- `local/IndicatorDetailsStatic.csv` gives the quality goalposts as `(0, 7)`; the executable and the methodology use `(1, 7)`.

Implementation decision in the new backend:
- The project owner approved a WEF workbook adapter on 2026-10-19. That is a software decision; it settles none of the methodology questions here. AQELEC is ported exactly as executed:
  - formula `0.5 * goalpost(WB_AVELEC, 0, 100) + 0.5 * goalpost(WEF_QUELEC, 1, 7)` (the executable (1, 7), not the static (0, 7));
  - no imputation, so no score outside 2007–2017 or without both inputs.
- The workbook is pinned by SHA-256 (`src/sspi/ingestion/wef.py`). Parity is exact on an invented workbook in the WEF layout (`tests/golden/test_golden_wef.py`) and, opt-in, on the original (`tests/golden/test_golden_wef_real_data.py`).
- The licence questions are a separate data-governance item, GOV-2 (`docs/data-governance-review.md`).

Reason:
- Preserving executable behaviour with an approved source adapter. Extending the series past 2017, changing its goalposts or choosing another source is a methodology decision.

Potential impact:
- No AQELEC score before 2007 or after 2017 (live: 711 of the 726 SSPI67 member-years 2007–2017 are scored; Iraq never).

Question for methodology review:
- Should AQELEC use the historical WEF series, which stops in 2017, under its licence, or a different electricity-quality measure?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/aqelec.py`, `sspi_flask_app/api/datasource/wef.py`, `sspi_flask_app/api/core/datasets/wef/wef_quelec.py`, `sspi_flask_app/api/core/datasets/wb/wb_avelec.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/aqelec.py`, `src/sspi/ingestion/wef.py`, `src/sspi/metadata/data/datasets/WEF_QUELEC.yaml`, `tests/golden/test_golden_wef.py`, `docs/data-governance-review.md`

---

## SANSRV-1 — SANSRV's executable goalposts are 50 → 100; the 2018 static scores used 0 → 100

Status: unresolved

Summary for the methodology team:
- Problem: the compute and impute routes score `goalpost(WB_SANSRV, lg, ug)` with the metadata goalposts (50, 100): half the population or less scores 0. Every one of the 49 SANSRV scores in the 2018 static SSPI equals its raw value divided by 100, which is the (0, 100) goalpost; only 8 also satisfy (50, 100). The static raw values are the same series (median absolute difference 0.19 points from today's `SH.STA.BASS.ZS` for the stated year). For India (44 % in 2015) the static score was 0.44; the executable scores 0.
- Potential direction A: keep 50 → 100.
- Potential direction B: return to 0 → 100.

Current executable behavior:
- `goalpost(WB_SANSRV, 50, 100)`, read from metadata at runtime.

Conflicting evidence:
- `local/SSPIStaticData2018.csv` (`SANSRV_RAW`, `SANSRV_SCORE`); `local/IndicatorDetailsStatic.csv` and the methodology file both say (50, 100).

Implementation decision in the new backend:
- The executable goalposts (50, 100), declared on the definition and checked against metadata.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Every SANSRV score below 100 % coverage, and most of all countries under 50 %, which all score 0.

Question for methodology review:
- Which lower goalpost should SANSRV use?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/sansrv.py`, `methodology/pg/inf/sansrv/methodology.md`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/sansrv.py`, `tests/golden/test_golden_sansrv.py`

---

## SANSRV-2 — SANSRV's impute route only extrapolates: a country's last value is carried to 2023 however old, and interior gaps are never filled

Status: unresolved

Summary for the methodology team:
- Problem: `impute_sansrv` carries each country's series forward to 2023 and backward to 2000, every country in the dataset, and scores the filled values. It does not interpolate, so a gap inside a series would stay empty. Today (live 2026-10-19, *illustrative*) the JMP series has no interior gaps and every SSPI67 member has a score in every year 2000–2023. One member's 2023 score is carried: Argentina's last value is 2016, repeated for 2017–2023. Saudi Arabia starts in 2013 and is carried back thirteen years. The JMP values are themselves modelled estimates, so an imputed SANSRV score is an extrapolation of a model output. `local/2025-06-25-indicator-status.json`: "Coverage good just need several imputations."
- Potential direction A: keep extrapolation only (the executable behaviour).
- Potential direction B: add interpolation of interior gaps, or limit how far a value may be carried.

Current executable behavior:
- `extrapolate_forward(..., 2023)` then `extrapolate_backward(..., 2000)`, series by `CountryCode` and `DatasetCode`, scored with the compute formula, unit `Percent`.

Conflicting evidence:
- None in the legacy files. Raised for review because carried values are scored as if current.

Implementation decision in the new backend:
- The executable behaviour, exactly: `SeriesFillThenScore` with steps forward then backward and no interpolation. The golden variant `with_rows_removed` shows an interior gap left empty and a single-year series carried both ways, as in legacy.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- Scores for country-years without a JMP estimate.

Question for methodology review:
- Should SANSRV interpolate gaps, and should stale values be carried without a limit?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/sansrv.py`, `sspi_flask_app/api/resources/utilities.py`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/indicators/sansrv.py`, `src/sspi/indicators/strategy.py`, `tests/golden/test_golden_sansrv.py`

---

## DRKWAT-1 — DRKWAT has no imputation, so countries without a safely managed water estimate are never scored, and the 2018 static values differ from today's series

Status: unresolved

Summary for the methodology team:
- Problem: legacy DRKWAT has a compute route only. No impute route exists anywhere in the pinned repository. `SH.H2O.SMDW.ZS` is published only where the JMP can estimate all three criteria: accessible on premises, available when needed, free from contamination. Live 2026-10-19 (*illustrative*): nine SSPI67 members have no estimate at all (Argentina, Australia, China, Kenya, Saudi Arabia, Thailand, Türkiye, Uruguay, Venezuela). The United States starts in 2005, Poland in 2005 and Korea in 2002. That leaves 1,356 of the 1,584 SSPI67 country-years 2000–2023 scored. `local/2025-06-25-indicator-status.json` says "Coverage good just need several imputations", but none was written. The 2018 static values follow the (0, 100) goalposts but differ from today's series for most countries (Brazil 2015: 97.5 static, 82.0 now). The JMP has revised the series heavily, and the static values are not clearly from it.
- Potential direction A: keep observed scores only (the executable behaviour).
- Potential direction B: impute (series fill, a reference class, or a related JMP series for countries without a safely managed estimate). Substituting basic or improved water would change the measure.

Current executable behavior:
- `compute_drkwat`: `goalpost(WB_DRKWAT, 0, 100)` (metadata goalposts) on every clean row, unit `%`.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json`; `local/SSPIStaticData2018.csv` (`DRKWAT_RAW`).

Implementation decision in the new backend:
- Direction A: no imputation, exact parity with the compute route.

Reason:
- The executable route is the legacy methodology.

Potential impact:
- No DRKWAT score for the nine members, or before a series starts.

Question for methodology review:
- Should DRKWAT be imputed and, if so, how, without changing what it measures?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/drkwat.py`, `sspi_flask_app/api/core/datasets/wb/wb_drkwat.py`, `local/2025-06-25-indicator-status.json`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/indicators/drkwat.py`, `tests/golden/test_golden_drkwat.py`

---

## INTRNT-1 — INTRNT's executable route reads datasets the metadata does not list, averages two raw values of different kinds, and the legacy database refused every such score

Status: unresolved

Summary for the methodology team:
- Problem, four layers:
  1. **Datasets.** The canonical metadata lists `UNSDG_AVINTR` ("percentage of households with internet access", source SDG 17.6.1) and `CABLE_QUINTR` ("fixed broadband download speed in Mbps", Cable.co.uk, but series code `IT.NET.USER.ZS`). The executable route reads two other datasets, `WB_INTRNT` and `UNSDG_INTRNT`. Neither has a documentation file, so neither is in the canonical catalog.
  2. **Measures.** `WB_INTRNT` is World Bank `IT.NET.USER.ZS`, individuals using the internet, % of population: people, not households. `UNSDG_INTRNT` is SDG 17.6.1 series `IT_NET_BBND` with `type_of_speed = 10MBPS`: fixed broadband subscriptions of 10 Mbps or more per 100 inhabitants. That is a subscription rate, not a measured speed, and not Cable.co.uk data.
  3. **Formula.** The route scores `(WB_INTRNT + UNSDG_INTRNT) / 2`, the raw average of a percentage and a rate per 100, with no goalposts. The methodology's score function instead averages `goalpost(UNSDG_INTRNT, 0, 100)` and `goalpost(WB_INTRNT, 0, 100)`. It names the executable datasets, not the listed ones.
  4. **Outcome.** The legacy indicator collection rejects any score outside [0, 1] when inserting. Run on the live sources (2026-10-19, *illustrative*), the pinned cleaners keep 5,971 `WB_INTRNT` and 2,023 `UNSDG_INTRNT` rows. The route forms 1,921 complete groups, of which 11 lie in [0, 1] (maximum 77.36; Malaysia around 30). It then raises `InvalidDocumentFormatError: 'Score' must be less than or equal to 1` before storing anything, after deleting the stored INTRNT scores. The legacy backend therefore never stored an INTRNT score from this route.
- The 2018 static INTRNT values are on a 0–1 scale. They are close to the goalposted (0 → 100) average of internet users and 10 Mbps broadband subscriptions (median difference about 0.04 against today's revised series), the methodology's formula rather than the executable one.
- Potential direction A: adopt the methodology formula (`goalpost(·, 0, 100)` on both inputs) with the executable datasets, recording `WB_INTRNT` and `UNSDG_INTRNT` in the catalog.
- Potential direction B: adopt the listed measures (households with internet access; measured broadband speed from a new source).
- Potential direction C: leave INTRNT unported.

Current executable behavior:
- `compute_intrnt` raises on real data, as above; nothing is stored. No impute route.

Conflicting evidence:
- `methodology/pg/inf/intrnt/methodology.md` (datasets, description, score function) against `sspi_flask_app/api/core/sspi/pg/inf/intrnt.py`; `datasets/cable/cable_quintr/documentation.md` (Cable.co.uk name, WDI series code); `local/SSPIStaticData2018.csv`, `local/IndicatorDetailsStatic.csv`.

Implementation decision in the new backend:
- Not ported. Producing any INTRNT score requires choosing a normalization or a dataset mapping the legacy code never executed. This is unlike FDEPTH: there the observed route stored scores and only the impute route was inoperative. INTRNT is not registered, its listed datasets are not ingestible, and no alias between the listed and executable dataset codes is invented.

Reason:
- The pinned route produced no stored output, and making it produce one is a methodology decision.

Potential impact:
- No INTRNT score.

Question for methodology review:
- Which internet-access and internet-quality measures should INTRNT use, and with which goalposts? Decisions needed, in order:
  1. Which datasets: the executable `WB_INTRNT` and `UNSDG_INTRNT`, the listed `UNSDG_AVINTR` and `CABLE_QUINTR`, or others?
  2. How is internet access normalized (the share of individuals, or of households, on which goalposts)?
  3. How are broadband subscriptions normalized (subscriptions of 10 Mbps or more per 100 inhabitants on which goalposts, or a different speed tier)?
  4. Does INTRNT measure connection quality (speed), subscription availability, or both?
  5. Which goalposts and which weights combine the two parts?
  6. Should another source be chosen, for example a measured-speed series?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/intrnt.py`, `sspi_flask_app/api/core/datasets/wb/wb_intrnt.py`, `sspi_flask_app/api/core/datasets/unsdg/unsdg_intrnt.py`, `sspi_flask_app/models/database/sspi_indicator_data.py`, `methodology/pg/inf/intrnt/methodology.md`, `datasets/cable/cable_quintr/documentation.md`, `datasets/unsdg/unsdg_avintr/documentation.md`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/INTRNT.yaml`, `src/sspi/metadata/data/datasets/UNSDG_AVINTR.yaml`, `src/sspi/metadata/data/datasets/CABLE_QUINTR.yaml`, `docs/indicator-migration.md`

---

## TRNETW-1 — TRNETW has no executable implementation and no defined source

Status: unresolved

Summary for the methodology team:
- Problem: the methodology describes TRNETW as "the average of two measures: the natural log of rail lines per square kilometer (millions) per capita (millions) and the natural log of roadways per square kilometer per capita", with score function `average(goalpost(WB_RAILNT, 0, 100), goalpost(CIA_ROADNT, 0, 100))`. At the pinned commit:
  - `trnetw.py` holds one import, with no compute or impute route;
  - `WB_RAILNT` has no definition;
  - `CIA_ROADNT` has a documentation file (CIA World Factbook, no series or query code) but no collector or cleaner;
  - the CIA dataset module (`api/core/datasets/cia/cia.py`) is empty;
  - no other code path computes it, now or in the repository's history.
- The 2018 static SSPI scored TRNETW from road and rail network intensity with goalposts (0, 5) for rail and (0, 6) for road (`local/IntermediateDetailsStatic.csv`), not the (0, 100) of the methodology text. `local/2025-06-25-indicator-status.json` says "Redesign Required".
- Potential direction A: leave TRNETW unported until it is redesigned.
- Potential direction B: define the rail and road inputs (sources, units, the area and population normalization, the logarithms) and goalposts, then implement.

Current executable behavior:
- None.

Conflicting evidence:
- `methodology/pg/inf/trnetw/methodology.md` against `local/IntermediateDetailsStatic.csv` and the absence of any executable path.

Implementation decision in the new backend:
- Not ported. TRNETW is not registered, `WB_RAILNT` is an unresolved catalog entry and `CIA_ROADNT` is not ingestible. No golden output is manufactured.

Reason:
- There is no executable legacy methodology to preserve.

Potential impact:
- No TRNETW score.

Question for methodology review:
- What should TRNETW measure, from which sources? Decisions needed:
  - the road network measure (total, paved or motorway length);
  - the rail network measure (route-kilometres, and from which series);
  - normalization by country size (land area);
  - normalization by population;
  - units, and whether natural logarithms are taken as the methodology text says;
  - goalposts and direction for each part, and how they are combined;
  - source and publication year (the CIA World Factbook and a World Bank rail series are named but never defined);
  - missing data: which countries have no rail network, and whether a missing part is imputed, scored as zero or omitted.

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/inf/trnetw.py`, `sspi_flask_app/api/core/datasets/cia/cia.py`, `methodology/pg/inf/trnetw/methodology.md`, `datasets/cia/cia_roadnt/documentation.md`, `local/IntermediateDetailsStatic.csv`, `local/2025-06-25-indicator-status.json`

Relevant new-backend files:
- `src/sspi/metadata/data/indicators/TRNETW.yaml`, `src/sspi/metadata/data/datasets/WB_RAILNT.yaml`, `src/sspi/metadata/data/datasets/CIA_ROADNT.yaml`, `docs/indicator-migration.md`

---

## MURDER-1 — The World Bank cleaner treats a reported zero homicide rate as missing, and the impute route then fills it

Status: unresolved

Summary for the methodology team:
- Problem: the shared World Bank cleaner (`clean_wb_data`) keeps a row only if its value is truthy, so a reported `0` is dropped like a null. For homicides, zero is a meaningful and best-possible value. The impute route then interpolates across the hole. Live 2026-10-25 (*illustrative*): `VC.IHR.PSRC.P5` has five zeros, Iceland 2006, Liechtenstein 2007 and 2009, Malta 2006 and the Channel Islands 2010 (not an ISO country, skipped anyway). Iceland, an SSPI67 member, gets an interpolated 0.826 per 100,000 for 2006 and scores 0.9587 instead of 1.0.
- Potential direction A: keep the executable behaviour (zeros are missing).
- Potential direction B: keep reported zeros as observations for MURDER (a change to the shared cleaner's semantics for this dataset, or for every World Bank dataset).

Current executable behavior:
- `clean_wb_murder` → `clean_wb_data(raw, "WB_MURDER", "Per 100,000 people")`, which skips falsy values; `impute_murder` interpolates every interior gap.

Conflicting evidence:
- The methodology describes the measure as "Intentional homicides per 100,000 people"; nothing says a zero is missing.

Implementation decision in the new backend:
- Preserve the legacy behaviour: `normalize_worldbank_dataset` counts a zero as a missing value (as for every World Bank dataset), and MURDER's series fill interpolates it. Exact parity (`tests/golden/test_golden_murder.py`).

Reason:
- Executable behaviour is the specification until the methodology team decides; the cleaner is shared by every World Bank dataset.

Potential impact:
- Four country-years today (one SSPI67 member-year), each scored slightly below 1.0. Small countries with rare homicides are the ones affected.

Question for methodology review:
- Should a reported zero homicide rate be an observation for MURDER, and should the same apply to the other World Bank datasets?

Relevant legacy files:
- `sspi_flask_app/api/datasource/worldbank.py`, `sspi_flask_app/api/core/datasets/wb/wb_murder.py`, `sspi_flask_app/api/core/sspi/pg/saf/murder.py`

Relevant new-backend files:
- `src/sspi/ingestion/worldbank.py`, `src/sspi/indicators/murder.py`, `tests/golden/test_golden_murder.py`

---

## MURDER-2 — MURDER's impute route carries every series to 2000 and 2023 and interpolates every gap, however far the nearest observation is

Status: unresolved

Summary for the methodology team:
- Problem: `impute_murder` interpolates every interior gap (any year, also before 2000), then carries the last value forward to 2023 and the first back to 2000, with no limit on distance and no recipient group. Live 2026-10-25 (*illustrative*, full World Bank response, 4,043 observations): 1,719 imputed scores (609 interpolated, 675 carried forward, 435 carried back); every SSPI67 member-year 2000–2023 is scored, 1,262 of 1,584 from observations. Thailand and Viet Nam (last values 2011) repeat 2011 for 2012–2023; Iraq repeats 2013 for ten years; Iran (2014), Egypt (2017), Bangladesh (2018) and Saudi Arabia (2019) are carried forward; Nigeria's first value (2016, 32.4 per 100,000) is carried back sixteen years; Ethiopia's single value (2012) fills all 24 years. Gaps from 1995 on are interpolated, including years before 2000.
- Potential direction A: keep the executable behaviour.
- Potential direction B: limit extrapolation distance, or mark long carries for exclusion from aggregates.

Current executable behavior:
- `impute_murder`: `interpolate_linear` + `extrapolate_forward(..., 2023)` + `extrapolate_backward(..., 2000)`, each from the observed rows, `series_id=["CountryCode", "DatasetCode"]`, `impute_only=True`; the three never fill the same year. Scored with `goalpost(WB_MURDER, 20, 0)`, unit `Index`.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json` lists MURDER as "Attention Required, Data is Available But Needs to Be Collected", with no note on imputation. The 2018 static file used 2016 values.

Implementation decision in the new backend:
- `SeriesFillThenScore(score_murder, (2000, 2023), steps=("interpolate", "forward", "backward"))`; exact parity on the committed sample and on the full live response.

Reason:
- Preserving executable behaviour.

Potential impact:
- Long carries make recent MURDER scores for several SSPI67 members reflect conditions a decade or more ago.

Question for methodology review:
- Should MURDER's extrapolation be bounded, and should interpolation before 2000 be kept?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/saf/murder.py`, `sspi_flask_app/api/resources/utilities.py`

Relevant new-backend files:
- `src/sspi/indicators/murder.py`, `src/sspi/indicators/strategy.py`, `tests/golden/test_golden_murder.py`

---

## CYBSEC-1 — The pinned CYBSEC ingestion cannot store the transcription: it reads a path that no longer exists, and five country names have no code

Status: resolved

> **✅ DECISION — project owner, 2026-10-25**
>
> - Approved source correction: map the five transcription spellings the legacy matcher cannot place to CIV, MKD, FSM, PSE and VAT, each verified against its ISO 3166-1 identity first.
> - A documented, source-specific alias table; the original ITU transcription is not altered and the generic country mapping is unchanged.
> - An explicitly approved representation correction, not a scoring change: editions, scaling (2020 and 2024 divided by 100) and `goalpost(ITU_CYBSEC, 0, 1)` stay as executed; no interpolation or extrapolation.

Summary for the methodology team:
- Problem: CYBSEC's only source is the SSPI's hand transcription of ITU Global Cybersecurity Index scores. The pinned collector and cleaner both read `local/gci-local-indicator-summary.csv`, but the file was moved unchanged to `local/CYBSEC/` on 2025-03-27 (commit 170274b32), so at the pinned commit both raise `FileNotFoundError`. Placed at the old path, the cleaner runs, but the legacy name matcher (`get_country_code`) returns five names unchanged: "Cote d'Ivoire", "Macedonia", "Micronesia", "State of Palestine", "Vatican". The legacy clean collection refuses the whole insert for a country code that is not three characters, so no `ITU_CYBSEC` row, and no CYBSEC score, could be stored. None of the five is an SSPI67 member.
- Potential direction A: keep CYBSEC unrun until the transcription is corrected or a name table is approved.
- Potential direction B: approve explicit name corrections for the transcription (CIV, MKD, FSM, PSE, VAT), recorded as source-representation corrections. **Chosen.**
- Potential direction C: drop rows whose names do not resolve (none is SSPI67), recording them as skipped.

Current executable behavior:
- `load_itu_data_from_local_transcription` and `clean_itu_data` read the missing path; `clean_itu_cybsec` inserts the cleaner's rows; `compute_cybsec` scores `goalpost(ITU_CYBSEC, 0, 1)`, unit `Index`, with no impute route.

Conflicting evidence:
- `local/indicator-confident.json`: "Confident we will be done with good data coverage in the next few weeks". `local/2025-06-25-indicator-status.json`: "Moderate Data Issues".

Implementation decision in the new backend:
- A generic local-file source (`src/sspi/ingestion/localfiles.py`, SHA-256-pinned) and an ITU normalizer reproducing the legacy cleaner exactly (`src/sspi/ingestion/itu.py`).
- `APPROVED_NAME_CORRECTIONS` in `src/sspi/ingestion/itu.py` holds exactly the five spellings and codes (pycountry: Côte d'Ivoire; North Macedonia; Micronesia, Federated States of; Palestine, State of; Holy See (Vatican City State)). It applies only to a name the legacy matcher returned unchanged; each corrected observation records `country_code_correction`. Any other uncoded name, a repeated country-year or a non-number is still an error.
- Registered in `APPROVED_SOURCE_CORRECTIONS` (`tests/golden/parity.py`); the migration gate checks the registration both ways.

Reason:
- The project owner's decision above.

Potential impact:
- Original transcription (*illustrative*, 2026-10-25): 968 observations, 195 countries; the five corrected countries gain 24 country-editions; 325 of the 330 SSPI67 member-editions are scored (Canada missing, CYBSEC-3).

Question for methodology review:
- None for this entry; CYBSEC-2 and CYBSEC-3 remain open.

Resolution evidence:
- Decision: the project owner's instruction of 2026-10-25 (box above).
- Code: `APPROVED_NAME_CORRECTIONS` and `normalize_itu_dataset` in `src/sspi/ingestion/itu.py`; the generic matcher `legacy_country_code` in `src/sspi/ingestion/geo.py` is unchanged.
- Evidence, in three separate steps: (A) the legacy failure, recorded in `tests/golden/itu_cybsec_synthetic_cases.json` and, opt-in, on the original file; (B) corrected normalization equal to the legacy cleaner's own rows with only the correction applied; (C) CYBSEC equal to the legacy compute route's scores on those rows. `tests/golden/test_golden_cybsec.py` (`test_a_...`, `test_b_...`, `test_c_...`) and `tests/golden/test_golden_public_safety_real_data.py`.

Relevant legacy files:
- `sspi_flask_app/api/datasource/itu.py`, `sspi_flask_app/api/core/datasets/itu/itu_cybsec.py`, `sspi_flask_app/api/core/sspi/pg/saf/cybsec.py`, `sspi_flask_app/api/resources/utilities.py` (`get_country_code`), `sspi_flask_app/models/database/mongo_wrapper.py`, `local/CYBSEC/gci-local-indicator-summary.csv`

Relevant new-backend files:
- `src/sspi/ingestion/localfiles.py`, `src/sspi/ingestion/itu.py`, `src/sspi/ingestion/geo.py`, `src/sspi/indicators/cybsec.py`, `tests/golden/test_golden_cybsec.py`, `tests/golden/test_golden_public_safety_real_data.py`
---

## CYBSEC-2 — CYBSEC compares GCI editions built on different scales and methods, and dates each by its edition label

Status: unresolved

Summary for the methodology team:
- Problem: the transcription holds five GCI editions. 2014, 2017 and 2018 publish scores on 0–1; 2020 and 2024 on 0–100, which the cleaner divides by 100 (it divides those two columns only, which puts all five on 0–1). The editions are different instruments: the questionnaire, the pillars, the weights and, in 2024, a tier-based presentation all changed. Scores rise sharply across editions. In the original transcription (*illustrative*), the mean score is 0.282 (2014), 0.354 (2017), 0.433 (2018), 0.515 (2020) and 0.651 (2024), and twelve countries score exactly 1.0 in 2024. Each edition is stored under its label year (the 2018 edition was published in 2019, the 2020 edition in 2021), and CYBSEC has no impute route, so scores exist for those five years only. The observation unit is the literal `Percentage` although the values are 0–1.
- Potential direction A: keep the executable behaviour.
- Potential direction B: treat editions as non-comparable (for example rank-based or edition-normalised scores), or date them by data year.

Current executable behavior:
- `clean_itu_data`: `df['2024'] / 100`, `df['2020'] / 100`, melt, unit `Percentage`; `compute_cybsec`: `goalpost(ITU_CYBSEC, 0, 1)`.

Conflicting evidence:
- The methodology describes "a composite index combining 25 indicators", which fits only some editions.

Implementation decision in the new backend:
- Reproduce the cleaner exactly, including the selective division and the edition years (`DIVIDED_BY_100` in `src/sspi/ingestion/itu.py`).

Reason:
- Silently rescaling or redating editions is a methodology change.

Potential impact:
- Apparent improvement over time may be an artefact of the method changes; scores exist only in five years.

Question for methodology review:
- Are GCI editions comparable enough to score on one scale, and which year should each represent?

Relevant legacy files:
- `sspi_flask_app/api/datasource/itu.py`, `local/CYBSEC/gci-local-indicator-summary.csv`, `local/CYBSEC/global_cybersecurity_index_2024.pdf`

Relevant new-backend files:
- `src/sspi/ingestion/itu.py`, `tests/golden/test_golden_cybsec.py`

---

## CYBSEC-3 — Canada, an SSPI67 member, is missing from the GCI transcription

Status: unresolved

Summary for the methodology team:
- Problem: the transcription has 196 rows. Canada is not one of them, so it has no CYBSEC observation in any of the five editions (2014, 2017, 2018, 2020, 2024); with no impute route it has no CYBSEC score. Every other SSPI67 member appears in all five editions.
- What the ITU reports say (read 2026-10-25 from the official PDFs at itu.int, kept privately in `local-data/itu/reports/`; *not merged into any data*):

  | Edition | Report | Canada | Note in the report |
  |---|---|---|---|
  | 2014 | Global Cybersecurity Index & Cyberwellness Profiles (2015) | 0.794 (rank 2) | "* Based on secondary data (Source: ABI Research)" |
  | 2017 | Global Cybersecurity Index 2017 | 0.818 (rank 9) | — |
  | 2018 | Global Cybersecurity Index 2018 | 0.892 (rank 9) | "countries marked with an * ... did not participate in the GCI 2018 process" |
  | 2020 | Global Cybersecurity Index 2020 (2021) | 97.67 (rank 8) | "** no response to the questionnaire / data collected by GCI Team" |
  | 2024 | Global Cybersecurity Index 2024 | not printed: Tier 2 "Advancing" (score 85–95) | country profiles are images |

  The same reports reproduce the transcription's values for Malaysia (0.765, 0.893, 0.893, 98.06), so the transcription agrees with them where checked. Four of Canada's five values are thus published; the 2024 one is only a range, and three of the four carry the reports' "secondary data / no questionnaire response" markers.
- Potential direction A: leave the transcription as it is (Canada unscored).
- Potential direction B: add Canada's 2014–2020 values from the reports, verified and recorded as an approved data correction; decide what to do for 2024 (a published score from another ITU source, or none).

Current executable behavior:
- No `CAN` row is produced.

Conflicting evidence:
- The GCI reports list Canada in every edition.

Implementation decision in the new backend:
- The transcription is read as pinned; nothing is added or merged.

Reason:
- Adding transcribed values is creating source data, which needs approval.

Potential impact:
- One SSPI67 member without CYBSEC in every edition (5 of 330 SSPI67 member-editions).

Question for methodology review:
- Should Canada's published values be added to the transcription, by whom and with what verification, and what should represent 2024?

Relevant legacy files:
- `local/CYBSEC/gci-local-indicator-summary.csv`, `local/CYBSEC/global_cybersecurity_index_2024.pdf`

Relevant new-backend files:
- `tests/golden/test_golden_public_safety_real_data.py`
---

## SECAPP-1 — No FSI value was ever stored by the pinned legacy code: its collector, raw document shape, source query and cleaner all fail

Status: resolved

> **✅ DECISION — project owner, 2026-10-25**
>
> - Approved source correction: implement a reusable adapter for the official FSI annual workbooks (https://fragilestatesindex.org/excel/), dataset `FSI_SECAPP`, component C1 only, scored `goalpost(FSI_SECAPP, 10, 0)`, unit `Index`, no imputation.
> - Preserve the executable cleaner's intended country and year transformations; verify country mappings; reject duplicates and ambiguous identities; check years against workbook content and file names; document any divergence caused by repairing acquisition.

>
> **✅ DECISION — project owner, 2026-10-26**
>
> - Approved source correction, confirmed: strip leading and trailing whitespace from FSI country names before ISO3 normalization.
> - Approved source correction, confirmed: map "North Korea" to PRK, keeping "South Korea" as KOR.
> - Both are source-identity repairs, not methodology changes. SECAPP-3 (Israel's unit change in 2021) stays unresolved for separate research review.

Summary for the methodology team:
- Problem: SECAPP scores the Fragile States Index indicator C1, Security Apparatus (0 best, 10 worst), with `goalpost(FSI_SECAPP, 10, 0)`. At the pinned commit the acquisition fails at every step, independently of the data: (1) `collect_fsi_data` requests `https://fragilestatesindex.org/excel/` but parses the address string, not the page (`BeautifulSoup(base_url, ...)`), so it finds no workbook link and stores nothing; (2) it would store `Raw` as a list of rows, while `clean_fsi_data` reads `Raw["json"]` (`TypeError`); (3) it would record source fields that differ from the documented source the cleaner queries, so the cleaner finds no raw document; (4) the registered cleaner's rows carry `IndicatorCode` FSI_SECAPP but no `DatasetCode`, so the clean collection refuses them. The bug in (1) dates from 2025-07-18 (3b0932030); the March 2025 collector parsed the page and stored `{"json": rows}`, the shape the pinned cleaner reads. On the 18 official workbooks the cleaner's name matching also fails in every edition: 99 unmatched name-editions (padded names in 2006, "Serbia  " in 2006–2009, "Uruguay " in 2011, "Cote d'Ivoire", "Macedonia", "Micronesia", "Palestine") and "North Korea" and "South Korea" both KOR in all 18.
- Potential direction A: leave SECAPP unported.
- Potential direction B: an FSI workbook adapter with approved name corrections. **Chosen (adapter approved).**

Current executable behavior:
- `compute_secapp`: `goalpost(FSI_SECAPP, 10, 0)` on clean `FSI_SECAPP` documents, unit `Index`; no impute route. No such document can be produced by the pinned collector and cleaner.

Conflicting evidence:
- `local/2025-06-25-indicator-status.json`: "Finalization In Progress, Minor Data Issues". The 2018 static file holds 2019 FSI values.

Implementation decision in the new backend:
- `src/sspi/ingestion/fsi.py` pins the 18 editions linked from the /excel/ page on 2026-10-25 (first link per year, as the March 2025 collector kept), each by URL and SHA-256. It reproduces the pinned cleaner on each workbook as that collector stored it: `Country`, `Year` and `C1: Security Apparatus` only, the value as read (no rounding), a date `Year` reduced to its calendar year.
- Divergences caused by repairing acquisition, all recorded on every affected observation (`country_code_correction`) and none changing a value or a year: the dataset code is set; names are stripped of surrounding whitespace; `APPROVED_NAME_CORRECTIONS` maps "Cote d'Ivoire" → CIV, "Macedonia" → MKD, "Micronesia" → FSM, "Palestine" → PSE (the identities approved for CYBSEC-1) and "North Korea" → PRK; added checks refuse a year that differs from the edition, a non-finite value, an uncoded name and a duplicate identity.
- Exact parity: the adapter equals the pinned cleaner's own rows with only that repair applied, and SECAPP equals the pinned compute route on them, on synthetic workbooks (`tests/golden/test_golden_secapp.py`) and, opt-in, on all 18 originals (3,170 observations and scores). Every row whose name needed no repair is the pinned cleaner's row unchanged.
- Registered in `APPROVED_SOURCE_CORRECTIONS` (`tests/golden/parity.py`).

Reason:
- The project owner's decisions above.

Potential impact:
- 3,170 observations, 179 countries, 2006–2023. SSPI67: 1,185 of the 1,188 member-years 2006–2023 (the United Arab Emirates, Iceland and Luxembourg are not in the 2006 edition); nothing before 2006. North Korea's 18 values would otherwise collide with South Korea's (an SSPI67 member).

Question for methodology review:
- None for this entry; SECAPP-2 and SECAPP-3 remain open.

Resolution evidence:
- Decisions: the project owner's approval of the FSI adapter (2026-10-25) and confirmation of the whitespace stripping and the North Korea mapping (2026-10-26), boxes above.
- Code: `APPROVED_NAME_CORRECTIONS`, `country_code` and `normalize_fsi_dataset` in `src/sspi/ingestion/fsi.py`; the generic matcher `legacy_country_code` in `src/sspi/ingestion/geo.py` is unchanged. Registered with every correction in `APPROVED_SOURCE_CORRECTIONS` (`tests/golden/parity.py`), marked confirmed.
- Evidence, in three separate steps: (A) the pinned failure; (B) the adapter equal to the pinned cleaner's own rows with only the repair applied; (C) SECAPP equal to the pinned compute route on them. `tests/golden/test_golden_secapp.py` and, on the 18 originals, `tests/golden/test_golden_public_safety_real_data.py`.

Relevant legacy files:
- `sspi_flask_app/api/datasource/fsi.py`, `sspi_flask_app/api/core/datasets/fsi/fsi_secapp.py`, `sspi_flask_app/api/core/sspi/pg/saf/secapp.py`, `datasets/fsi/fsi_secapp/documentation.md`, `sspi_flask_app/api/resources/utilities.py` (`get_country_code`)

Relevant new-backend files:
- `src/sspi/ingestion/fsi.py`, `src/sspi/indicators/secapp.py`, `tests/golden/generate_public_safety_cases.py`, `tests/golden/test_golden_secapp.py`, `tests/golden/test_golden_public_safety_real_data.py`
---

## SECAPP-2 — SECAPP's status note promises backward extrapolation that no route implements, and FSI editions are dated by their edition year

Status: unresolved

Summary for the methodology team:
- Problem: `local/2025-06-25-indicator-status.json` says "Data is available after 2006. Using backward extrapolation for 2000 to 2006." There is no SECAPP impute route at the pinned commit, so SECAPP has no score before 2006. Separately, in all 18 workbooks the `Year` cells equal the edition year in the file name (checked 2026-10-25), and the cleaner stores that year. The FSI's methodology page describes an annual assessment of "key events from that year, compared to the previous one" but does not state which calendar year an edition assesses; the FSI is commonly described as assessing the year before publication, which this migration has not verified.
- Potential direction A: follow the executable (no imputation; edition year).
- Potential direction B: implement the documented backward extrapolation, and/or shift editions to the year they assess.

Current executable behavior:
- No impute route; `Year` taken from the workbook as is (the edition year).

Conflicting evidence:
- The status note quoted above.

Implementation decision in the new backend:
- Direction A: no imputation, edition year (`src/sspi/indicators/secapp.py`, `src/sspi/ingestion/fsi.py`).

Reason:
- Both are methodology choices.

Potential impact:
- No SECAPP score for 2000–2005; if editions assess the previous year, every SECAPP score is dated one year late.

Question for methodology review:
- Should SECAPP be extrapolated backward to 2000, and which year should an FSI edition represent?

Relevant legacy files:
- `local/2025-06-25-indicator-status.json`, `sspi_flask_app/api/datasource/fsi.py`

Relevant new-backend files:
- `src/sspi/ingestion/fsi.py`, `tests/golden/test_golden_secapp.py`
---

## SECAPP-3 — Israel's FSI unit of assessment changes in 2021, from "Israel and West Bank" to Israel alone

Status: unresolved

Summary for the methodology team:
- Problem: through the 2020 edition the FSI assesses "Israel and West Bank" as one unit, which the legacy matcher maps to ISR (an explicit legacy rule). From 2021 it lists "Israel" and "Palestine" separately. Israel's C1 falls from 6.0 (2020) to 2.4 (2021), its SECAPP score from 0.40 to 0.76, a break caused by the change of unit, not of conditions. Palestine (PSE, not SSPI67) is scored only from 2021.
- Potential direction A: keep the series as published (the executable behaviour).
- Potential direction B: treat 2006–2020 and 2021– as different measures for Israel (for example drop or flag one segment).

Current executable behavior:
- `get_country_code("Israel and West Bank")` → ISR; "Israel" → ISR.

Conflicting evidence:
- The FSI's own change of unit in 2021.

Implementation decision in the new backend:
- Direction A, as executed.

Reason:
- A methodology choice.

Potential impact:
- One SSPI67 member (Israel) with a structural break of about 0.36 in SECAPP between 2020 and 2021.

Question for methodology review:
- How should SECAPP treat Israel's change of FSI unit in 2021?

Relevant legacy files:
- `sspi_flask_app/api/resources/utilities.py` (`get_country_code`)

Relevant new-backend files:
- `src/sspi/ingestion/fsi.py`, `tests/golden/test_golden_public_safety_real_data.py`

---

## PRISON-1 — The United Kingdom's prison rate is the unweighted mean of whichever jurisdictions reported that year

Status: unresolved

Summary for the methodology team:
- Problem: UNODC reports the United Kingdom as three jurisdictions (`GBR_E_W`, `GBR_S`, `GBR_NI`). The cleaner builds a `GBR` row per year as the plain mean of the jurisdictions' rates present that year (its own comment calls this a stand-in for a population-weighted average). England and Wales hold about 89 % of the population, so the unweighted mean is too low, and when a jurisdiction is missing the mean changes composition. In the release of 30/09/2026 (*illustrative*), the mean is 118.41 per 100,000 for 2022 where a population-weighted rate (implied by the same workbook's counts and rates) is 133.76; 2003–2004 average England and Wales with Scotland only; 2023 averages Scotland and Northern Ireland only (England and Wales not yet reported): 118.62 against a weighted 130.32. The score difference is about 0.03 per year (goalposts 540 → 40). The 2018 SSPI stored 361 for the UK, close to the sum of the three rates.
- Potential direction A: keep the unweighted mean (the executable behaviour).
- Potential direction B: a population-weighted rate (from the same workbook's counts, or from population data), and a rule for years with missing jurisdictions.

Current executable behavior:
- `clean_unodc_pripop`: `gbr_regions.groupby("Year").agg({"VALUE": "mean"})` after the same six filters, appended as `GBR`.

Conflicting evidence:
- The cleaner's comment ("For population-weighted average of rates, we'll use simple average for now"); the 2018 static value.

Implementation decision in the new backend:
- Reproduced exactly (`REGIONAL_MEANS` in `src/sspi/ingestion/unodc.py`, same pandas operation); each `GBR` observation records the jurisdictions averaged in `unweighted_mean_of`.

Reason:
- The cleaner's rule is the executable methodology; a weighted rate is a methodology change.

Potential impact:
- The UK's PRISON score is overstated by about 0.03, more in years with missing jurisdictions.

Question for methodology review:
- Should the UK rate be population-weighted, and what should happen when a jurisdiction has not reported?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unodc/unodc_pripop.py`, `local/SSPIStaticData2018.csv`

Relevant new-backend files:
- `src/sspi/ingestion/unodc.py`, `tests/golden/test_golden_prison.py`, `tests/golden/test_golden_public_safety_real_data.py`

---

## PRISON-2 — China, with no UNODC series, gets the flat mean of every value in the workbook for 2000–2023; observed Chinese data would stop the route

Status: unresolved

Summary for the methodology team:
- Problem: UNODC publishes no prison rate for China. `impute_prison` gives China, hard-coded, `impute_reference_class_average("CHN", 2000, 2023, "Dataset", ...)`: the plain mean of every clean row, all 222 areas (territories, Holy See zeros, the UK mean) and all years, as China's value for every year. Release of 30/09/2026 (*illustrative*): 185.76 per 100,000 from 3,346 rows, scoring 0.7085 every year. The 2018 SSPI used 121 (World Prison Brief). If China ever gains an observed row, its series fill and the reference rows overlap; the legacy route then raised "Duplicate dataset document found" and stored no imputed PRISON score for any country (recorded by the generator's China probe).
- Potential direction A: keep the reference-class mean.
- Potential direction B: another source or estimate for China (for example World Prison Brief), or a reference class of comparable countries; and a precedence rule if China gains data.

Current executable behavior:
- `impute_prison`: `forward + backward + interpolated + prison_chn`, scored with `goalpost(UNODC_PRIPOP, 540, 40)`.

Conflicting evidence:
- The 2018 static value (121) came from another source.

Implementation decision in the new backend:
- `SeriesFillThenScore(..., listed_recipients=("CHN",))`: exact parity; if China has observed rows the strategy raises `ImputationError` before anything is written (no precedence decided), as legacy stored nothing.

Reason:
- Preserving executable behaviour; choosing a value for China is a methodology decision.

Potential impact:
- China's PRISON score is a world average, not a Chinese figure.

Question for methodology review:
- What should China's PRISON value be, and what should happen if UNODC publishes Chinese data?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/saf/prison.py`, `sspi_flask_app/api/resources/utilities.py`

Relevant new-backend files:
- `src/sspi/indicators/prison.py`, `src/sspi/indicators/strategy.py`, `tests/golden/test_golden_prison.py`

---

## PRISON-3 — PRISON's series fill carries old or single values across the whole 2000–2023 window

Status: unresolved

Summary for the methodology team:
- Problem: `impute_prison` carries each series forward to 2023, back to 2000 and interpolates gaps, with no distance limit. Release of 30/09/2026 (*illustrative*): 2,142 imputed scores (964 carried back, 945 interpolated, 209 carried forward, 24 for China); every SSPI67 member-year 2000–2023 is scored, 1,190 of 1,584 from observations. The workbook starts in 2003 (the 2025 release started in 2000), so every country's 2000–2002 is carried back. Observed 2024 values are scored, but nothing is filled after 2023. `local/2025-06-25-indicator-status.json` still says "Data available only through 2018" (the World Prison Brief era).
- Potential direction A: keep the executable behaviour.
- Potential direction B: bound the carries.

Current executable behavior:
- `extrapolate_forward(..., 2023)`, `extrapolate_backward(..., 2000)`, `interpolate_linear`, each from the observed rows.

Conflicting evidence:
- The status note quoted above.

Implementation decision in the new backend:
- `SeriesFillThenScore(score_prison, (2000, 2023), steps=("forward", "backward", "interpolate"), ...)`; exact parity.

Reason:
- Preserving executable behaviour.

Potential impact:
- Early-2000s PRISON scores repeat 2003 values for most countries.

Question for methodology review:
- Should PRISON's extrapolation be bounded?

Relevant legacy files:
- `sspi_flask_app/api/core/sspi/pg/saf/prison.py`

Relevant new-backend files:
- `src/sspi/indicators/prison.py`, `tests/golden/test_golden_prison.py`

---

## PRISON-4 — Iraq's sub-national prison rates are dropped, not combined, so a single national value is carried over 24 years

Status: unresolved

Summary for the methodology team:
- Problem: UNODC reports Iraq mostly as Central Iraq (`IRQ_C`, 2008–2013) and the Kurdistan Region (`IRQ_KRI`, 2009–2013). The cleaner keeps only three-character codes, so both are dropped; unlike the UK they are not combined. Release of 30/09/2026 (*illustrative*): Iraq's only kept value is a national 171.15 for 2021, carried back 21 years and forward 2 to fill 2000–2023.
- Potential direction A: keep the executable behaviour.
- Potential direction B: combine Iraq's units (with a weighting rule), as for the UK.

Current executable behavior:
- `clean_df[clean_df["CountryCode"].str.len() == 3]` after the UK aggregation.

Conflicting evidence:
- The UK special case shows the cleaner intended to keep countries reported by parts.

Implementation decision in the new backend:
- Reproduced: the units are reported as skipped areas.

Reason:
- Combining units is a methodology choice.

Potential impact:
- Iraq (SSPI67) has one observed PRISON year.

Question for methodology review:
- Should Iraq's reporting units be combined, and how?

Relevant legacy files:
- `sspi_flask_app/api/core/datasets/unodc/unodc_pripop.py`

Relevant new-backend files:
- `src/sspi/ingestion/unodc.py`, `tests/golden/test_golden_public_safety_real_data.py`

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
