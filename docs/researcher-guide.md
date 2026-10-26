# Researcher guide

This page assumes [setup](setup.md) is done: the package is installed,
`DATABASE_URL` is configured and `alembic upgrade head` has run.

## The one idea to keep in mind

Data moves through four stages. Each is a separate, explicit call, and
nothing happens unless you ask for it:

| Stage | What it is | How it gets there |
|---|---|---|
| raw source data | what a source API returns, for example UN SDG pivot rows | fetched by `ingest()`, never stored |
| canonical observations | one value per dataset, country and year, as the source reported it, in PostgreSQL | written by `ingest()` |
| imputed observations | values filled in for missing country-years, in memory only | created inside `run()` |
| indicator scores | one score per indicator, country and year, after goalposting/scoring, in PostgreSQL | written by `run()` |

`query()` reads canonical observations and indicator scores from PostgreSQL
and gives you a DataFrame. It does not fetch, impute, or compute.

**For ordinary analysis you only call `query()`.** You do not need to ingest
or run anything each time. Call `ingest()` only when you deliberately want
fresh source data, and `run()` only when you want indicator scores recomputed
from the observations currently stored.

## Creating the entry point

```python
from sspi import SSPI

sspi = SSPI()
```

`SSPI()` is cheap. It opens no connection and reads no configuration until
the first call that needs the database. Metadata lookups work without a
database at all.

Optional cleanup: `sspi.close()` releases the connection pool, and the
context-manager form does the same on exit. Neither is required in a
notebook; the connection is released when the kernel stops.

```python
with SSPI() as sspi:            # optional pattern for scripts
    df = sspi.query(indicators=["BIODIV"])
```

To point at a specific database without touching `.env`, pass a URL:
`SSPI(database="postgresql+psycopg://user:pass@host:5432/dbname")`.

## Querying datasets: canonical observations

```python
marine = sspi.query(
    datasets=["UNSDG_MARINE"],       # one or more dataset codes
    countries=["MYS", "USA"],        # ISO3 codes, or None for every country
    years=(2010, 2023),              # inclusive range, or None for every year
)
```

```
   dataset_code country_code  year     value     unit
0  UNSDG_MARINE          MYS  2010  19.70109  PERCENT
1  UNSDG_MARINE          MYS  2011  19.70109  PERCENT
...
```

Columns and dtypes are always the same: `dataset_code` and `country_code`
and `unit` are pandas `string`, `year` is `int64`, `value` is `float64`.
Rows are sorted by dataset code, country code, year. A query that matches
nothing returns an empty frame with exactly these columns and dtypes.

These are **canonical observations**: what the source reported, before any
imputation. Country-years the source did not report are simply absent. For
example, Austria has no marine series at the UN source, so
`sspi.query(datasets=["UNSDG_MARINE"], countries=["AUT"])` is empty even
after BIODIV has been computed with an imputed marine value for Austria.
Imputed observations are never stored as observations; they exist only inside
`run()` and, afterwards, embedded in the scores they produced (see
`include_inputs` below).

### Pre-imputation analysis

Because dataset queries return pre-imputation data, they are the right input
for any analysis of source coverage, gaps or raw levels:

```python
df = sspi.query(datasets=["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"], years=(2000, 2023))
coverage = df.pivot_table(index="country_code", columns="dataset_code", values="year", aggfunc="count")
```

### The DataFrame is a copy

The frame is built from the rows read at that moment. Editing it, adding
columns, dropping rows or overwriting values changes nothing in PostgreSQL.
There is no "save" path from a DataFrame. Only `ingest()` writes
observations, and only `run()` writes scores.

```python
df.loc[df["country_code"] == "MYS", "value"] = 0      # affects df only
sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"])  # still 19.70109
```

### Provenance

By default the frame has no source details. Ask for them with
`include_provenance=True`, which adds one `provenance` column holding a
dict per row:

```python
df = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2020, 2020), include_provenance=True)
df["provenance"][0]
```

```
{'source_organization': 'UNSDG', 'source_indicator': '14.5.1', 'source_series': 'ER_MRN_MPA',
 'source_geo_area_code': '458', 'source_geo_area_name': 'Malaysia', 'nature': 'C', 'observation_status': 'A'}
```

The keys depend on the source and are not flattened into columns, so the
default schema stays stable.

## Querying indicators: indicator scores

```python
biodiv = sspi.query(
    indicators=["BIODIV"],
    countries=["MYS", "AUT"],
    years=(2018, 2023),
)
```

```
   indicator_code country_code  year     score   unit  imputed
0          BIODIV          AUT  2018  0.585748  Index     True
1          BIODIV          AUT  2019  0.585856  Index     True
...
6          BIODIV          MYS  2018  0.297287  Index    False
...
```

`score` is `float64` in 0 to 1, `imputed` is `bool`, the rest as for
datasets. `imputed` is `True` when at least one input to that score was an
imputed observation; a score built entirely from canonical observations is
`False`. The flag is derived from the stored inputs and verified on every
read, so it cannot drift from the data.

For BIODIV, Malaysia has all three source series, so its scores are observed.
Austria has no marine series, so its marine input is imputed and every
Austrian BIODIV score is flagged `True`.

### Score inputs

`include_inputs=True` adds an `inputs` column with a tuple of small dicts,
one per input observation, showing the value used and whether it was
imputed. `include_provenance=True` adds a `provenance` column with the
score's own derivation record, which is `{}` for every score computed
directly from its inputs. DEFRST is the one indicator whose imputation
works on scores rather than inputs: its imputed rows have no imputed inputs
and instead carry a provenance such as
`{'imputed': True, 'imputation_method': 'Forward Extrapolation', 'source_year': 2022, 'imputation_distance': 1}`
or `{'imputed': True, 'imputation_method': 'ImputeReferenceClassAverage', 'reference_score_count': 184, ...}`
(the latter with an empty `inputs` tuple).

```python
df = sspi.query(indicators=["BIODIV"], countries=["AUT"], years=(2020, 2020), include_inputs=True)
df["inputs"][0]
```

```
({'dataset_code': 'UNSDG_MARINE', 'value': 36.56867346153846, 'unit': 'PERCENT',
  'imputed': True, 'imputation_method': 'ImputeReferenceClassAverage'},
 {'dataset_code': 'UNSDG_TERRST', 'value': 67.89465, 'unit': 'PERCENT', 'imputed': False, 'imputation_method': None},
 {'dataset_code': 'UNSDG_FRSHWT', 'value': 71.29881, 'unit': 'PERCENT', 'imputed': False, 'imputation_method': None})
```

This is the only place imputed observations are visible.

### Rules that apply to every query

- Pass exactly one of `datasets=[...]` or `indicators=[...]`. Observations
  and scores never share a frame.
- `countries=None` and `years=None` mean no restriction. An empty list is an
  error, not "everything".
- Dataset and indicator codes are checked against the metadata catalog;
  an unknown code raises `UnknownCodeError` before anything is read.
- Country codes must be three uppercase letters. A well-formed code with no
  rows gives an empty frame.
- Any indicator in the catalog can be queried, even one that has never been
  computed; you get an empty frame.

Filtering by a country group is done by passing its members:

```python
sspi.query(indicators=["BIODIV"], countries=sspi.country_group("SSPI67").members, years=(2000, 2023))
```

## Refreshing data: `ingest()`

`ingest()` fetches raw source data from the source API, converts it into
canonical observations and replaces the stored series for each requested
dataset. It needs internet access.

```python
result = sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"])
result.datasets                # ('UNSDG_MARINE', 'UNSDG_TERRST', 'UNSDG_FRSHWT')
result.observations_written    # 312
result.counts                  # {'UNSDG_MARINE': 104, 'UNSDG_TERRST': 104, 'UNSDG_FRSHWT': 104}
result.source_fetches          # ('14.5.1', '15.1.2')
result.per_dataset[0]          # rows written, skipped source areas (regional aggregates), missing values
```

Accepted forms are a single code, a list, or a tuple. Order is preserved.

What a refresh means:

- After it succeeds, the stored series for each requested dataset equals the
  newly fetched source series exactly. Rows the source no longer reports are
  gone.
- Datasets that share a source query, such as `UNSDG_TERRST` and
  `UNSDG_FRSHWT` from SDG 15.1.2, are fetched once.
- Everything is fetched and converted first; the requested datasets are then
  written together. If anything fails, nothing is written for any of them.
- **Ingestion does not recompute scores.** After
  `sspi.ingest("UNSDG_MARINE")`, stored BIODIV scores still reflect the
  previous observations until you call `sspi.run("BIODIV")`. This is
  deliberate: refreshing data and changing results are two decisions.

