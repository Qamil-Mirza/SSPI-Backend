"""The executable Waste category on the isolated database. No network.

Of MSWGEN, RECYCL and STCONS only MSWGEN is executable, and its one input,
``EPI_MSWGEN``, has no live source (``UNAVAILABLE_SOURCES``): from a fresh
database ``sspi.ingest(["EPI_MSWGEN"])`` refuses before any fetch and
``sspi.run("MSWGEN")`` scores nothing. RECYCL and STCONS are not ported and
EWASTE is not a current indicator. So there is no runnable researcher
workflow for Waste.

The historical half: the committed 2024 fixture, normalized by the EPI
adapter and stored directly (the way a source would have), runs through
``sspi.run`` and ``sspi.query`` and matches the legacy golden exactly.
No Waste category score exists.
"""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.db import Repository
from sspi.errors import SourceUnavailableError, UnknownCodeError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import EPIClient
from sspi.ingestion.epi import normalize_epi_dataset
from sspi.metadata import MetadataCatalog

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
LEGACY = {(r["country_code"], r["year"]): r["score"] for r in json.loads((GOLDEN / "mswgen_cases.json").read_text())["scores"]}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, inputs FROM indicator_score WHERE indicator_code = 'MSWGEN' ORDER BY 1, 2")).all()


def historical_observations():
    dataset = MetadataCatalog.load().dataset("EPI_MSWGEN")
    text_ = (FIXTURES / "epi" / "epi2024indicators_P5_Indicator_WPC_ind_na.csv").read_text(encoding="utf-8")
    return normalize_epi_dataset(dataset, {"WPC_ind_na.csv": text_}).observations


def test_from_an_empty_database_waste_cannot_be_ingested_or_scored(db):
    assert counts(db) == (0, 0)
    requests = []
    client = EPIClient(http=httpx.Client(transport=httpx.MockTransport(lambda r: requests.append(r) or httpx.Response(404))))
    with SSPI(database=db) as sspi:
        with pytest.raises(SourceUnavailableError, match="EPI_MSWGEN cannot be ingested"):
            sspi.ingest(["EPI_MSWGEN"], client={"EPI": client})
        assert requests == [] and counts(db) == (0, 0)  # refused before any fetch or write
        assert sspi.run("MSWGEN").written == 0  # no observations: nothing to score, nothing imputed
        for code in ("RECYCL", "STCONS", "EWASTE"):
            with pytest.raises(UnknownCodeError):
                sspi.run(code)
        assert sspi.query(indicators=["MSWGEN", "RECYCL", "STCONS"]).empty
    assert counts(db) == (0, 0)


def test_historical_observations_run_and_query_with_exact_legacy_parity(db):
    observations = historical_observations()
    with db.transaction() as session:
        assert Repository(session).replace_dataset("EPI_MSWGEN", observations) == 6210
    with SSPI(database=db) as sspi:
        run = sspi.run("MSWGEN")
        everything = sspi.query(indicators=["MSWGEN"], include_inputs=True)
        waste = sspi.query(indicators=["MSWGEN"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        before = stored(db)
        assert sspi.run("MSWGEN").written == run.written == 6210 and stored(db) == before  # reruns converge
    assert (len(run.observed_scores), len(run.imputed_scores)) == (6210, 0)
    assert {(r.country_code, r.year): r.score for r in everything.itertuples()} == LEGACY and not everything["imputed"].any()
    assert {c: str(t) for c, t in waste.dtypes.items()} == INDICATOR_DTYPES and len(waste) == 3 * 14 and set(waste["indicator_code"]) == {"MSWGEN"}
    usa = {r.year: r.score for r in waste.itertuples() if r.country_code == "USA"}
    assert usa[2018] == 0.867  # 1 - 13.3/100: the legacy direction (MSWGEN-1)
