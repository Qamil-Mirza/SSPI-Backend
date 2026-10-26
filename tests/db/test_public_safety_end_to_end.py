"""The four Public Safety leaf indicators on the isolated database, with
every source served offline: the World Bank API, the UNODC portal and the
FSI site from the committed sample and synthetic workbooks by mock
transports, and the GCI transcription from the committed synthetic file in
a local source directory. No network.

    sspi.ingest(["WB_MURDER", "ITU_CYBSEC", "FSI_SECAPP", "UNODC_PRIPOP"])
    sspi.run("MURDER"), sspi.run("CYBSEC"), sspi.run("SECAPP"), sspi.run("PRISON")
    sspi.query(indicators=["MURDER", "CYBSEC", "SECAPP", "PRISON"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline in tests/unit/test_researcher_guide_public_safety.py).
Stored scores are compared with the legacy golden files exactly; re-ingesting
and re-running converge. No Public Safety category score exists.
"""

import hashlib
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError, NormalizationError, SourceRequestError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import WorldBankClient
from sspi.ingestion.fsi import FSIWorkbookClient
from sspi.ingestion.fsi import SourceWorkbook as FSISourceWorkbook
from sspi.ingestion.localfiles import LOCAL_FILES, LocalFileClient, LocalSourceFile
from sspi.ingestion.unodc import WORKBOOKS, SourceWorkbook, UNODCWorkbookClient
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.unit.test_researcher_guide_public_safety import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
WORKBOOK = FIXTURES / "unodc" / "data_cts_prisons_and_prisoners_synthetic.xlsx"
TRANSCRIPTION = FIXTURES / "itu" / "gci-local-indicator-summary_synthetic.csv"
UNODC_KEY = "data_cts_prisons_and_prisoners_2026-09-30"
ITU_KEY = "gci-local-indicator-summary"
FSI_KEY = "fsi-excel_2006-2023"
FSI_EDITIONS = (2018, 2021, 2023)
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["MURDER", "CYBSEC", "SECAPP", "PRISON"]
CASES = {
    code: json.loads((GOLDEN / name).read_text())
    for code, name in (("MURDER", "murder_cases.json"), ("CYBSEC", "cybsec_synthetic_cases.json"), ("SECAPP", "secapp_synthetic_cases.json"), ("PRISON", "prison_synthetic_cases.json"))
}


def fsi_path(edition):
    return FIXTURES / "fsi" / f"fsi-{edition}_synthetic.xlsx"


def fsi_url(edition):
    return f"https://fsi.invalid/fsi-{edition}_synthetic.xlsx"


class Servers:
    """A mock World Bank API, UNODC portal and FSI site, answering from the committed fixtures."""

    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url.split("?")[0])
        if url.startswith(WB_URL + "VC.IHR.PSRC.P5?"):
            return httpx.Response(200, content=(FIXTURES / "wb" / "VC.IHR.PSRC.P5_sample.json").read_bytes())
        if url == WORKBOOKS[UNODC_KEY].url:
            return httpx.Response(200, content=WORKBOOK.read_bytes())
        for edition in FSI_EDITIONS:
            if url == fsi_url(edition):
                return httpx.Response(200, content=fsi_path(edition).read_bytes())
        return httpx.Response(404)

    def clients(self, local_root):
        http = httpx.Client(transport=httpx.MockTransport(self))
        unodc = {UNODC_KEY: SourceWorkbook("synthetic test workbook", WORKBOOKS[UNODC_KEY].url, hashlib.sha256(WORKBOOK.read_bytes()).hexdigest())}
        fsi = {FSI_KEY: tuple(FSISourceWorkbook(e, fsi_url(e), hashlib.sha256(fsi_path(e).read_bytes()).hexdigest()) for e in FSI_EDITIONS)}
        (local_root / "itu").mkdir(parents=True, exist_ok=True)
        (local_root / "itu" / "gci-local-indicator-summary.csv").write_bytes(TRANSCRIPTION.read_bytes())
        itu = {ITU_KEY: LocalSourceFile("synthetic test transcription", "itu/gci-local-indicator-summary.csv", hashlib.sha256(TRANSCRIPTION.read_bytes()).hexdigest(), "tests")}
        clients = {"WB": WorldBankClient(http=http), "UNODC": UNODCWorkbookClient(workbooks=unodc, http=http), "FSI": FSIWorkbookClient(edition_sets=fsi, http=http), "ITU": LocalFileClient(root=local_root, files=itu)}
        return clients, http

    def ingest(self, sspi, datasets, local_root):
        clients, http = self.clients(local_root)
        with http:
            return sspi.ingest(datasets, client=clients)