Requests fail before any network or database use if a code is unknown
(`UnknownCodeError`), known but not yet ingestible (`NotIngestibleError`),
or malformed such as an empty list or a duplicate code
(`IngestionRequestError`).

## Recomputing scores: `run()`

`run()` reads the canonical observations currently stored for an indicator's
datasets, scores every complete country-year, and replaces the indicator's
stored scores. For an indicator that has imputation (BIODIV), it also
imputes missing country-years for the SSPI67 group and scores those.

```python
result = sspi.run("BIODIV")
result.written                 # score rows persisted, e.g. 1590
len(result.observed_scores)    # scores with no imputed input
len(result.imputed_scores)     # scores with at least one imputed input
result.unscored                # country-years that stayed incomplete even after imputation
sspi.executable_indicators()   # ('BIODIV', 'REDLST', 'CHMPOL', 'WATMAN', 'NITROG', 'DEFRST', 'CARBON', 'ISHRAT', 'GINIPT', 'EMPLOY', 'COLBAR', 'ALTNRG', 'NRGINT', 'AIRPOL', 'BEEFMK', 'COALPW', 'GTRANS')
```

Not every indicator imputes. REDLST has no imputation: its score is
`goalpost(UNSDG_REDLST, 0, 1)` for every country-year the source reports,
a missing observation produces no score, and every REDLST row has
`imputed` equal to `False`.

```python
sspi.ingest("UNSDG_REDLST")
sspi.run("REDLST")
sspi.query(indicators=["REDLST"], countries=["MYS", "AUT"], years=(2018, 2023))
```

```
   indicator_code country_code  year    score   unit  imputed
0          REDLST          AUT  2018  0.95597  Index    False
...
6          REDLST          MYS  2018  0.83317  Index    False
...
```

Datasets derived from another dataset are ingested with their base in one
call, which downloads the source once:

```python
sspi.ingest(["UNFAO_FRSTLV", "UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_CRBNAV"])  # one FAOSTAT bulk download
sspi.run("DEFRST")
sspi.run("CARBON")
sspi.ingest("EPI_NITROG")                                                       # one EPI archive download
sspi.run("NITROG")
```

One indicator depends on another's scores. GINIPT fills countries that have
no Gini data with a prediction from their ISHRAT scores, so ISHRAT must be
run first. `run("GINIPT")` never runs ISHRAT for you; if ISHRAT has no
scores it stops with a `ScoreDependencyError` and writes nothing. If you
rerun ISHRAT later, rerun GINIPT as well.

```python
sspi.ingest(["WID_NINCSH_PRETAX_P90P100", "WID_NINCSH_PRETAX_P0P50"])  # one WID bulk download (about 900 MB)
sspi.run("ISHRAT")
sspi.ingest("WB_GINIPT")                                               # World Bank API
sspi.run("GINIPT")
```

The Worker Engagement category (`WEN`) has two indicators, `EMPLOY` and
`COLBAR`. They read the ILO's statistics API, one small request each, and do
not depend on each other:

```python
sspi.ingest(["ILO_EMPLOY_TO_POP", "ILO_COLBAR"])                       # ILOSTAT SDMX API, two requests
sspi.run("EMPLOY")
sspi.run("COLBAR")
```

The Energy category (`NRG`) has three indicators, `ALTNRG`, `NRGINT` and
`AIRPOL`. They do not depend on each other. `ALTNRG` reads seven datasets
from one International Energy Agency request; ingest all seven before
running it. The other two read the UN SDG database, one request each:

```python
sspi.ingest([
    "IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP",
    "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL",                         # IEA TESbySource, one request
    "UNSDG_NRGINT", "UNSDG_AIRPOL",                                    # UN SDG API, indicators 7.3.1 and 11.6.2
])
sspi.run("ALTNRG")
sspi.run("NRGINT")
sspi.run("AIRPOL")

energy = sspi.query(
    indicators=["ALTNRG", "NRGINT", "AIRPOL"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)
```

The Greenhouse Gases category (`GHG`) has three indicators, `BEEFMK`,
`COALPW` and `GTRANS`. They do not depend on each other or on any other
indicator's scores, but they need eleven datasets between them:

| Indicator | Datasets it reads |
|---|---|
| `BEEFMK` | `UNFAO_BFPROD`, `UNFAO_BFCONS`, `WB_POPULN` |
| `COALPW` | `IEA_TLCOAL`, `IEA_NATGAS`, `IEA_NCLEAR`, `IEA_HYDROP`, `IEA_GEOPWR`, `IEA_BIOWAS`, `IEA_FSLOIL` (the same seven as `ALTNRG`) |
| `GTRANS` | `IEA_TCO2EM`, `WB_POPULN` |

Ingest all eleven before running. COALPW does not complain if one of its
seven datasets is missing: like ALTNRG, it treats that fuel as zero for every
SSPI67 country and stores the result as imputed. BEEFMK and GTRANS simply
score nothing without their inputs. From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    # BEEFMK
    "UNFAO_BFPROD", "UNFAO_BFCONS",                                    # FAOSTAT Food Balances bulk file, one download
    "WB_POPULN",                                                       # World Bank Indicators API, SP.POP.TOTL (GTRANS too)
    # COALPW
    "IEA_TLCOAL", "IEA_NATGAS", "IEA_NCLEAR", "IEA_HYDROP",
    "IEA_GEOPWR", "IEA_BIOWAS", "IEA_FSLOIL",                         # IEA TESbySource, one request
    # GTRANS
    "IEA_TCO2EM",                                                      # IEA CO2BySector, one request
])

sspi.run("BEEFMK")
sspi.run("COALPW")
sspi.run("GTRANS")

