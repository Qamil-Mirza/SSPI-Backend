"""The three Tax leaf indicators on the isolated database, with the Tax
Foundation file, the World Bank API and the WID bulk archive served from the
committed fixtures by a mock transport. No network.

    sspi.ingest(["TF_CRPTAX", "WB_TAXREV", four WID income-share datasets])
    sspi.run("CRPTAX"), sspi.run("TAXREV"), sspi.run("TXRDST")
    sspi.query(indicators=["CRPTAX", "TAXREV", "TXRDST"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definitions in
tests/unit/test_researcher_guide_tax.py). Stored scores are compared with the
legacy golden files exactly. No Tax category score exists.

The Tax Foundation fixture is a subset of the approved file, so its
checksum differs from the one the default configuration pins. The workflow
therefore injects a client configured explicitly for the fixture (same key,
edition and address, the fixture's checksum); a separate test shows the
default configuration refusing it and storing nothing.
"""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError, SourceResponseError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import TaxFoundationClient, WIDClient, WorldBankClient
from sspi.ingestion.taxfoundation import FILES, SourceFile
from sspi.ingestion.wid import ARCHIVES
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_tax import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["CRPTAX", "TAXREV", "TXRDST"]
CRPTAX = json.loads((GOLDEN / "crptax_cases.json").read_text())
TAXREV = json.loads((GOLDEN / "taxrev_cases.json").read_text())
TXRDST = json.loads((GOLDEN / "txrdst_cases.json").read_text())
TF_KEY = "rates_final_2025-01"
TF_CONTENT = (FIXTURES / "taxfoundation" / "rates_final_2025-01_sample.csv").read_bytes()
TF_FIXTURE_FILES = {TF_KEY: SourceFile(FILES[TF_KEY].edition, FILES[TF_KEY].url, hashlib.sha256(TF_CONTENT).hexdigest())}


def _wid_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted((FIXTURES / "wid").glob("WID_*.csv")):
            z.writestr(path.name, path.read_text(encoding="utf-8"))
    return buffer.getvalue()


WID_ZIP = _wid_zip()