def legacy_scores(*codes):
    """(indicator, country, year) -> score, observed and imputed, from the golden files."""
    out = {}
    for code in codes:
        case = CASES[code]
        for record in (case.get("observed_scores") or case.get("scores") or []) + case.get("imputed_scores", []):
            out[(code, record["country_code"], record["year"])] = record["score"]
    return out


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, imputed, unit, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_public_safety_workflow_from_an_empty_database(db, tmp_path):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["WB_MURDER", "ITU_CYBSEC", "FSI_SECAPP", "UNODC_PRIPOP"]
    servers = Servers()
    with SSPI(database=db) as sspi:
        ingestion = servers.ingest(sspi, DATASETS, tmp_path)
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        results = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True)
        britain = sspi.query(datasets=["UNODC_PRIPOP"], countries=["GBR"], years=(2021, 2022), include_provenance=True)
        koreas = sspi.query(datasets=["FSI_SECAPP"], countries=["KOR", "PRK"], include_provenance=True)

    # one fetch per source; the FSI set is three workbooks
    assert ingestion.source_fetches == ("VC.IHR.PSRC.P5", ITU_KEY, FSI_KEY, UNODC_KEY)
    assert servers.requests == [WB_URL + "VC.IHR.PSRC.P5", *(fsi_url(e) for e in FSI_EDITIONS), WORKBOOKS[UNODC_KEY].url]
    assert ingestion.counts == {"WB_MURDER": 297, "ITU_CYBSEC": 56, "FSI_SECAPP": 56, "UNODC_PRIPOP": 112}

    assert (len(runs["MURDER"].observed_scores), len(runs["MURDER"].imputed_scores), runs["MURDER"].written) == (297, 187, 484)
    assert (len(runs["CYBSEC"].observed_scores), len(runs["CYBSEC"].imputed_scores), runs["CYBSEC"].written) == (56, 0, 56)
    assert (len(runs["SECAPP"].observed_scores), len(runs["SECAPP"].imputed_scores), runs["SECAPP"].written) == (56, 0, 56)
    assert (len(runs["PRISON"].observed_scores), len(runs["PRISON"].imputed_scores), runs["PRISON"].written) == (112, 105, 217)
    assert {(r.indicator_code, r.country_code, r.year): r.score for r in everything.itertuples()} == legacy_scores(*INDICATORS)

    # the researcher-facing frame: four leaf indicators, three countries, 2010-2023; no category score
    assert {c: str(t) for c, t in results.dtypes.items()} == INDICATOR_DTYPES and sorted(set(results["indicator_code"])) == sorted(INDICATORS)
    years = {c: sorted(set(results[results.indicator_code == c]["year"])) for c in INDICATORS}
    assert years["CYBSEC"] == [2014, 2017, 2018, 2020] and years["SECAPP"] == [2018, 2021, 2023]  # source editions only
    assert len(results) == 42 + 11 + 9 + 42
    assert {c: set(results[results.indicator_code == c]["unit"]) for c in INDICATORS} == {"MURDER": {"Index"}, "CYBSEC": {"Index"}, "SECAPP": {"Index"}, "PRISON": {"Prisoners per 100,000 population"}}
    imputed = {(r.indicator_code, r.country_code, r.year) for r in results.itertuples() if r.imputed}
    assert imputed == {("PRISON", "MYS", 2010), ("PRISON", "MYS", 2011), ("PRISON", "MYS", 2023), ("PRISON", "USA", 2022), ("PRISON", "USA", 2023)}
    mys = {(r.indicator_code, r.year): r.score for r in results.itertuples() if r.country_code == "MYS"}
    assert mys[("MURDER", 2023)] == 0.9632753784643061 and mys[("PRISON", 2010)] == 0.745 and mys[("CYBSEC", 2020)] == 0.9986 and mys[("SECAPP", 2018)] == 0.375

    # what is stored: the UK row records the jurisdictions it averages (PRISON-1); North Korea is not South Korea (SECAPP-1)
    by_year = {r.year: r for r in britain.itertuples()}
    assert by_year[2021].value == 147.0 and by_year[2021].provenance["unweighted_mean_of"] == ["GBR_E_W", "GBR_S"]
    assert by_year[2022].provenance["unweighted_mean_of"] == ["GBR_E_W"] and by_year[2022].provenance["source_file"] == UNODC_KEY
    korea = {(r.country_code, r.year): r for r in koreas.itertuples()}
    assert korea[("PRK", 2023)].value == 8.2 and korea[("PRK", 2023)].provenance["source_country_name"] == "North Korea" and "country_code_correction" in korea[("PRK", 2023)].provenance
    assert korea[("KOR", 2023)].value == 1.8 and "country_code_correction" not in korea[("KOR", 2023)].provenance