ghg = sspi.query(
    indicators=["BEEFMK", "COALPW", "GTRANS"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(ghg)
```

The ingest makes four downloads (one FAOSTAT file, one World Bank request,
two IEA requests). The query returns the three leaf indicators only; no
Greenhouse Gases category score is computed.

The Waste category (`WST`) is `MSWGEN`, `RECYCL` and `STCONS` (EWASTE, in
some older material, is not a current indicator). **There is no runnable
Waste workflow.** `MSWGEN` is executable and reproduces the legacy scores
exactly, but its only input, `EPI_MSWGEN` (the 2024 EPI waste-per-capita
score), has no live source: the archive is no longer served and the current
EPI edition has no such series. `sspi.ingest(["EPI_MSWGEN"])` raises
`SourceUnavailableError` and fetches nothing, so on a fresh database
`sspi.run("MSWGEN")` scores nothing. Note also that the legacy formula
scores more waste *higher* (MSWGEN-1 in
[methodology-conflicts.md](methodology-conflicts.md)). `RECYCL` and `STCONS`
are not executable yet: both wait on a source decision (What a Waste and the
Global Footprint Network); see
[indicator-migration.md](indicator-migration.md).

The Education category (`EDU`) has four leaf indicators, all executable:
`ENRPRI`, `ENRSEC`, `PUPTCH` and `YRSEDU`. They read:

| Indicator | Datasets |
|---|---|
| `ENRPRI` | `UIS_ENRPRI` (UNESCO Institute for Statistics, `NERT.1.CP`, total net enrolment rate, primary, both sexes, %) |
| `ENRSEC` | `UIS_ENRSEC` (UNESCO Institute for Statistics, `NERT.2.CP`, total net enrolment rate, lower secondary, both sexes, %) |
| `PUPTCH` | `WB_PUPTCH` (World Bank Indicators API, `SE.PRM.ENRL.TC.ZS`, pupils per teacher in primary school) |
| `YRSEDU` | `UIS_YRSEDU` (UNESCO Institute for Statistics, `YEARS.FC.COMP.1T3`, years of compulsory primary and secondary education in law) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "UIS_ENRPRI",   # UIS Data API, NERT.1.CP, current published release
    "UIS_ENRSEC",   # UIS Data API, NERT.2.CP, same release
    "WB_PUPTCH",    # World Bank Indicators API, SE.PRM.ENRL.TC.ZS
    "UIS_YRSEDU",   # UIS Data API, YEARS.FC.COMP.1T3, same release
])

sspi.run("ENRPRI")
sspi.run("ENRSEC")
sspi.run("PUPTCH")
sspi.run("YRSEDU")

education = sspi.query(
    indicators=["ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(education)
```

The query returns the four leaf indicators only; no Education category
score is computed. Things to know:

- UIS publishes its database in releases that revise past values. By
  default `ingest` reads the release UIS currently publishes and records its
  identifier on every observation (`provenance["source_version"]`). To read
  a specific release, pass a client:
  `sspi.ingest(["UIS_ENRPRI", "UIS_ENRSEC", "UIS_YRSEDU"], client={"UIS": UISClient(version="20260507-91260335")})`
  (`from sspi.ingestion import UISClient`). A new release can change scores
  although the methodology is unchanged.
- `ENRPRI`, `ENRSEC` and `PUPTCH` carry each country's last value forward
  to 2023, however old: China's last primary enrolment value is from 1997,
  and the World Bank pupil–teacher series stops in 2019 (PUPTCH-1 in
  [methodology-conflicts.md](methodology-conflicts.md)). Check `imputed`
  and the input provenance before reading recent years.
- `ENRSEC` gives China and Nigeria, which have no lower-secondary data, the
  mean of every value of every country and year for 2000–2023 (ENRSEC-1).
  If either country ever has data, `sspi.run("ENRSEC")` raises
  `ImputationError` and writes nothing until the methodology team decides.
- Without its dataset, `sspi.run("ENRPRI")`, `sspi.run("PUPTCH")` and
  `sspi.run("YRSEDU")` score nothing; `sspi.run("ENRSEC")` raises `ImputationError` (the China and
  Nigeria mean has nothing to average), as the legacy route did.
- `YRSEDU` never sees a 0. UIS reports 0 years where a country had no
  compulsory schooling in law, but the legacy cleaner drops every zero, so
  the years before a country's law take its first later value (India
  2000–2008 scores as 8 years, not 0) and a 0 after an earlier value leaves
  no score at all (YRSEDU-1). It is only extrapolated backward to 2000:
  nothing is carried forward and gaps are not interpolated.
- Fewer pupils per teacher score higher (40 scores 0, 9 scores 1); enrolment
  scores 0 at 80 % (primary) or 70 % (lower secondary) and 1 at 100 %;
  compulsory education scores 0 at 6 years or fewer and 1 at 12 or more.

The Tax category (`TAX`) has three leaf indicators, all executable:
`CRPTAX`, `TAXREV` and `TXRDST`. They read:

| Indicator | Datasets |
|---|---|
| `CRPTAX` | `TF_CRPTAX` (Tax Foundation worldwide corporate tax rates, January 2025 edition, `rates_final.csv`, combined central and subnational statutory corporate income tax rate, %) |
| `TAXREV` | `WB_TAXREV` (World Bank Indicators API, `GC.TAX.TOTL.GD.ZS`, central-government tax revenue, % of GDP) |
| `TXRDST` | `WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50`, `WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100`, `WID_NINCSH_PRETAX_P0P50`, `WID_NINCSH_PRETAX_P90P100` (World Inequality Database bulk archive, post-tax `sdiincj992` and pre-tax `sptincj992` national income shares of the bottom 50 % and top 10 %, equal-split adults) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "TF_CRPTAX",                              # Tax Foundation rates_final.csv, January 2025 edition
    "WB_TAXREV",                              # World Bank Indicators API, GC.TAX.TOTL.GD.ZS
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50",    # WID bulk archive (one download for all four)
    "WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100",
    "WID_NINCSH_PRETAX_P0P50",
    "WID_NINCSH_PRETAX_P90P100",
])

sspi.run("CRPTAX")
sspi.run("TAXREV")
sspi.run("TXRDST")

taxes = sspi.query(
    indicators=["CRPTAX", "TAXREV", "TXRDST"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(taxes)
```

The query returns the three leaf indicators only; no Tax category score is
computed. Things to know:

- `CRPTAX` reads exactly the Tax Foundation's January 2025 file, the one the
  old backend used; no newer edition is read. The download is checked
  against that file's SHA-256: if the published file ever changes,
  `sspi.ingest(["TF_CRPTAX"])` raises `SourceResponseError` and stores
  nothing. Each observation records the edition, address and checksum
  (`provenance["source_edition"]`, `["source_url"]`, `["source_sha256"]`).
  The rate is the *combined* statutory rate (central plus average
  subnational); the 2018 static SSPI used central-government rates for some
  countries, for example 15 % for Germany (CRPTAX-1 in
  [methodology-conflicts.md](methodology-conflicts.md)). A higher rate scores
  higher (0 % scores 0, 40 % or more scores 1); a reported 0 % is kept and
  scores 0. Gaps are interpolated and late series carried back to 2000, but
  nothing is carried forward: the file ends in 2024. Every area in the file
  is kept, territories included.
- `TAXREV` is *central-government* tax revenue (TAXREV-3); it carries each
  country's last value forward to 2023 however old (Japan's last value is
  from 1993) and interpolates gaps. Vietnam, Nigeria, Venezuela and Algeria,
  which have no data, get the mean of every value of every country and year
  for 2000–2023 (TAXREV-1); if one of them ever has data,
  `sspi.run("TAXREV")` raises `ImputationError` and writes nothing until the
  methodology team decides. Pakistan has no data and no TAXREV score
  (TAXREV-2). Without its dataset, `sspi.run("TAXREV")` raises
  `ImputationError` (the mean has nothing to average), as the legacy route did.
- `TXRDST` is the percentage change of the bottom-50 % / top-10 % income
  share ratio from pre-tax to post-tax national income, scored −10 → 100.
  Post-tax national income includes transfers and public spending, so it
  measures tax-and-transfer redistribution (TXRDST-2). It reads the four
  share datasets directly, not ISHRAT or GINIPT scores, and imputes nothing:
  a country-year missing any of the four shares has no score. The pre-tax
  shares are the ones ISHRAT reads.
- Higher tax revenue scores higher (0 % of GDP scores 0, 50 % scores 1).

The Worker Wellbeing category (`WWB`) has four leaf indicators: `UNEMPB`,
`MATERN`, `FATINJ` and `SENIOR`. Two are executable, `UNEMPB` and `FATINJ`;
`MATERN` and `SENIOR` cannot be run yet (see below). They read:

| Indicator | Datasets |
|---|---|
| `UNEMPB` | `UNSDG_BENFTS_UNEMP` (UN SDG API, indicator 1.3.1, series `SI_COV_UEMP`, both sexes: share of unemployed people receiving an unemployment cash benefit, %) |
| `FATINJ` | `ILO_FATINJ` (ILOSTAT SDMX API, `DF_SDG_F881_SEX_MIG_RT`, both sexes, all migrant statuses: fatal occupational injuries per 100,000 workers) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "UNSDG_BENFTS_UNEMP",   # UN SDG API, indicator 1.3.1 (one request, several pages)
    "ILO_FATINJ",           # ILOSTAT SDMX API, DF_SDG_F881_SEX_MIG_RT (one request)
])

sspi.run("UNEMPB")
sspi.run("FATINJ")

wellbeing = sspi.query(
    indicators=["UNEMPB", "FATINJ"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(wellbeing)
```

The query returns the two executable leaf indicators only; no Worker
Wellbeing category score is computed, and the category is not complete
without MATERN and SENIOR. Things to know:

- The unemployment benefit indicator is `UNEMPB`. Older SSPI material (the
  2018 static data and some status files) calls it `UNEMPL`; there is no
  `UNEMPL` indicator or alias. `ILO_UNEMPL`, a legacy dataset no indicator
  reads, is not in the catalog.
- `UNEMPB` scores coverage from 0 % (score 0) to 100 % (score 1). A reported
  0 % is kept and scores 0: in many countries no unemployed person receives
  a cash benefit. Every value is an ILO estimate. Each country's series is
  carried back to 2000, forward to 2023 and interpolated in between; those
  rows have `imputed` equal to `True` and the `unit` column reads `Tax Rate`,
  a legacy mislabel kept so stored rows match it exactly (UNEMPB-1).
  Observed rows read `Benefits Coverage (%)`. Most countries report only a
  few years, so most scores are filled: Malaysia reports 2019 only, and that
  one value is its score for every year 2000–2023 (UNEMPB-3).
- Iceland has no unemployment benefit data and, by a fixed rule of the old
  backend, gets the mean of every value of every country and year for
  2000–2023 (UNEMPB-2). If Iceland ever has data, `sspi.run("UNEMPB")`
  raises `ImputationError` and writes nothing until the methodology team
  decides. Without its dataset, `sspi.run("UNEMPB")` raises
  `ImputationError` (the mean has nothing to average), as the legacy route
  did.
- `FATINJ` scores 25 or more deaths per 100,000 workers as 0 and none as 1;
  a reported 0 is kept and scores 1. Nothing is imputed: a country has a
  score only in the years the ILO reports, and most report one or two
  years (FATINJ-1). Today Austria reports only 2024, so the 2010–2023
  query above has no FATINJ row for it; Malaysia reports 2022 and the
  United States 2023. Thirteen SSPI67 countries have no FATINJ score at all.
  National figures count different things (reported or compensated
  injuries, all workers or insured persons only) and are not adjusted
  (FATINJ-2).
- `MATERN` (paid maternity leave, OECD) and `SENIOR` (senior wellbeing,
  OECD) cannot be ingested or run: the old backend had no working data path
  for either, and their OECD source is not supported. Asking for them raises
  a clear error (MATERN-1, SENIOR-1 to SENIOR-3).

The Healthcare category (`HLC`) has five leaf indicators: `ATBRTH`,
`DPTCOV`, `PHYSPC`, `FAMPLN` and `CSTUNT`. Four are executable, `CSTUNT`,
`ATBRTH`, `DPTCOV` and `PHYSPC`; `FAMPLN` cannot be run yet (see below).
They read:

| Indicator | Datasets |
|---|---|
| `CSTUNT` | `UNSDG_CSTUNT` (UN SDG API, indicator 2.2.1, series `SH_STA_STNT`, both sexes, under 5: share of children moderately or severely stunted, %) and `WB_GDP_PERCAP_CURPRICE_USD` (World Bank Indicators API, `NY.GDP.PCAP.CD`: GDP per capita in current US dollars, the predictor for countries without stunting data) |
| `ATBRTH` | `WHO_ATBRTH` (WHO Global Health Observatory, `MDG_0000000025`: births attended by skilled health personnel, % of live births) |
| `DPTCOV` | `WHO_DPTCOV` (WHO Global Health Observatory, `WHS4_100`: third-dose DTP coverage among 1-year-olds, WHO/UNICEF estimates, %) |
| `PHYSPC` | `WHO_PHYSPC` (WHO Global Health Observatory, `HWF_0001`: medical doctors per 10,000 population) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "UNSDG_CSTUNT",                 # UN SDG API, indicator 2.2.1 (one request, several pages)
    "WB_GDP_PERCAP_CURPRICE_USD",   # World Bank Indicators API, NY.GDP.PCAP.CD (one request)
    "WHO_ATBRTH",                   # WHO GHO OData API, MDG_0000000025 (one request)
    "WHO_DPTCOV",                   # WHO GHO OData API, WHS4_100 (one request)
    "WHO_PHYSPC",                   # WHO GHO OData API, HWF_0001 (one request)
])

