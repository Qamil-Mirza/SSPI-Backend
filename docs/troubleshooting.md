# Troubleshooting first-run errors

Each entry shows the message as you will see it, what it means, and the fix.

## `ModuleNotFoundError: No module named 'sspi'`

The virtual environment is not active, or the package was not installed into
it. In a notebook, the kernel may be a different Python than your `.venv`.

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import sspi, sys; print(sys.executable)"
```

For Jupyter, make sure the kernel's `sys.executable` points inside `.venv`.

## `DatabaseConfigurationError: DATABASE_URL is not configured. Set the DATABASE_URL environment variable or add it to /path/to/sspi-backend/.env.`

The library found neither the environment variable nor a `.env` file at the
path in the message. The path is always the repository root, whatever
directory the notebook runs in.

```bash
cp .env.example .env
```

Then check the URL inside matches your server. This error appears on the
first `query()`, `ingest()` or `run()`, not when you construct `SSPI()`;
that is expected.

## `OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 5432 failed`

PostgreSQL is not running, or is on a different host or port than
`DATABASE_URL` says.

```bash
docker compose ps            # is sspi-postgres running?
docker compose up -d         # start it
```

For a non-Docker server, confirm host and port, and that the server accepts
TCP connections from your machine.

## `OperationalError: ... password authentication failed for user "sspi"` or `role "..." does not exist` or `database "..." does not exist`

The URL's user, password or database name does not match the server. With
Docker all three are `sspi`. With your own server, create the role and
database as shown in [setup](setup.md#3-start-postgresql), then fix `.env`.

## `ProgrammingError: (psycopg.errors.UndefinedTable) relation "observation" does not exist`

The database exists and is reachable but has no tables: migrations have not
run.

```bash
alembic upgrade head
```

If you see `relation "indicator_score" does not exist` or an error naming a
column such as `imputed`, the same command brings an older database up to
date.

## `alembic: command not found`

The virtual environment is not active. Activate it, or run
`python -m alembic upgrade head`.

## `alembic upgrade head` fails with a connection or configuration error

Alembic uses the same `DATABASE_URL` rule as the library, so fix the cause
listed above for that message, then rerun.

## `query()` returns an empty DataFrame

Usually not an error. Common causes, in order:

1. Nothing has been ingested into this database yet. Run
   `sspi.ingest([...])` once if you own the database, or check with whoever
   maintains a shared one.
2. You asked for an indicator that has never been computed. Run it, for
   example `sspi.run("BIODIV")` or `sspi.run("REDLST")`.
3. The filter genuinely matches nothing: a country the source does not
   report, such as Austria for `UNSDG_MARINE`, or years outside the data.

Check quickly with an unfiltered query:

```python
sspi.query(datasets=["UNSDG_MARINE"]).shape
```

## `UnknownCodeError: unknown dataset code 'UNSDG_MARIN'`

A typo or a code that is not in the metadata catalog. Codes are uppercase
and exact. List valid ones:

```python
[d.code for d in sspi.metadata.datasets()]
[i.code for i in sspi.metadata.indicators()]
```

## `UnknownCodeError: no executable definition registered for indicator 'RECYCL'; registered: ['BIODIV', 'REDLST', 'CHMPOL', 'WATMAN', 'NITROG', 'DEFRST', 'CARBON', 'ISHRAT', 'GINIPT', 'EMPLOY', 'COLBAR', 'ALTNRG', 'NRGINT', 'AIRPOL', 'BEEFMK', 'COALPW', 'GTRANS', 'MSWGEN']`

The indicator exists in the catalog but cannot be run in V1. Only the
indicators in the `registered` list are executable. You can still `query()` it; you will get an empty frame unless
someone has stored scores for it.

## `NotIngestibleError: UNSDG_CSTUNT is defined in the metadata catalog (organization UNSDG) but has no ingestion path yet; ingestible datasets today: [...]`

The dataset is documented but V1 has no source path for it. Nothing was
fetched or written.

## `SourceUnavailableError: EPI_MSWGEN cannot be ingested: the legacy source, series WPC of the 2024 EPI indicator archive ... is no longer served ...`

The dataset's legacy source is gone and no replacement source has been
approved, so there is nothing to fetch. This is a `NotIngestibleError`
raised before any network or database use. The indicator that reads it
(MSWGEN) is still registered and reproduces the legacy scores exactly on the
committed historical fixture, but `sspi.ingest()` cannot populate its input,
so `sspi.run("MSWGEN")` on a fresh database scores nothing. Do not work
around this by loading a different source; see
[indicator-migration.md](indicator-migration.md) ("Historical parity only:
live source unavailable").

## `InvalidQueryError: pass exactly one of datasets=[...] or indicators=[...]`

Observations and scores are different things and never share a frame. Make
two queries.

## `InvalidQueryError: countries=[] selects nothing; pass None for no restriction or at least one code`

An empty list is rejected on purpose so a mistake in building the list
cannot silently mean "everything". Pass `None` or omit the argument.

## `InvalidQueryError: countries must be a list of codes, not the string 'MYS'`

Wrap single codes in a list: `countries=["MYS"]`. The same applies to
`datasets` and `indicators`.

## `InvalidQueryError: countries entries must be ISO 3166-1 alpha-3 codes (three uppercase letters), got 'Malaysia'`

Use ISO3 codes. Look one up: `sspi.country("MYS").name`.

## `IngestionRequestError: duplicate dataset codes requested: ['UNSDG_MARINE']`

Each dataset may appear once per `ingest()` call.

## `SourceRequestError` or `SourceResponseError` during `ingest()`

The source (UN SDG API, FAOSTAT bulk server or EPI website) could not be
reached or returned something unexpected. Check your internet connection and
retry. Nothing was written to the database, for any dataset in that call.
`SourceResponseError: EPI archive 'epi2024indicators' is not a zip file`
means the legacy 2024 URL was requested; it now serves an HTML page, and the
catalog points `EPI_NITROG` at the 2026 archive.

## `NormalizationError` during `ingest()`

The source returned data that does not match the canonical definition, for
example a changed unit. Nothing was written. This needs a maintainer to look
at the source change; include the full message when reporting it.

## `ScoreIntegrityError: BIODIV/MYS/2020: stored imputed=True but the embedded inputs classify the score as observed`

A score row was modified outside the library. Rerun `sspi.run("BIODIV")`
to rebuild the indicator's scores from the stored observations.

## BIODIV scores look unchanged after `ingest()`

By design. `ingest()` refreshes observations only. Call
`sspi.run("BIODIV")` to recompute scores from the new observations.

## `ImputationError: WATMAN: the legacy impute route builds synthetic CWUEFF series for [...] unconditionally, but the source now provides CWUEFF for them ...`

Not a bug in your setup. One of the twelve countries the legacy WATMAN
procedure treats specially now reports source data of its own, and no policy
exists yet for that case; see WATMAN-3 in
[methodology-conflicts.md](methodology-conflicts.md). Nothing was written.

## `ScoreDependencyError: GINIPT requires existing ISHRAT scores for its legacy imputation procedure and none were found. Run ISHRAT first, ...`

GINIPT predicts scores for countries without Gini data from their ISHRAT
scores, so ISHRAT has to be computed first. Nothing was written. Ingest the
two WID datasets, `run("ISHRAT")`, then `run("GINIPT")` again.

## `RuntimeError: this SSPI instance is closed`

You called a method after `sspi.close()` or after leaving a
`with SSPI() as sspi:` block. Create a new `SSPI()`.
