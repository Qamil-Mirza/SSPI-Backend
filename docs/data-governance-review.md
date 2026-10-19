# Data-governance and licensing review items

This file records open questions about the **use, redistribution and
attribution of source data**. It is written for the research team, and is
reviewed alongside the methodology questions in
[`methodology-conflicts.md`](methodology-conflicts.md), which links here.

These items are **not methodology decisions**. They do not change how
anything is computed:
- no formula, source identifier, imputation strategy or score depends on
  their answers;
- the backend ingests and scores the real source data meanwhile.

What they decide is what the project may distribute (in the repository, in
test fixtures, in published files) and how it must credit the data.

## Rules for this file

- One entry per question, with a stable ID (`GOV-n`). IDs are never reused.
- `Status` is `open` or `closed`. An entry is closed only by a recorded
  answer: from the rights holder, or a decision by the project owner citing
  one. The entry then cites it under `Resolution evidence:`.
- Every entry is listed in the index below and cross-referenced from
  `methodology-conflicts.md` (`tests/unit/test_data_governance_review.py`).

## Index

| ID | Title | Classification | Status |
|---|---|---|---|
| GOV-1 | WHO Global Health Observatory data: governing terms, redistribution of extracts, third-party credits, UNICEF permission, attribution | DATA-GOVERNANCE / LICENSING REVIEW | open |
| GOV-2 | WEF Historical Competitiveness Data: governing licence, non-commercial use, redistribution of extracts and of the database, derived scores, attribution | DATA-GOVERNANCE / LICENSING REVIEW | open |

---

## GOV-1 — WHO Global Health Observatory data: governing terms, redistribution of extracts, third-party credits, UNICEF permission, attribution

Status: open

Classification: DATA-GOVERNANCE / LICENSING REVIEW (not a scoring-methodology decision)

Raised: 2026-10-19, during the Healthcare migration (ATBRTH, DPTCOV, PHYSPC).

> **DECISION: project owner, 2026-10-19**
>
> - Follow the legacy SSPI repository's approach to WHO data. The backend
>   keeps ingesting actual WHO GHO observations, persisting them in
>   PostgreSQL and computing scores from those values. No synthetic data in
>   production ingestion or scoring.
> - The WHO adapter and the Healthcare indicator implementations are
>   accepted. Their exact legacy methodology is preserved.
> - Licensing uncertainty does not block further backend development.
> - Keep the real WHO data available for local and opt-in validation. Use
>   synthetic fixtures for repository-distributable automated parity tests
>   until redistribution rights are confirmed.
> - Do not change scoring formulas, source identifiers, imputation,
>   golden-comparison requirements or the migration gate.
> - Do not commit original WHO data extracts while the redistribution
>   question remains open.

### Questions for the research team