sspi.run("CSTUNT")
sspi.run("ATBRTH")
sspi.run("DPTCOV")
sspi.run("PHYSPC")

healthcare = sspi.query(
    indicators=["CSTUNT", "ATBRTH", "DPTCOV", "PHYSPC"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(healthcare)
```

The query returns the four executable leaf indicators only; no Healthcare
category score is computed, and the category is not complete without
FAMPLN. Things to know:

- `CSTUNT` scores a stunting prevalence of 50 % or more as 0 and 0 % as 1.
  Every value is a modelled UN estimate (UNICEF, WHO and World Bank Joint
  Malnutrition Estimates), not a survey result, and is revised with each
  edition. Today every country the UN covers has every year 2000–2024, so
  their scores are all observed.
- A country with no stunting estimate at all (today 18 SSPI67 countries,
  Austria among them, and many small economies) gets a score predicted
  from GDP per capita: one straight line fitted across all countries and
  years with both. These rows have `imputed` equal to `True`, no inputs,
  and provenance naming the method, the GDP score and the fitted line.
  They cover every year the World Bank reports GDP, 1960 to 2025, not only
  2000–2023. Because GDP is in current dollars, the predicted prevalence
  falls as prices rise; eleven SSPI67 countries, Austria included, are
  predicted at a perfect 1.0 (no stunting) in 2023, above every measured
  country (CSTUNT-2). Run `CSTUNT` with `WB_GDP_PERCAP_CURPRICE_USD`
  ingested: without it, or without any stunting data, `sspi.run("CSTUNT")`
  raises `ImputationError` and writes nothing, as the legacy route failed.
- If the UN series ever has gaps, each country's series is carried back to
  2000, forward to 2023 and interpolated in between; those rows read
  `Coefficient` in the `unit` column, a legacy label (CSTUNT-1). Observed
  and predicted rows read `%`.
- The 2018 SSPI took its stunting figures from IHME, a different source
  (CSTUNT-3).
- `ATBRTH` scores 80 % of births attended or less as 0 and 100 % as 1.
  Each country's series is carried back to 2000, forward to 2023 and
  interpolated between survey years; those rows have `imputed` equal to
  `True`. Switzerland, the United Kingdom, the Netherlands, Belgium and
  Sweden have no WHO data and, by a fixed rule of the old backend, get the
  mean of every value of every country and year (91.5 % today, a score of
  0.575) for 2000–2023 (ATBRTH-1). If one of them ever has data,
  `sspi.run("ATBRTH")` raises `ImputationError` and writes nothing until
  the methodology team decides; without its dataset it raises too (the
  mean has nothing to average), as the legacy route did.
- `DPTCOV` scores third-dose DTP coverage from 75 % (score 0) to 100 %
  (score 1). The figures are WHO/UNICEF estimates for one-year-olds, capped
  at 99 %, so no score reaches 1; the description in the metadata speaks of
  a survey of children aged 12–23 months instead (DPTCOV-1). Nothing is
  imputed: a year without an estimate has no score.
- `PHYSPC` scores 0 doctors per 10,000 as 0 and 70 or more as 1, from
  1990 on; gaps are filled from each country's own series as for ATBRTH,
  with no fixed recipients. WHO's figures are scored as published: today
  Austria's 2018 value is 95.42 (about 52 in the neighbouring years), so
  its 2018 score is 1.0 (PHYSPC-1).
- The WHO source serves no editions and WHO revises past years (WUENIC
  every year, the workforce accounts with each update): re-ingesting can
  change historical values and scores. WHO has announced that this API will
  be replaced; if it stops answering, ingestion fails with a source error
  rather than switching to another service. The data are WHO's, ingested
  from the GHO and stored in your database as for every other source. Which
  WHO terms govern them, and whether extracts may be redistributed, is an
  open data-governance question (`docs/data-governance-review.md`, GOV-1);
  until it is answered the repository ships no WHO data, and its WHO test
  fixtures are synthetic. Credit WHO when you publish results from these
  datasets.
- `FAMPLN` (family planning) cannot be ingested or run: the old backend
  never produced a score for it (its formula names the wrong dataset), and
  its description, data and 2018 values describe different measures. Which
  measure it should be is a methodology decision (FAMPLN-1). Asking for
  `WHO_FAMPLN` or `FAMPLN` raises a clear error.

The Financial Sector category (`FIN`) has three leaf indicators: `FSTABL`,
`FDEPTH` and `PUBACC`. Two are executable, `FDEPTH` and `PUBACC`; `FSTABL`
cannot be run yet (see below). They read:

| Indicator | Datasets |
|---|---|
| `FDEPTH` | `WB_CREDIT` (World Bank Indicators API, `FS.AST.PRVT.GD.ZS`: domestic credit to the private sector, % of GDP) and `WB_DPOSIT` (World Bank Indicators API, Global Financial Development `GFDD.OI.02`: bank deposits, % of GDP) |
| `PUBACC` | `WB_PUBACC` (World Bank Indicators API, `FX.OWN.TOTL.ZS`: adults, ages 15+, with an account at a financial institution or a mobile-money service, %, from the Global Findex survey) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "WB_CREDIT",   # World Bank Indicators API, FS.AST.PRVT.GD.ZS (one request)
    "WB_DPOSIT",   # World Bank Indicators API, GFDD.OI.02 (one request)
    "WB_PUBACC",   # World Bank Indicators API, FX.OWN.TOTL.ZS (one request)
])

sspi.run("FDEPTH")
sspi.run("PUBACC")

results = sspi.query(
    indicators=["FDEPTH", "PUBACC"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(results)
```

The query returns the two executable leaf indicators only; no Financial Sector
category score is computed, and the category is not complete without
FSTABL. Things to know:

- `FDEPTH` is half credit and half deposits: credit scored from 0 % of GDP
  (0) to 200 % (1), deposits from 0 % to 100 %, each half on its own. Many
  countries' deposits exceed 100 % of GDP and score 1 on that half. The 2018
  SSPI used 0–190 % and 0–200 % (FDEPTH-2).
- A country-year needs both inputs to get an `FDEPTH` score. Nothing is
  imputed: the old backend's FDEPTH imputation never ran (it fails on every
  input), so the only FDEPTH scores it ever stored were observed ones, and
  that is what `run("FDEPTH")` stores too (FDEPTH-1). The deposit series
  comes from a World Bank database last updated in 2022, so there is no
  FDEPTH score after 2021, and none for the United Kingdom, which has no
  deposit series. The query above returns 2010–2021 for Malaysia and
  Austria and 2010–2020 for the United States.
- The deposit input is named "financial system deposits" in the metadata,
  but the series is deposits in banks only; the World Bank publishes a
  financial-system series separately (FDEPTH-3).
- `PUBACC` scores the share of adults with an account from 0 % (0) to 100 %
  (1). The source is a survey run in waves, so scores exist only for 2011,
  2014, 2017, 2021 and 2024 (2022 for a few countries); nothing is filled
  in between (PUBACC-1).
- Both read the World Bank Indicators API, which serves no editions: the
  World Bank revises past years, so re-ingesting can change historical
  values and scores. The World Bank publishes both databases under the
  Creative Commons Attribution 4.0 licence; credit the World Bank (and the
  IMF International Financial Statistics, the underlying source of the
  credit and deposit figures) when you publish results.
- `FSTABL` (nonperforming loans) cannot be ingested or run: the old backend
  never computed it, its IMF dataset was never defined, and a World Bank
  series added later was never wired to a score. Which source to use is a
  research decision (FSTABL-1). Asking for `IMF_FSTABL` or `FSTABL` raises a
  clear error.

The Infrastructure category (`INF`) has five leaf indicators: `AQELEC`,
`SANSRV`, `DRKWAT`, `INTRNT` and `TRNETW`. Three are executable, `AQELEC`,
`SANSRV` and `DRKWAT`; `INTRNT` and `TRNETW` cannot be run yet (see below).
They read:

| Indicator | Datasets |
|---|---|
| `AQELEC` | `WB_AVELEC` (World Bank Indicators API, `EG.ELC.ACCS.ZS`: access to electricity, % of population) and `WEF_QUELEC` (World Economic Forum workbook, `WEF.GCIHH.EOSQ064`: quality of electricity supply, executive survey score 1-7, 2007-2017) |
| `SANSRV` | `WB_SANSRV` (World Bank Indicators API, `SH.STA.BASS.ZS`: people using at least basic sanitation services, % of population, WHO/UNICEF JMP) |
| `DRKWAT` | `WB_DRKWAT` (World Bank Indicators API, `SH.H2O.SMDW.ZS`: people using safely managed drinking water services, % of population, WHO/UNICEF JMP) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "WB_AVELEC",   # World Bank Indicators API, EG.ELC.ACCS.ZS (one request)
    "WEF_QUELEC",  # WEF Global Competitiveness Index Historical Dataset workbook (one download, checksum-pinned)
    "WB_SANSRV",   # World Bank Indicators API, SH.STA.BASS.ZS (one request)
    "WB_DRKWAT",   # World Bank Indicators API, SH.H2O.SMDW.ZS (one request)
])

