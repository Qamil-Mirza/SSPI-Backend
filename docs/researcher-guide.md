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
sspi.executable_indicators()   # ('BIODIV', 'REDLST', 'CHMPOL', 'WATMAN', 'NITROG', 'DEFRST', 'CARBON', 'ISHRAT', 'GINIPT', 'EMPLOY', 'COLBAR')
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
| Ingestible datasets | BIODIV: `UNSDG_MARINE`, `UNSDG_TERRST`, `UNSDG_FRSHWT`; REDLST: `UNSDG_REDLST`; CHMPOL: `UNSDG_STKHLM`, `UNSDG_MINMAT`, `UNSDG_MONTRL`, `UNSDG_BASELA`, `UNSDG_ROTDAM`; WATMAN inputs: `UNSDG_WTSTRS`, `UNSDG_WUSEFF`, `UNSDG_CWUEFF`; NITROG: `EPI_NITROG`; DEFRST: `UNFAO_FRSTLV`, `UNFAO_FRSTAV`; CARBON: `UNFAO_CRBNLV`, `UNFAO_CRBNAV`; ISHRAT: `WID_NINCSH_PRETAX_P90P100`, `WID_NINCSH_PRETAX_P0P50`; GINIPT: `WB_GINIPT`; EMPLOY: `ILO_EMPLOY_TO_POP`; COLBAR: `ILO_COLBAR` |
| Executable indicators | `BIODIV`, `REDLST`, `CHMPOL`, `WATMAN`, `NITROG`, `ISHRAT`, `GINIPT` (run `ISHRAT` first), `EMPLOY`, `COLBAR` live; `DEFRST`, `CARBON` implemented and parity-validated, a live run may stop pending a methodology decision (see below) |
| Sources | UN SDG Global Database API; FAOSTAT bulk download (Land Use domain); Yale EPI 2026 indicator archive; World Inequality Database bulk archive; World Bank Indicators API; ILOSTAT SDMX API |
| Queryable | any dataset or indicator in the catalog, returning whatever is stored |

## Known limitations

- Only the datasets above can be ingested and only the eleven indicators
  above can be run.
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
- DEFRST and CARBON are implemented and match the legacy backend exactly on
  the historical fixtures, but they are not yet fully live-ready: a live run
  may stop with an `ImputationError`. The legacy methodology always imputes
  a fixed list of countries (Belgium, the Emirates and Luxembourg for
  DEFRST; Kuwait, Belgium and Luxembourg for CARBON). Current FAO data now
  contains real data for the Emirates and for Kuwait, so the old rule would
  produce both a real and an imputed score for the same country-years. The
  backend stops rather than choosing between them, writes nothing, and the
  methodology team has not yet decided (DEFRST-1, CARBON-1).
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