class Servers:
    """One mock transport serving the Tax Foundation, World Bank and WID fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0])
        if url == FILES[TF_KEY].url:
            return httpx.Response(200, content=TF_CONTENT, headers={"content-type": "text/csv"})
        if url == ARCHIVES["wid_all_data"]:
            return httpx.Response(200, content=WID_ZIP)
        if url.startswith(WB_URL + "GC.TAX.TOTL.GD.ZS?"):
            return httpx.Response(200, content=(FIXTURES / "wb" / "GC.TAX.TOTL.GD.ZS_sample.json").read_bytes())
        return httpx.Response(404)

    def clients(self, tf_files=TF_FIXTURE_FILES):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"TF": TaxFoundationClient(files=tf_files, http=http), "WB": WorldBankClient(http=http), "WID": WIDClient(http=http)}

    def ingest(self, sspi, datasets, **kwargs):
        """``sspi.ingest`` with injected clients, which it never closes; the WID client holds the spooled archive."""
        clients = self.clients(**kwargs)
        try:
            return sspi.ingest(datasets, client=clients)
        finally:
            clients["WID"].close()


def legacy_scores():
    """(indicator, country, year) -> (score, stored by the impute route)."""
    imputing = {code: {(code, r["country_code"], r["year"]): (r["score"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in case[key]} for code, case in (("CRPTAX", CRPTAX), ("TAXREV", TAXREV))}
    txrdst = {("TXRDST", r["country_code"], r["year"]): (r["score"], False) for r in TXRDST["scores"]}
    return {**imputing["CRPTAX"], **imputing["TAXREV"], **txrdst}


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, inputs FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_tax_workflow_from_an_empty_database(db):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert set(DATASETS) == set(required_datasets()) and len(DATASETS) == 6
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = servers.ingest(sspi, DATASETS)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        taxes = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        rates = sspi.query(datasets=["TF_CRPTAX"], countries=["USA"], years=(2018, 2018), include_provenance=True)

    # one Tax Foundation file, one World Bank request, one archive download for all four WID datasets
    assert ingestion.source_fetches == (TF_KEY, "GC.TAX.TOTL.GD.ZS", "wid_all_data")
    assert servers.requests == [FILES[TF_KEY].url, WB_URL + "GC.TAX.TOTL.GD.ZS", ARCHIVES["wid_all_data"]]
    assert ingestion.counts == {"TF_CRPTAX": 731, "WB_TAXREV": 339, **{code: 1650 for code in DATASETS[2:]}}

    assert (len(runs["CRPTAX"].observed_scores), len(runs["CRPTAX"].imputed_scores), runs["CRPTAX"].written) == (731, 69, 800)
    assert (len(runs["TAXREV"].observed_scores), len(runs["TAXREV"].imputed_scores), runs["TAXREV"].written) == (339, 235, 574)
    assert (len(runs["TXRDST"].observed_scores), len(runs["TXRDST"].imputed_scores), runs["TXRDST"].written) == (1650, 0, 1650)
    assert {(r.indicator_code, r.country_code, r.year): (r.score, r.imputed) for r in everything.itertuples()} == legacy_scores()

    # the researcher-facing frame: three leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in taxes.dtypes.items()} == INDICATOR_DTYPES and sorted(set(taxes["indicator_code"])) == INDICATORS
    assert len(taxes) == 3 * 3 * 14 and not taxes["imputed"].any()  # all three countries report every year of all three
    assert {c: set(taxes[taxes.indicator_code == c]["unit"]) for c in INDICATORS} == {"CRPTAX": {"Tax Rate"}, "TAXREV": {"Percentage"}, "TXRDST": {"Ratio of Bottom 50% Income Share to to Top 10% Income Share"}}
    usa = {(r.indicator_code, r.year): r.score for r in taxes.itertuples() if r.country_code == "USA"}
    assert (usa[("CRPTAX", 2017)], usa[("CRPTAX", 2018)]) == (38.906474 / 40, 25.83858 / 40)  # the 2018 federal cut, combined rate
    assert usa[("TAXREV", 2023)] == 10.6177678118026 / 50 and usa[("TXRDST", 2023)] == 0.9286340767505368

    # what is stored: the edition with each rate; the four TXRDST shares; Nigeria's TAXREV mean; Niue carried back
    (row,) = rates.itertuples()
    assert row.value == 25.83858 and row.unit == "Tax Rate"
    assert {k: row.provenance[k] for k in ("source_edition", "source_url", "source_file", "source_value")} == {"source_edition": "2025/01", "source_url": FILES[TF_KEY].url, "source_file": TF_KEY, "source_value": "25.83858"}
    scored = {(r.indicator_code, r.country_code, r.year): r for r in everything.itertuples()}
    assert {i["dataset_code"] for i in scored[("TXRDST", "MYS", 2023)].inputs} == set(DATASETS[2:])
    (mean,) = scored[("TAXREV", "NGA", 2015)].inputs
    assert mean["imputation_method"] == "ImputeReferenceClassAverage" and mean["value"] == TAXREV["reference_class"]["mean"]
    (niue,) = scored[("CRPTAX", "NIU", 2000)].inputs
    assert scored[("CRPTAX", "NIU", 2000)].imputed and (niue["imputation_method"], niue["value"]) == ("Backward Extrapolation", 30.0)  # Niue's first rate, 2020


def test_the_default_configuration_refuses_any_file_but_the_approved_edition(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        with pytest.raises(SourceResponseError, match="no other edition is substituted"):
            servers.ingest(sspi, ["TF_CRPTAX"], tf_files=None)  # FILES: the full 2025/01 file's checksum, not the fixture's
    assert counts(db) == (0, 0) and servers.requests == [FILES[TF_KEY].url]


def test_missing_datasets_behave_as_legacy_and_reruns_converge(db):
    servers = Servers()
    with SSPI(database=db) as sspi:
        assert sspi.run("CRPTAX").written == 0 == sspi.run("TXRDST").written  # never ingested: nothing to score, no error
        with pytest.raises(ImputationError, match="reference data for WB_TAXREV/VNM is empty"):
            sspi.run("TAXREV")  # the legacy impute route raised here too: no mean for the four listed countries
        assert counts(db) == (0, 0) and servers.requests == []
        servers.ingest(sspi, DATASETS)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        servers.ingest(sspi, DATASETS)  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot
