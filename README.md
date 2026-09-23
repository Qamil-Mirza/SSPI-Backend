SETUP
1. Create virtual environment

## Using the library from a notebook

The researcher-facing entry point is `SSPI`. It reads data already stored in
PostgreSQL and returns tidy pandas DataFrames. Nothing is fetched from a
source API and nothing is computed unless you ask for it explicitly.

```python
from sspi import SSPI

sspi = SSPI()                     # database resolved from DATABASE_URL, then the project-root .env

marine = sspi.query(
    datasets=["UNSDG_MARINE"],    # dataset codes, validated against the metadata catalog
    countries=["MYS"],            # ISO3 codes; None means every country
    years=(2018, 2023),           # inclusive; None means every year
)
#   dataset_code country_code  year     value     unit
#   UNSDG_MARINE          MYS  2018  19.70109  PERCENT
#   ...

biodiv = sspi.query(
    indicators=["BIODIV"],
    countries=["MYS", "AUT"],
    years=(2018, 2023),
)
#   indicator_code country_code  year     score   unit  imputed
#           BIODIV          AUT  2018  0.585...  Index     True
#           BIODIV          MYS  2018  0.297...  Index    False
#   ...
```

Rules of `query`:

- Pass exactly one of `datasets=[...]` or `indicators=[...]`; observations
  and scores are different things and never share a frame.
- Rows are ordered by code, country and year. An empty result keeps the same
  columns and dtypes (`year` int64, `value`/`score` float64, `imputed` bool,
  codes and units `string`).
- `imputed` is True when at least one input of the score was imputed.
- `include_provenance=True` (dataset queries) adds a `provenance` column of
  dicts; `include_inputs=True` (indicator queries) adds an `inputs` column
  describing each score's inputs. Both are off by default.
- Unknown dataset or indicator codes raise `UnknownCodeError`; malformed
  arguments raise `InvalidQueryError`; an empty list raises rather than
  meaning "everything". Country codes are checked for ISO3 format only.

Computation is separate and explicit:

```python
result = sspi.run("BIODIV")       # reads observations from PostgreSQL, scores, imputes, persists
result.observed_scores, result.imputed_scores, result.unscored, result.written
sspi.executable_indicators()      # ('BIODIV',) today; the metadata catalog knows 57 indicators
```

Metadata lookups need no database: `sspi.indicator("BIODIV")`,
`sspi.dataset("UNSDG_MARINE")`, `sspi.country("MYS")`,
`sspi.country_group("SSPI67").members`, and the full catalogs as
`sspi.metadata` and `sspi.countries`.

Database ownership: `SSPI()` and `SSPI(database="postgresql+psycopg://...")`
create and own their database and dispose it on `close()` or when used as a
context manager; `SSPI(database=existing_database)` never disposes the object
you passed. No session stays open between calls. Without a configured
database, the first `query` or `run` raises `DatabaseConfigurationError`.

```python
with SSPI() as sspi:
    df = sspi.query(indicators=["BIODIV"], countries=sspi.country_group("SSPI67").members)
```