sspi.run("AQELEC")
sspi.run("SANSRV")
sspi.run("DRKWAT")

result = sspi.query(
    indicators=["AQELEC", "SANSRV", "DRKWAT"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(result)
```

The query returns the three executable leaf indicators only; no Infrastructure
category score is computed, and the category is not complete without
INTRNT and TRNETW. Things to know:

- `AQELEC` is half electricity access (0 % scores 0, 100 % scores 1) and
  half the World Economic Forum's executive-survey rating of the
  reliability of electricity supply (1 scores 0, 7 scores 1). A country-year
  needs both. The WEF series covers 2007–2017 only and nothing is imputed,
  so **there is no AQELEC score after 2017** (or before 2007): the query
  above returns AQELEC for 2010–2017 only. Today 711 of the 726 SSPI67
  member-years 2007–2017 are scored (never Iraq) (AQELEC-1).
- The WEF workbook is World Economic Forum data hosted by the World Bank,
  read from one pinned file: if its bytes ever change, ingestion stops with
  an error rather than reading another edition. Its terms (Creative Commons
  Attribution-NonCommercial-NoDerivatives 4.0) allow non-commercial use but
  not sharing modified material; whether `WEF_QUELEC` values or AQELEC
  scores may be published or redistributed is an open question (GOV-2,
  `docs/data-governance-review.md`). Until it is answered, do not publish
  them, and credit the World Economic Forum when you use them.
- `SANSRV` scores 50 % of the population or less with basic sanitation as 0
  and 100 % as 1. The 2018 SSPI scored the same series from 0 % (SANSRV-1).
  Each country's series is carried forward to 2023 and back to 2000; those
  rows have `imputed` equal to `True`. Gaps inside a series are not filled.
  Today only a few countries need it: Argentina's last value is 2016, so its
  2017–2023 scores repeat that year (SANSRV-2).
- `DRKWAT` scores the share using safely managed drinking water (an improved
  source on premises, available when needed and free from contamination)
  from 0 % to 100 %. Nothing is imputed: today nine SSPI67 members have no
  estimate at all (Argentina, Australia, China, Kenya, Saudi Arabia,
  Thailand, Türkiye, Uruguay, Venezuela) and the United States starts in
  2005, so they have no DRKWAT score for those years (DRKWAT-1).
- The sanitation and water series are modelled annual estimates from the
  WHO/UNICEF Joint Monitoring Programme, published by the World Bank, which
  serves no editions: the JMP revises past years with each release, so
  re-ingesting can change historical values and scores. Credit the WHO/UNICEF
  JMP and the World Bank when you publish results.
- `INTRNT` (internet access and quality) cannot be ingested or run: the old
  backend's route read two datasets the metadata does not list and averaged
  their raw values, which the old database refused to store, so it never
  produced a score (INTRNT-1).
- `TRNETW` (transport networks) cannot be ingested or run: the old backend
  had no implementation and no source for it (TRNETW-1).

The Public Safety category (`SAF`) has four leaf indicators, all
executable: `MURDER`, `CYBSEC`, `SECAPP` and `PRISON`. They read:

| Indicator | Datasets |
|---|---|
| `MURDER` | `WB_MURDER` (World Bank Indicators API, `VC.IHR.PSRC.P5`: intentional homicides per 100,000 people) |
| `CYBSEC` | `ITU_CYBSEC` (the SSPI's hand transcription of the ITU Global Cybersecurity Index scores, editions 2014, 2017, 2018, 2020 and 2024, read as a local file) |
| `SECAPP` | `FSI_SECAPP` (Fund for Peace, Fragile States Index workbooks 2006-2023, component C1 "Security Apparatus") |
| `PRISON` | `UNODC_PRIPOP` (UNODC data portal workbook "Prisons and prisoners", one pinned release: persons held in prisons per 100,000 population) |

`ITU_CYBSEC` is not downloaded: copy the transcription from the old
repository (`sspi-data-webapp`, `local/CYBSEC/gci-local-indicator-summary.csv`)
to `local-data/itu/gci-local-indicator-summary.csv` first; the file is
checked against its pinned SHA-256. Then, from a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "WB_MURDER",     # World Bank Indicators API, VC.IHR.PSRC.P5 (one request)
    "ITU_CYBSEC",    # local file local-data/itu/gci-local-indicator-summary.csv (checksum-pinned)
    "FSI_SECAPP",    # Fragile States Index, 18 annual workbooks (each checksum-pinned)
    "UNODC_PRIPOP",  # UNODC data portal, data_cts_prisons_and_prisoners.xlsx (one download, checksum-pinned)
])

sspi.run("MURDER")
sspi.run("CYBSEC")
sspi.run("SECAPP")
sspi.run("PRISON")

results = sspi.query(
    indicators=["MURDER", "CYBSEC", "SECAPP", "PRISON"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(results)
```

The query returns the four leaf indicators only; no Public Safety category
score is computed. Things to know:

- `MURDER` scores 20 or more homicides per 100,000 people as 0 and none as
  1. Each country's series is interpolated across gaps and carried forward
  to 2023 and back to 2000, however far the nearest observation is; those
  rows have `imputed` equal to `True`. Today Thailand's and Viet Nam's last
  values are 2011, so their 2012–2023 scores repeat that year, and Nigeria's
  first value (2016) is carried back to 2000 (MURDER-2). Gaps before 2000
  are interpolated too.
- The World Bank cleaner treats a reported **zero** as missing, so a year
  with no recorded homicide is filled in from its neighbours: today Iceland
  2006, Liechtenstein 2007 and 2009 and Malta 2006 (MURDER-1).
- `CYBSEC` scores the transcribed index from 0 to 1 **in the five edition
  years only** (2014, 2017, 2018, 2020, 2024); nothing is imputed, so the
  query above returns CYBSEC for 2014, 2017, 2018 and 2020. The 2020 and
  2024 editions were published on 0–100 and are divided by 100; the
  editions differ in method (CYBSEC-2). Five spellings the old name matcher
  could not place ("Cote d'Ivoire", "Macedonia", "Micronesia", "State of
  Palestine", "Vatican") are mapped to their ISO codes by an approved
  correction (CYBSEC-1). **Canada is not in the transcription**, so it has
  no CYBSEC score (CYBSEC-3). The licence terms are open (GOV-4).
- `SECAPP` scores the FSI's Security Apparatus component, 10 (worst) as 0
  and 0 as 1, **in the FSI edition years 2006–2023 only**; nothing is
  imputed and nothing exists before 2006 (SECAPP-2). It is component C1, not
  the overall FSI. The old backend never stored an FSI value; the approved
  adapter reads the official workbooks and repairs the country names the old
  matcher could not place, including North Korea, which it confused with
  South Korea (SECAPP-1). Israel's FSI unit changes in 2021, from "Israel and
  West Bank" to Israel alone, so its series breaks there (SECAPP-3). No
  licence for the FSI data has been found (GOV-5).
- `PRISON` scores 540 or more prisoners per 100,000 as 0 and 40 or fewer as
  1. Each series is carried to 2023 and 2000 and interpolated; 2024 values
  are scored but nothing is filled after 2023 (PRISON-3).
- The **United Kingdom** reports as three jurisdictions. Its value is their
  unweighted average in each year, over whichever of them reported: 118.4
  per 100,000 for 2022, where a population-weighted rate is 133.8, and for
  2023, which England and Wales has not reported, the average of Scotland
  and Northern Ireland alone (PRISON-1).
- **China** has no UNODC series. For every year 2000–2023 it gets the plain
  average of every value in the workbook, all countries and years (185.8
  per 100,000 today). If UNODC ever publishes Chinese figures,
  `run("PRISON")` stops with an error, as the old backend did (PRISON-2).
  Iraq reports mostly as two sub-national units, which are not combined;
  its only national value (2021) is carried over 2000–2023 (PRISON-4).
- The UNODC workbook, the FSI workbooks and the ITU transcription are each
  read as pinned files: if a file changes, ingestion stops with an error
  rather than reading another version. The address the old backend used for
  the UNODC workbook now redirects to the portal's home page. The UN's
  website terms grant only personal, non-commercial use without
  redistribution or derivative works; whether UNODC values or PRISON scores
  may be published is an open question (GOV-3). Do not publish CYBSEC,
  SECAPP or PRISON results until GOV-3 to GOV-5 are answered, and credit
  ITU, the Fund for Peace and UNODC when you use them.

The Rights category (`RTS`) has five leaf indicators: `RULELW`, `PUBSRV`,
`EDEMOC`, `UNCONV` and `GENDEQ`. Two of the five are migrated: only `RULELW`
and `EDEMOC` are executable, and Rights is not complete. They read:

| Indicator | Datasets |
|---|---|
| `RULELW` | `VDEM_RULELW` (V-Dem Country-Year Full+Others archive, version 13, column `v2x_rule`: rule of law index, 0–1) |
| `EDEMOC` | `VDEM_EDEMOC` (the same archive, column `v2x_polyarchy`: electoral democracy index, 0–1) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "VDEM_RULELW",  # V-Dem v13 archive V-Dem-CY-FullOthers_csv_v13.zip (one download for both, checksum-pinned)
    "VDEM_EDEMOC",
])

sspi.run("RULELW")
sspi.run("EDEMOC")

results = sspi.query(
    indicators=["RULELW", "EDEMOC"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(results)
```

The query returns the two leaf indicators only; no Rights category score is
computed. Things to know:

- Both scores are the V-Dem index itself (goalposts 0 and 1), the point
  estimate only: V-Dem's confidence bounds are not used.
- The archive is **V-Dem version 13** (March 2023), with data to 2022, the
  edition the old backend downloaded and the one kept for this migration; it
  is read as a pinned file and is never replaced by a newer edition. V-Dem re-estimates past years in every
  release, so the current edition (16, March 2026) gives different values
  for most years (RULELW-2, EDEMOC-2).
- Each country's latest value is carried forward to 2023, nothing is carried
  backward and no gap is filled: with version 13 every country's 2023 score
  repeats its 2022 value, and those rows have `imputed` equal to `True`. The
  old backend stored these carried scores among its observed scores, where
  its dashboards showed them as observed; storing them as imputed, once, with
  the 2022 value unchanged is an approved correction (RULELW-1, EDEMOC-1),
  and whether they should be imputed at all is open (RULELW-3, EDEMOC-3).
- Years 1991 to the year before the ingestion are kept, as the old cleaner
  did; with version 13 that is 1991–2022 whenever you ingest.
- Countries are V-Dem's own codes, including some that are not ISO
  countries (`XKX` Kosovo, `PSG` Palestine/Gaza, `PSE` Palestine/West Bank,
  `SML` Somaliland, `ZZB` Zanzibar).
- V-Dem states a CC BY-SA 4.0 licence today, but the version 13 archive
  states none; cite V-Dem when you use these values and do not publish the
  results until GOV-6 is answered.
- `PUBSRV` (quality of public services), `UNCONV` (UN conventions) and
  `GENDEQ` (gender equality) cannot be ingested or run: the old backend had
  no implementation for any of them, and each awaits methodology decisions
  (PUBSRV-1, UNCONV-1, GENDEQ-1).

The Global Role category (`GLB`) has four leaf indicators: `ARMEXP`,
`MILEXP`, `RDFUND` and `FORAID`. Three of the four are registered,
`ARMEXP`, `MILEXP` and `RDFUND`; `FORAID` is blocked, and
Global Role is not complete. They read:

| Indicator | Datasets |
|---|---|
| `ARMEXP` | `SIPRI_ARMEXP` (SIPRI Arms Transfers Database API: exports of major arms by supplier, millions of SIPRI trend-indicator values, 1990–2025) |
| `MILEXP` | `SIPRI_MILEXP` (SIPRI Military Expenditure Database, revised workbook `SIPRI-Milex-data-1949-2025_v1.2.xlsx`, sheet "Share of GDP", 1990–2024, percent of GDP) |
| `RDFUND` | `UNSDG_RDPGDP` (UN SDG 9.5.1, `GB_XPD_RSDV`: R&D expenditure, % of GDP), `UNSDG_NRSRCH` (UN SDG 9.5.2, `GB_POP_SCIERD`: researchers per million inhabitants) |

From a fresh, empty database:

```python
from sspi import SSPI

sspi = SSPI()

sspi.ingest([
    "SIPRI_MILEXP",  # SIPRI's revised workbook (one download, checksum-pinned)
    "SIPRI_ARMEXP",  # SIPRI Arms Transfers Database API (one request)
    "UNSDG_RDPGDP",  # UN SDG Global Database, indicator 9.5.1
    "UNSDG_NRSRCH",  # UN SDG Global Database, indicator 9.5.2
])

sspi.run("MILEXP")
sspi.run("ARMEXP")  # observed scores only (ARMEXP-2)
sspi.run("RDFUND")

results = sspi.query(
    indicators=["MILEXP", "ARMEXP", "RDFUND"],
    countries=["MYS", "AUT", "USA"],
    years=(2010, 2023),
)

print(results)
```

The query returns the leaf indicators only; no Global Role category score is
computed. Things to know:

- **`ARMEXP` has observed scores only.** The old impute route gives the
  United Arab Emirates, Bangladesh and Iraq the average of every exporter's
  every year, but the United Arab Emirates now exports, so the old backend
  refused all ARMEXP imputation and kept only observed scores. `run("ARMEXP")`
  does the same: it stores the observed scores and attempts no imputation
  (an approved treatment; the question is open, ARMEXP-2). Country-years
  without SIPRI data have no ARMEXP score; none is shown as zero.
- `ARMEXP` scores SIPRI trend-indicator values, a volume of weapons, not
  money, although its unit says `Expenditure` (ARMEXP-1); 500 million TIV or
  more scores 0. A country that never exported is not in SIPRI's table and
  gets no score (ARMEXP-3). SIPRI's "Brunei" and "Bosnia-Herzegovina", which
  the old backend dropped, are stored as BRN and BIH (ARMEXP-4).
- `RDFUND` is the mean of R&D spending scored 0–4% of GDP and researchers
  scored 0–5,000 per million. Each input is carried forward to 2023, back to
  2000 and interpolated; Peru, Bangladesh and Israel get the all-country
  average researcher count, Bangladesh also the average R&D share (RDFUND-1);
  an imputed score may pair one observed and one filled input (RDFUND-2). The
  R&D input is total spending, not higher-education spending (RDFUND-3).
- `MILEXP` scores military expenditure as a share of GDP, 0% scoring 1 and
  5% or more scoring 0 (the 2018 scores used 10%, MILEXP-3). It reads SIPRI's
  revised workbook of 27 April 2026, not the API the old backend read, which
  still serves withdrawn Belarus figures (MILEXP-4); the file is downloaded
  from sipri.org and refused if its checksum differs. To work offline, pass a
  local copy of the same file:
  `sspi.ingest(["SIPRI_MILEXP"], client={"SIPRI": SIPRIClient(local_workbook_directory="path/to/dir")})`
  (`from sspi.ingestion.sipri import SIPRIClient`). Each value takes the year
  of its own column and SIPRI's fractions are converted to percent; the old
  backend stored them 10 or 11 years late and left shares of 100% or more
  unscaled (MILEXP-1, MILEXP-2). Kuwait 1991 is 117% of GDP and scores 0.
  Costa Rica, Panama (from 2000) and Iceland publish 0 (no military
  expenditure) and score 1 as observed values; "..." stays missing.
  Each series is carried forward to 2023, back to 2000 and interpolated;
  Iceland gets a fixed 0 only for years without a published value (MILEXP-3,
  MILEXP-5).
- `FORAID` (foreign aid) cannot be ingested or run: the old route never runs
  (FORAID-1 to FORAID-3).
- SIPRI's terms allow non-commercial analytical use of less than 10 per cent
  of a data set with attribution; do not publish ARMEXP or MILEXP results
  until GOV-7 is answered, and credit SIPRI.

A run is a full replacement: stale scores, including imputed ones for
country-years that now have canonical data, disappear. Running twice on the
same observations gives the same rows. `run()` never fetches from a source
and never changes observations.

## Metadata without a database

```python
sspi.indicator("BIODIV")               # name, pillar, category, dataset dependencies, formula text
sspi.dataset("UNSDG_MARINE")           # name, unit, source organization and query
sspi.country("MYS")                    # name and group memberships
sspi.country_group("SSPI67").members   # tuple of ISO3 codes
sspi.metadata.indicators()             # all 57 catalog indicators
sspi.metadata.datasets()               # all documented datasets
```

## V1 support

| | Codes |
|---|---|
| Ingestible datasets | BIODIV: `UNSDG_MARINE`, `UNSDG_TERRST`, `UNSDG_FRSHWT`; REDLST: `UNSDG_REDLST`; CHMPOL: `UNSDG_STKHLM`, `UNSDG_MINMAT`, `UNSDG_MONTRL`, `UNSDG_BASELA`, `UNSDG_ROTDAM`; WATMAN inputs: `UNSDG_WTSTRS`, `UNSDG_WUSEFF`, `UNSDG_CWUEFF`; NITROG: `EPI_NITROG`; DEFRST: `UNFAO_FRSTLV`, `UNFAO_FRSTAV`; CARBON: `UNFAO_CRBNLV`, `UNFAO_CRBNAV`; ISHRAT: `WID_NINCSH_PRETAX_P90P100`, `WID_NINCSH_PRETAX_P0P50`; GINIPT: `WB_GINIPT`; EMPLOY: `ILO_EMPLOY_TO_POP`; COLBAR: `ILO_COLBAR`; ALTNRG: `IEA_TLCOAL`, `IEA_NATGAS`, `IEA_NCLEAR`, `IEA_HYDROP`, `IEA_GEOPWR`, `IEA_BIOWAS`, `IEA_FSLOIL`; NRGINT: `UNSDG_NRGINT`; AIRPOL: `UNSDG_AIRPOL`; BEEFMK: `UNFAO_BFPROD`, `UNFAO_BFCONS`, `WB_POPULN`; COALPW: the seven ALTNRG datasets; GTRANS: `IEA_TCO2EM`, `WB_POPULN`; PUPTCH: `WB_PUPTCH`; ENRPRI: `UIS_ENRPRI`; ENRSEC: `UIS_ENRSEC`; YRSEDU: `UIS_YRSEDU`; CRPTAX: `TF_CRPTAX`; TAXREV: `WB_TAXREV`; TXRDST: `WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50`, `WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100` and the two ISHRAT datasets; UNEMPB: `UNSDG_BENFTS_UNEMP`; FATINJ: `ILO_FATINJ`; CSTUNT: `UNSDG_CSTUNT`, `WB_GDP_PERCAP_CURPRICE_USD`; ATBRTH: `WHO_ATBRTH`; DPTCOV: `WHO_DPTCOV`; PHYSPC: `WHO_PHYSPC`; FDEPTH: `WB_CREDIT`, `WB_DPOSIT`; PUBACC: `WB_PUBACC`; SANSRV: `WB_SANSRV`; DRKWAT: `WB_DRKWAT`; AQELEC: `WB_AVELEC`, `WEF_QUELEC`; MURDER: `WB_MURDER`; CYBSEC: `ITU_CYBSEC` (local transcription, approved name correction, CYBSEC-1); SECAPP: `FSI_SECAPP`; PRISON: `UNODC_PRIPOP`; RULELW: `VDEM_RULELW`; EDEMOC: `VDEM_EDEMOC` (one V-Dem v13 archive); ARMEXP: `SIPRI_ARMEXP`; MILEXP: `SIPRI_MILEXP` (one pinned SIPRI workbook); RDFUND: `UNSDG_RDPGDP`, `UNSDG_NRSRCH` |
| Not ingestible: live source unavailable | MSWGEN: `EPI_MSWGEN` (historical parity only) |
| Executable indicators | `BIODIV`, `REDLST`, `CHMPOL`, `WATMAN`, `NITROG`, `ISHRAT`, `GINIPT` (run `ISHRAT` first), `EMPLOY`, `COLBAR`, `ALTNRG`, `NRGINT`, `AIRPOL`, `BEEFMK`, `COALPW`, `GTRANS`, `PUPTCH`, `ENRPRI`, `ENRSEC`, `YRSEDU`, `CRPTAX`, `TAXREV`, `TXRDST`, `UNEMPB`, `FATINJ`, `CSTUNT`, `ATBRTH`, `DPTCOV`, `PHYSPC`, `FDEPTH`, `PUBACC`, `SANSRV`, `DRKWAT`, `AQELEC`, `MURDER`, `CYBSEC`, `SECAPP`, `PRISON`, `RULELW`, `EDEMOC`, `RDFUND`, `ARMEXP` (observed scores only, ARMEXP-2), `MILEXP` live; `DEFRST`, `CARBON` (imputation recipients follow DEFRST-1 / CARBON-1, see below); `MSWGEN` (registered, but its input cannot be ingested) |
| Sources | UN SDG Global Database API; FAOSTAT bulk download (Land Use and Food Balances domains); Yale EPI 2026 indicator archive; World Inequality Database bulk archive; World Bank Indicators API; ILOSTAT SDMX API; IEA statistics endpoint (`TESbySource`, `CO2BySector`); UNESCO Institute for Statistics Data API; Tax Foundation corporate tax rate file (January 2025 edition only); WHO Global Health Observatory OData API; WEF Global Competitiveness Index Historical Dataset workbook (one pinned edition); UNODC data portal workbook (one pinned release); Fragile States Index annual workbooks 2006–2023 (each pinned); V-Dem Country-Year Full+Others archive (version 13, pinned); SIPRI Arms Transfers Database API; SIPRI Military Expenditure Database workbook (revised 2026-04-27, pinned); local source files (the ITU Global Cybersecurity Index transcription) |
| Queryable | any dataset or indicator in the catalog, returning whatever is stored |

## Known limitations

- Only the datasets above can be ingested and only the forty-five indicators
  above can be run; MSWGEN has nothing to run on unless its input is stored,
  and CYBSEC needs the transcription copied to `local-data/itu/`.
- Worker Wellbeing is incomplete: MATERN and SENIOR cannot be run (no
  working legacy data path, OECD source not supported), and no Worker
  Wellbeing category score is computed.
- Healthcare is incomplete: FAMPLN cannot be run (no score in the old
  backend, and its measure awaits a methodology decision). No Healthcare
  category score is computed.
- Financial Sector is incomplete: FSTABL cannot be run (no computation in
  the old backend, and its source awaits a research decision). FDEPTH is
  never imputed and stops in 2021; PUBACC exists only in survey years. No
  Financial Sector category score is computed.
- Infrastructure is incomplete: INTRNT (the old route never stored a score)
  and TRNETW (no implementation) cannot be run. AQELEC exists only for
  2007–2017, DRKWAT is never imputed, and the WEF data behind AQELEC may
  not be redistributed until GOV-2 is answered. No Infrastructure category
  score is computed.
- Public Safety is complete at leaf level (MURDER, CYBSEC, SECAPP, PRISON),
  with no category score. CYBSEC and SECAPP exist only in their source
  edition years; Canada has no CYBSEC; PRISON averages the United Kingdom's
  jurisdictions unweighted and gives China an all-country average; MURDER
  fills reported zeros. Publication of CYBSEC, SECAPP and PRISON awaits
  GOV-3 to GOV-5.
- Rights is incomplete, 2 of 5 migrated: PUBSRV, UNCONV and GENDEQ
  cannot be run (no implementation in the old backend; each awaits
  methodology decisions). RULELW and EDEMOC read V-Dem version 13 and
  carry 2022 to 2023; their publication awaits GOV-6. No Rights category
  score is computed.
- Global Role is incomplete, 3 of 4 registered: FORAID cannot be run
  (FORAID-1), and ARMEXP has observed scores only (ARMEXP-2). No Global Role
  category score is computed.
- ALTNRG reads the International Energy Agency through the same web
  address the old backend used. The IEA does not document it as a stable
  public service, so it may stop working without notice; nothing in this
  repository gives a right to redistribute IEA data.
- ALTNRG is scored from observed data only where a country reports all
  seven fuel groups. Most countries report no nuclear energy, so for them
  every 2000-2023 score is computed with nuclear set to zero and has
  `imputed` equal to `True`; that input shows unit `PJ`, a legacy mislabel.
  Other gaps are filled from the country's nearest reported value, which
  carries a closed nuclear plant's last output forward to 2023 (ALTNRG-2).
  Countries outside SSPI67 without all seven fuel groups get no score. If
  you run ALTNRG with one of its datasets not ingested, that fuel is
  treated as zero for every country: ingest all seven first.
- The dataset `IEA_GEOPWR` is named geothermal but holds the IEA's "solar,
  wind and other renewables", and ALTNRG measures total energy supply
  although older text says final consumption (ALTNRG-1).
- No Energy category score is computed.
- No Greenhouse Gases category score is computed.
- BEEFMK averages a production part and a consumption part. The production
  part divides thousand tonnes by people without converting to kilograms,
  so it is 1.0 (to six places) for every country and no BEEFMK score falls
  meaningfully below 0.5 (BEEFMK-1). The FAO Food Balances start in 2010:
  every 2000-2009 BEEFMK score is the country's 2010 score carried back,
  with `imputed` equal to `True` (BEEFMK-2). Singapore is not in the Food
  Balances and receives the average of all observed scores; Japan is no
  longer in them either and, not being on the old backend's list, gets no
  BEEFMK score (BEEFMK-3).
- COALPW uses the ALTNRG data and its gap filling (see ALTNRG above). A
  country with no coal at all (today Ecuador, Iraq and Kuwait) is never
  scored from data; its coal is set to zero and it scores 1.0 with
  `imputed` equal to `True`. A country with no IEA energy data at all would
  also score 1.0 (COALPW-1).
- GTRANS divides the IEA's transport CO2, stored in kilograms (the source's
  million tonnes times 10^9), by World Bank population: kilograms per
  person against goalposts of 7,000 and 0. The dataset's unit label and the
  description say tonnes per inhabitant (GTRANS-1); the scores are not
  affected. A country with emissions but no World Bank population (Taiwan)
  is not scored.
- NRGINT scores every country-year the UN reports (1990 onward). The only
  imputation is carrying a country's latest score forward to 2023 when its
  series stops earlier. The UN now reports the series in 2021 dollars; the
  description still says 2017 and the goalposts are unchanged (NRGINT-1).
- AIRPOL uses whole-country PM2.5, although its name says urban and its
  description says PM2.5 and PM10 in cities (AIRPOL-1). The UN series
  starts in 2010: every 2000-2009 AIRPOL score is the country's 2010 score
  carried back, with `imputed` equal to `True` (AIRPOL-2). An SSPI67 country
  with no data at all would get the average of all observed scores; today
  every SSPI67 country has data, so none does.
- EMPLOY is the indicator older SSPI material calls LFPART. The code is
  `EMPLOY`; there is no `LFPART` indicator or alias. It scores the
  ILO employment-to-population ratio for ages 15-64, although its
  description says ages 25-54 (EMPLOY-1). Scores exist for every area the
  ILO reports, from 2000 to the latest year.
- COLBAR has no score for ten SSPI67 countries the ILO series does not cover
  (Algeria, Ecuador, India, Iran, Iraq, Kuwait, Nigeria, Pakistan, Saudi
  Arabia, United Arab Emirates); the imputations planned for them were never
  written (COLBAR-1). The ILO series ends in 2020, so every 2021-2023 COLBAR
  score is the latest observed value carried forward.
- For EMPLOY and COLBAR, gaps in a country's own series are filled (carried
  back to 2000, forward to 2023, interpolated in between) and scored
  normally; those rows have `imputed` equal to `True`. Their `unit` column
  reads `Tax Rate`, a mislabel in the legacy backend kept so that stored
  rows match it exactly; observed rows read `Percentage` (EMPLOY) or `%`
  (COLBAR). The scores are unaffected (EMPLOY-2, COLBAR-2).
- The ILO datasets keep the ILO's own area codes, a few of which are not ISO
  codes (`KOS` for Kosovo, `ANT` for the former Netherlands Antilles). Note
  that the World Bank calls Kosovo `XKX`.
- GINIPT needs ISHRAT scores to exist (see `run()` above). Its imputed
  scores are of two kinds: gaps in a country's own Gini series are filled
  and scored normally, and countries with no Gini data at all (currently
  Kuwait, New Zealand, Saudi Arabia and Singapore) get a score predicted
  from ISHRAT. GINIPT scores exist for every country and year the World
  Bank reports, not only 2000-2023 or the SSPI67 countries (GINIPT-3).
- The two WID datasets hold values as the legacy backend stored them: a
  published share of 0.1921 appears as 0.1921000034 (a float32 artefact kept
  on purpose so scores match the legacy backend exactly). The published
  text is in each observation's provenance as `source_value`.
- DEFRST and CARBON give a fixed list of countries an imputed score
  (Belgium, the Emirates and Luxembourg for DEFRST; Kuwait, Belgium and
  Luxembourg for CARBON). Since 2026-10-08 a listed country that has its own
  FAO data is scored from that data instead (DEFRST-1, CARBON-1): today the
  Emirates and Kuwait. Belgium and Luxembourg still receive the imputed
  score. Their DEFRST and CARBON scores therefore differ from the legacy
  backend's for those two countries only.
- NITROG is computed from the 2026 EPI edition; the legacy backend used the
  2024 edition and the two report different values for the same years.
  Score changes between the editions are not evidence of changed country
  performance (NITROG-1).
- WATMAN reproduces the legacy imputation, including a fixed list of
  countries that receive constructed inputs, with one documented policy:
  Singapore's canonical series takes precedence over the legacy fallback
  that would otherwise duplicate it (WATMAN-3). That policy is a required
  resolution, not settled methodology.
  The catalog documents 88 datasets and 57 indicators; the rest have no data
  path yet, and asking to ingest or run them raises a clear error.
- No aggregation: there are no pillar, category or overall SSPI scores.
- No historical versions: a refresh or a run replaces what was stored.
- Ingestion needs a live connection to the source (UN SDG API, FAOSTAT bulk
  server, EPI website, WID website, World Bank API, ILO API); there is no offline
  mode and no cache. The WID archive is about 900 MB and is downloaded once
  per `ingest()` call, however many WID datasets the call names.
- Country codes are validated for format only, not against the country
  catalog, because canonical data can contain codes such as `XKX` (Kosovo)
  that ISO does not assign.
- BIODIV follows the legacy executable methodology exactly, including its
  treatment of landlocked countries: a missing marine series is filled with
  the reference-class average, not omitted. That behaviour is preserved and
  the question is open.
- REDLST uses the executable legacy goalposts (0, 1). The retired 2018
  static data implies (0.5, 1); the discrepancy is open.
- CHMPOL reproduces the legacy data path exactly, including a dataset
  (`UNSDG_ROTDAM`) that holds Stockholm Convention data rather than
  Rotterdam Convention data; the question is open.
- Open methodology questions such as these are listed, with their
  effect on scores, in [methodology-conflicts.md](methodology-conflicts.md).
  They are questions for methodology review, not necessarily bugs.
- `SSPI` and `Repository` are the only supported ways to write; there is no
  path from a DataFrame back into the database.
- No command-line interface and no web API yet.

See [troubleshooting](troubleshooting.md) if a first run does not behave as
described here.