1. **Which terms govern the GHO API?** Two WHO documents could apply:
   - The *Terms and conditions of use for WHO data compilations,
     aggregations, evaluations and analyses*
     (https://www.who.int/about/policies/publishing/data-policy/terms-and-conditions).
     They allow use, reproduction and distribution for public-health
     purposes; forbid sale or commercial promotion; allow no modification
     beyond minor styling without WHO's written authorization; and exclude
     material credited to another source.
   - The data.who.int terms
     (https://data.who.int/about/data/terms-and-conditions): CC BY 4.0 with
     additional terms (attribution as given in the metadata, no implied
     endorsement, no use of WHO's name or emblem).

   The GHO OData API (`https://ghoapi.azureedge.net/api/`) is documented on
   www.who.int. WHO says the GHO and data.who.int share one data source.
   Neither page says which terms govern this API, or the successor API WHO
   has announced.
2. **Can WHO source extracts be redistributed in the SSPI repository?**
   That means small unmodified row subsets of the GHO responses as test
   fixtures, and files derived from them (scores, filled-in series). A
   public repository can be downloaded and reused by anyone. A public API
   grants no redistribution right by itself.
3. **Do ATBRTH's third-party source credits impose additional
   conditions?** Every country row of `MDG_0000000025` carries a `Comments`
   field naming the survey or publication behind the value: national
   statistical offices and ministries, DHS (ICF), UNICEF MICS. The
   www.who.int terms exclude "materials credited to another source".
   Whether such a citation takes a row outside WHO's licence, or merely
   documents the provenance of WHO's compiled figure, is not established.
   Dropping `Comments` before redistribution would itself be a
   modification, so it is a question, not a workaround.
4. **Does DPTCOV require separate UNICEF permission?** `WHS4_100` is a
   WUENIC series, the WHO/UNICEF Estimates of National Immunization
   Coverage, produced jointly. WHO presents it without crediting another
   source. UNICEF's terms have not been reviewed. Skilled birth attendance
   (ATBRTH) is also a joint UNICEF/WHO database.
5. **What attribution is required?** That covers:
   - the form WHO asks for (the www.who.int terms ask for "WHO, title of
     dataset, year, date of access" and acknowledgement of the countries
     that provided the data);
   - where it must appear: repository, published scores, the researcher
     guide;
   - whether contributing countries or survey programmes must be named
     individually.

### Legal permission is not attribution

The two are often conflated:

- **Legal permission to redistribute.** It comes from whoever holds rights
  in the published compilation, and is stated in a licence or terms. For
  GHO data that is WHO, under one of the two documents above. For WUENIC it
  is a joint WHO/UNICEF product; for skilled birth attendance, a joint
  UNICEF/WHO database.
- **Attribution to contributing organizations.** It is a condition of
  those terms, and good practice towards the organizations behind
  individual values: WHO Member States, national statistical offices and
  ministries, the DHS Program, UNICEF MICS, the National Health Workforce
  Accounts.
- **They do not substitute for each other.** Crediting a contributor grants
  no permission. Being credited does not by itself make a contributor a
  rights holder in WHO's compilation. Question 3 is exactly where the two
  meet.

### Current state of the repository

**Production.** `WHO_ATBRTH`, `WHO_DPTCOV` and `WHO_PHYSPC`:
- are ingested from the live GHO API by `src/sspi/ingestion/who.py`;
- are stored with request URL, OData context, WHO's comment and change
  date in provenance;
- are scored by the accepted legacy methodology.

**Distributable automated tests use synthetic data.**
`tests/fixtures/who/<code>_synthetic.json` are invented GHO-shaped
responses written by `tests/fixtures/who/build_synthetic.py`, with every
row labelled synthetic. The golden files `tests/golden/who_*_synthetic_cases.json`
and `tests/golden/{atbrth,dptcov,physpc}_synthetic_cases.json` were
generated from them by the pinned legacy code
(`76f842b08e551dfa8fb9563e4c812be086654ba6`). `tests/golden/test_golden_who.py`
and `tests/db/test_healthcare_end_to_end.py` hold the new backend to exact
parity with that output. Nothing in the gate changed: a committed fixture,
golden files from the pinned commit, exact parity and a register row are
still required for every ingestible dataset and executable indicator.

**Real data is kept for local and opt-in validation, and not committed.**
These live in a git-ignored local directory (`local-data/who/`), pinned by
the committed `tests/fixtures/who/REAL_DATA.sha256`:
- the three GHO row subsets of 2026-10-18;
- the six golden files the pinned legacy code produced from them;
- the full responses of 2026-10-18 and 2026-10-19.

`SSPI_WHO_REAL_DATA=local-data/who` runs the original real-data parity
tests unchanged (`tests/golden/test_golden_who_real_data.py`, marker
`who_real_data`) and the end-to-end workflow on the real subsets. The full
live validation of 2026-10-19 (identical legacy and new-backend digests on
every row WHO served) is recorded in `tests/fixtures/who/README.md`.

**Not committed while this item is open:** any file under `local-data/`,
and any other original WHO extract. `tests/golden/test_golden_who.py` fails
if a file pinned by `REAL_DATA.sha256` appears under `tests/`.

**Still quoted in the repository, for the research team to confirm.**
These are individual WHO figures, cited, not extracts:
- in `docs/indicator-migration.md`: real-fixture coverage and live-validation
  tables, such as Austria's 95.42 doctors per 10,000 in 2018;
- in `docs/methodology-conflicts.md`: ATBRTH-1, DPTCOV-1, PHYSPC-1,
  FAMPLN-1;
- in `docs/researcher-guide.md`: 91.5 %, 95.42;
- in `tests/golden/test_golden_who_real_data.py`: about a dozen real
  values asserted in the opt-in test.

### Draft letter to WHO

To be sent by the project owner through WHO's permissions and licensing
channel (linked from the footer of the GHO pages):

> Subject: Redistribution of small GHO extracts as software test fixtures
>
> We maintain the Sustainable and Shared-Prosperity Policy Index (SSPI), a
> public research index. Our backend software reads three Global Health
> Observatory indicators through the GHO OData API
> (`https://ghoapi.azureedge.net/api/`): `MDG_0000000025` (births attended
> by skilled health personnel), `WHS4_100` (DTP3 immunization coverage
> among 1-year-olds, WUENIC) and `HWF_0001` (medical doctors per 10,000).
> To prove that our software reproduces our published methodology, we would
> like to include in our public code repository small unmodified extracts of
> these responses (200, 275 and 205 rows, about 0.4 MB in total) and test
> files derived from them, with attribution to WHO in the form your terms
> specify.
>
> 1. Which terms govern data obtained from the GHO OData API at
>    `ghoapi.azureedge.net`: the "Terms and conditions of use for WHO data
>    compilations, aggregations, evaluations and analyses" on www.who.int,
>    or the data.who.int terms (CC BY 4.0 with additional terms)? Does the
>    answer change for the successor API WHO has announced?
> 2. Does redistributing such unmodified extracts in a public software
>    repository, as test data for a non-commercial research index, fall
>    within the permitted use (including "public health purposes", if the
>    www.who.int terms apply)? A repository is publicly downloadable and
>    others may reuse it; does that affect the answer?
> 3. `MDG_0000000025`: each country row carries a `Comments` field naming
>    the survey or publication behind the value (national statistical
>    offices, DHS, UNICEF MICS). Are these rows "materials credited to
>    another source" excluded from WHO's licence, or are they covered as
>    part of WHO's compiled dataset? If excluded, whom should we ask, and
>    may we redistribute the rows with the `Comments` field removed (we
>    would otherwise not modify the data)?
> 4. `WHS4_100` (WUENIC): the estimates are produced jointly by WHO and
>    UNICEF. Does WHO's permission cover redistribution of the WUENIC
>    figures as served by the GHO, or is UNICEF's permission also needed?
> 5. What exact attribution do you require for each of the three
>    indicators, and should the contributing countries or survey programmes
>    be named individually?
> 6. Our test files also contain values computed from the extracts (scores
>    and filled-in series). Are such derived values subject to the same
>    conditions, or to the provision on modified data?

Record the reply, its date and its sender under `Resolution evidence:`
below.

### What each answer would change

None of the answers changes a score. They only decide what is distributed:

- **Redistribution permitted for an indicator.** Its real fixtures and
  golden files may be committed with the required attribution and added
  back to the default test run, beside the synthetic ones. The gate is
  unchanged either way.
- **Permitted for some indicators and not others** (for example DPTCOV and
  PHYSPC but not ATBRTH). Use real data for those, and synthetic data for
  the rest.
- **Not permitted.** The current state stays. Real-data parity remains an
  opt-in local check against the committed checksums.
- **Attribution requirements.** These go into the researcher guide, the
  fixture README and any published score files.

### Relevant files

- `src/sspi/ingestion/who.py`, `src/sspi/indicators/{atbrth,dptcov,physpc}.py`
- `tests/fixtures/who/README.md`, `tests/fixtures/who/build_synthetic.py`, `tests/fixtures/who/REAL_DATA.sha256`
- `tests/golden/generate_who_cases.py`, `tests/golden/test_golden_who.py`, `tests/golden/test_golden_who_real_data.py`, `tests/golden/who_real_data.py`
- `tests/db/test_healthcare_end_to_end.py`
- `docs/indicator-migration.md` (Healthcare section), `docs/researcher-guide.md` (Healthcare section)

Resolution evidence: none yet.

---

## GOV-2 — WEF Historical Competitiveness Data: governing licence, non-commercial use, redistribution of extracts and of the database, derived scores, attribution

Status: open

Classification: DATA-GOVERNANCE / LICENSING REVIEW (not a scoring-methodology decision)

Raised: 2026-10-19, during the Infrastructure migration (AQELEC).

> **DECISION: project owner, 2026-10-19**
>
> - Approve development of a reusable WEF historical workbook adapter, so
>   that `WEF_QUELEC` and AQELEC can be ingested and scored from the
>   original workbook.
> - Do not infer permission to distribute original WEF data. Use invented
>   data in the WEF layout for repository-distributable parity tests; keep
>   the original workbook for local and opt-in validation.
> - Do not treat this item as a scoring-methodology conflict, and do not
>   mark it resolved without the project owner's confirmation.

### The source

`WEF_QUELEC` is indicator `WEF.GCIHH.EOSQ064`, "Quality of electricity
supply, 1-7 (best)", from the *WEF Global Competitiveness Index - Historical
Dataset* (dataset provider: World Economic Forum; last updated 2023-07-17;
2007-2017, 152 economies). The legacy collector read it from a workbook the
World Bank hosts,
`https://thedocs.worldbank.org/en/doc/cf8eee7ff5029398f75e897b342e7320-0050122023/related/WEF-GCIHH.xlsx`
(SHA-256 `a0d2c7afc22c97036b7f3df07a96ec99d2be6e5a6424cb1217392250f3fe0451`,
3,476,362 bytes, verified 2026-10-19). Hosting on a World Bank server does
not make it World Bank data, and publication on a public page grants no
redistribution right by itself.

What the documents say:

- **The WEF Licence Terms** (www.weforum.org, "Last updated: January 5,
  2024"; read from the Internet Archive capture of 2026-09-28, because the
  live page refuses automated requests) cover the "Materials" on the WEF's
  websites, "including data". "Unless otherwise indicated, use of the
  Forum's Material is Licensed to you under the terms of Creative Commons
  Attribution-NonCommercial-NoDerivatives 4.0 International Public
  Licence". That means sharing only for non-commercial purposes, with
  attribution, and without distributing modifications. Commercial use needs
  the Forum's prior written permission.
- **The workbook itself** carries the same terms. Its "Dataset Metadata"
  sheet has a "Legal Text" field: "Under the CCPL license, Visitors may
  copy, distribute and transmit the Articles, in any medium or format
  provided the work is properly attributed to the author and the World
  Economic Forum, that any such use is for non-commercial purposes and it is
  not altered, transformed or built upon." Its "Legal Link" is
  `https://www.weforum.org/about/terms-of-use`. So the terms travel with the
  file. The World Bank page that hosts it states no other licence that has
  been found.
- **CC BY-NC-ND 4.0** (Section 2(a)(1)) licenses users to "reproduce and
  Share the Licensed Material, in whole or in part, for NonCommercial
  purposes only; and produce and reproduce, but not Share, Adapted Material
  for NonCommercial purposes only".

### Questions for the research team

1. **Which terms govern the World Bank-hosted workbook?** Both documents
   point to CC BY-NC-ND 4.0. Confirm that nothing else applies to the copy
   at `thedocs.worldbank.org`, such as World Bank terms for the page or a
   different WEF licence for the GCI historical dataset.
2. **Is SSPI's use non-commercial?** The licence permits copying the
   workbook, and producing adapted material, only for non-commercial
   purposes. Ingesting it and computing AQELEC scores locally is the
   production of adapted material. If any SSPI use is commercial, or funded
   in a way that could count as commercial, the Forum's written permission
   is needed first.
3. **May extracts be published as test fixtures?** These would be small
   unmodified row subsets of the workbook, in the public repository. The
   licence permits sharing the material "in whole or in part" for
   non-commercial purposes. Whether a row subset converted to another file
   is "in part" or an adaptation is not established.
4. **May the database be redistributed?** That covers a PostgreSQL dump,
   an API or a published data file containing `WEF_QUELEC` observations,
   unmodified values or not.
5. **Are AQELEC scores adapted material that may not be shared?** Each
   score combines a WEF value, rescaled to 0-1, with World Bank data. Under
   the "NoDerivatives" term, sharing adapted material is not licensed.
   Whether a published index score counts as adapted material in the
   copyright sense, and whether publishing SSPI scores built on it needs
   permission, is not established.
6. **What attribution is required?** The workbook asks for attribution "to
   the author and the World Economic Forum". Should it name the Global
   Competitiveness Report, the dataset title and edition, and the World Bank
   as host? Where must it appear: repository, published scores, researcher
   guide?
7. **Should permission be requested?** The Forum's terms direct requests
   for permission to its contact address. A request would cover public or
   commercial use, redistributing extracts and publishing derived scores.

### Current state of the repository

**Production.**
- `WEF_QUELEC` is ingested from the pinned original workbook by
  `src/sspi/ingestion/wef.py`. A workbook with other bytes is refused.
- Each observation records the workbook, its edition, address and SHA-256
  in its provenance.
- AQELEC is scored by the legacy formula.
- The researcher guide asks users not to publish WEF values or AQELEC
  scores until this item is answered.

**Distributable automated tests use invented data.**
- `tests/fixtures/wef/WEF-GCIHH_synthetic.xlsx` is written by
  `tests/fixtures/wef/build_synthetic.py`. It has the workbook's layout and
  invented values, and its metadata sheets say so.
- The golden files `wef_quelec_synthetic_cases.json` and
  `aqelec_synthetic_cases.json` were generated from it by the pinned legacy
  code (`76f842b08e551dfa8fb9563e4c812be086654ba6`).
- `tests/golden/test_golden_wef.py` holds the new backend to exact parity.
- The World Bank access sample `EG.ELC.ACCS.ZS_sample.json` is real World
  Bank data (WDI, CC BY 4.0), as for the other World Bank fixtures.

**The original workbook is kept for local and opt-in validation and is
not committed.** It lives in the git-ignored `local-data/wef/` with:
- the full World Bank response it was validated with;
- the legacy output on both.

All are pinned by the committed `tests/fixtures/wef/REAL_DATA.sha256`.
`SSPI_WEF_REAL_DATA=local-data/wef` runs `tests/golden/test_golden_wef_real_data.py`
(marker `wef_real_data`). `tests/golden/test_golden_wef.py` fails if a file
pinned by the manifest appears under `tests/`.

**Still quoted in the repository, for the research team to confirm.** A few
individual figures computed from the original workbook appear in the
migration notes (`docs/indicator-migration.md`): coverage counts, three
AQELEC scores for Malaysia, Austria and the United States, and SHA-256
digests of the records.

### What each answer would change

None of the answers changes a score or the parity gate:

- **Commercial use, or no permission to adapt:** stop ingesting the
  original workbook (`WEF_QUELEC` would join the unavailable sources) until
  permission is obtained. AQELEC would then stop running live.
- **Extracts may be redistributed:** original-workbook fixtures and golden
  files could be committed beside the synthetic ones, with attribution.
- **Derived scores may not be shared:** AQELEC scores stay out of any
  published output until permission is obtained.
- **Attribution requirements:** these go into the researcher guide, the
  fixture README and any published output.

### Relevant files

- `src/sspi/ingestion/wef.py`, `src/sspi/indicators/aqelec.py`, `src/sspi/metadata/data/datasets/WEF_QUELEC.yaml`
- `tests/fixtures/wef/README.md`, `tests/fixtures/wef/build_synthetic.py`, `tests/fixtures/wef/REAL_DATA.sha256`
- `tests/golden/generate_wef_cases.py`, `tests/golden/test_golden_wef.py`, `tests/golden/test_golden_wef_real_data.py`, `tests/golden/wef_real_data.py`
- `docs/indicator-migration.md` (Infrastructure section), `docs/researcher-guide.md` (Infrastructure section), `docs/methodology-conflicts.md` (AQELEC-1)

Resolution evidence: none yet.
