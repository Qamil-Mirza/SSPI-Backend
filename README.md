# sspi-backend

Backend and research data platform for the Sustainable and Shared-Prosperity
Policy Index (SSPI). Python 3.11+, PostgreSQL, pandas at the researcher boundary.

## For research assistants

```python
from sspi import SSPI

sspi = SSPI()

df = sspi.query(
    indicators=["BIODIV"],
    countries=["MYS", "AUT"],
    years=(2000, 2023),
)
```

`query()` reads what is already stored in PostgreSQL and returns a tidy pandas
DataFrame. It never fetches from a source API and never recomputes anything.
Refreshing data (`ingest()`) and recomputing indicator scores (`run()`) are
separate, explicit calls that most analysis sessions never need.

- [Setup: from a fresh clone to your first query](docs/setup.md)
- [Researcher guide: query, ingest, run, and what the data means](docs/researcher-guide.md)
- [Troubleshooting first-run errors](docs/troubleshooting.md)

## V1 scope

| Ingestible datasets | Executable indicators |
|---|---|
| 12 UN SDG datasets, listed in the [researcher guide](docs/researcher-guide.md#v1-support) | `BIODIV`, `REDLST`, `CHMPOL` |

The metadata catalog describes 88 datasets and 57 indicators; only the ones
above have a working data path today. See the [known limitations](docs/researcher-guide.md#known-limitations).

## For maintainers and methodology reviewers

- [Methodology conflicts and questions for review](docs/methodology-conflicts.md):
  open questions found during migration, where legacy sources disagree. These
  are questions for review, not necessarily bugs.
- [Indicator migration: the parity gate](docs/indicator-migration.md): what
  must match the legacy backend before an indicator counts as migrated.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then edit DATABASE_URL if needed
docker compose up -d            # local PostgreSQL, or use your own server
alembic upgrade head            # create the tables
pytest                          # PostgreSQL tests skip unless SSPI_TEST_DATABASE_URL is set
```