def test_cybsec_needs_its_local_file_and_applies_only_the_approved_correction(db, tmp_path):
    names = ["Cote d'Ivoire", "Macedonia", "Micronesia", "State of Palestine", "Vatican"]
    rows = TRANSCRIPTION.read_text(encoding="utf-8") + "".join(f"{name},0.1,1,0.1,1,0.1,1,10,1,10,1,\n" for name in names)
    (tmp_path / "itu").mkdir()
    (tmp_path / "itu" / "gci-local-indicator-summary.csv").write_text(rows, encoding="utf-8")
    unpinned = {ITU_KEY: LocalSourceFile("synthetic with the original's five uncoded names", "itu/gci-local-indicator-summary.csv", None, "tests")}
    with SSPI(database=db) as sspi:
        with pytest.raises(SourceRequestError, match="is not at"):
            sspi.ingest(["ITU_CYBSEC"], client=LocalFileClient(root=tmp_path / "empty"))  # the default table, no file
        assert sspi.ingest(["ITU_CYBSEC"], client=LocalFileClient(root=tmp_path, files=unpinned)).counts == {"ITU_CYBSEC": 56 + 25}
        assert {"CIV", "MKD", "FSM", "PSE", "VAT"} <= set(sspi.query(datasets=["ITU_CYBSEC"])["country_code"])
        (tmp_path / "itu" / "gci-local-indicator-summary.csv").write_text(rows + "Atlantis,0.1,1,0.1,1,0.1,1,10,1,10,1,\n", encoding="utf-8")
        with pytest.raises(NormalizationError, match="Atlantis"):
            sspi.ingest(["ITU_CYBSEC"], client=LocalFileClient(root=tmp_path, files=unpinned))  # anything else is still refused
        assert len(sspi.query(datasets=["ITU_CYBSEC"])) == 81  # the failed refresh changed nothing
    assert LOCAL_FILES[ITU_KEY].sha256 != hashlib.sha256(TRANSCRIPTION.read_bytes()).hexdigest()  # the default pins the original file


def test_reruns_converge_and_prison_without_data_raises_as_legacy(db, tmp_path):
    servers = Servers()
    with SSPI(database=db) as sspi:
        assert sspi.run("MURDER").written == 0 == sspi.run("CYBSEC").written == sspi.run("SECAPP").written  # never ingested: nothing to score, no error
        with pytest.raises(ImputationError, match="reference data for UNODC_PRIPOP/CHN is empty"):
            sspi.run("PRISON")  # the legacy impute route raised on an empty dataset too
        servers.ingest(sspi, DATASETS, tmp_path)
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        first = counts(db)
        servers.ingest(sspi, DATASETS, tmp_path)  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and counts(db) == first == (297 + 56 + 56 + 112, 484 + 56 + 56 + 217)
