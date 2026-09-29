# Setup: from a fresh clone to your first query

This page takes you from nothing to a working `sspi.query(...)` in a notebook.
Every step is required once; after that you only need to activate the
virtual environment.

You need Python 3.11 or newer, `git`, and either Docker or an existing
PostgreSQL server you can create a database on.

## 1. Clone and create a virtual environment

```bash
git clone <repository-url> sspi-backend
cd sspi-backend
python3 --version            # must print 3.11 or newer
python3 -m venv .venv
source .venv/bin/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
```

Your prompt now starts with `(.venv)`. Every later command assumes this
environment is active.

## 2. Install the package

```bash
pip install -e ".[dev]"
```

The `-e` flag installs the package in editable mode, so pulling new code
takes effect without reinstalling. `[dev]` adds `pytest`. This also installs
pandas, SQLAlchemy, the PostgreSQL driver and Alembic.

Check it worked. This needs no database yet:

```bash
python -c "from sspi import SSPI; print(SSPI().indicator('BIODIV').name)"
```

Expected output:

```
Biodiversity Protection
```

## 3. Start PostgreSQL

Pick one of the two options.

**Option A: Docker (recommended if you have no PostgreSQL yet).** The
repository ships a compose file that starts PostgreSQL 16 with a database,
user and password all named `sspi`, on port 5432:

```bash
docker compose up -d
docker compose ps            # the sspi-postgres container should be "running"
```

Data persists in a Docker volume across restarts. `docker compose down`
stops the server and keeps the data; `docker compose down -v` deletes it.

**Option B: an existing PostgreSQL server.** Create an empty database and a
role that owns it, for example:

```sql
CREATE ROLE sspi WITH LOGIN PASSWORD 'sspi';
CREATE DATABASE sspi OWNER sspi;
```

Any PostgreSQL 12 or newer works.

## 4. Tell the library where the database is: `DATABASE_URL`

The library reads one setting, `DATABASE_URL`, in this order:

1. the `DATABASE_URL` environment variable, if set;
2. otherwise the `.env` file in the repository root.

The `.env` lookup uses the repository root regardless of the directory your
notebook runs in, so a notebook under `analysis/` or anywhere else finds it.

Create the file from the template:

```bash
cp .env.example .env
```

The template already matches the Docker setup:

```
DATABASE_URL=postgresql+psycopg://sspi:sspi@localhost:5432/sspi
```

For your own server, edit the URL. The format is
`postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`. Keep the
`postgresql+psycopg` prefix; it selects the installed driver. `.env` is
git-ignored, so credentials stay local.

## 5. Create the tables: Alembic migrations

The database starts empty. Alembic creates and upgrades the tables:

```bash
alembic upgrade head
```

Expected output ends with lines like:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, observation and indicator_score tables
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, indicator_score.imputed: derived observed/imputed classification
```

Alembic resolves the database from the same `DATABASE_URL` rule as the
library, so no extra configuration is needed. Rerunning the command is safe;
it does nothing when the database is already current. After pulling new code,
run it again in case a migration was added.

## 6. Your first query

Start Python or a notebook with the virtual environment active:

```python
from sspi import SSPI

sspi = SSPI()
df = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"], years=(2018, 2023))
df
```

On a freshly created database this returns an empty DataFrame with five
columns, because nothing has been ingested yet. That is the correct result,
not an error:

```
Empty DataFrame
Columns: [dataset_code, country_code, year, value, unit]
Index: []
```

If your team shares a database that already holds data, you see rows
immediately and setup is complete. If you are working alone on a fresh
database, load the datasets you need once and compute their indicator, for
example BIODIV (REDLST works the same way with `UNSDG_REDLST`):

```python
sspi.ingest(["UNSDG_MARINE", "UNSDG_TERRST", "UNSDG_FRSHWT"])   # fetches from the UN SDG API; needs internet
sspi.run("BIODIV")
sspi.query(indicators=["BIODIV"], countries=["MYS", "AUT"], years=(2018, 2023))
```

```
   indicator_code country_code  year     score   unit  imputed
0          BIODIV          AUT  2018  0.585748  Index     True
1          BIODIV          AUT  2019  0.585856  Index     True
...
6          BIODIV          MYS  2018  0.297287  Index    False
...
```

From here on, ordinary analysis is `query()` alone. Read the
[researcher guide](researcher-guide.md) for what the columns mean and when
`ingest()` and `run()` are appropriate.

## Optional: running the test suite

```bash
pytest                       # unit and golden tests, no database needed
```

The PostgreSQL integration tests create a throwaway database named
`sspi_test_<random>` on a server you point them at, run, and drop it. They
never touch your `DATABASE_URL` database. To include them:

```bash
SSPI_TEST_DATABASE_URL=postgresql+psycopg://sspi:sspi@localhost:5432/sspi pytest
```

The role must be allowed to `CREATE DATABASE`; the Docker `sspi` role is.
