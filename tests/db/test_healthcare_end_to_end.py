"""The four executable Healthcare leaf indicators on the isolated database,
with the UN SDG API, the World Bank Indicators API and the WHO GHO OData API
served from fixtures by a mock transport. No network.

The GHO responses are the committed synthetic fixtures; WHO extracts are not
distributed with the repository while redistribution rights are open
(docs/data-governance-review.md, GOV-1). The same workflow runs on the real
GHO subsets, kept outside the repository, when ``SSPI_WHO_REAL_DATA`` names
their directory (tests/golden/who_real_data.py). Production ingestion always
reads the GHO API.

    sspi.ingest(["UNSDG_CSTUNT", "WHO_ATBRTH", "WHO_DPTCOV", "WHO_PHYSPC"])
    sspi.run("CSTUNT"), sspi.run("ATBRTH"), sspi.run("DPTCOV"), sspi.run("PHYSPC")
    sspi.query(indicators=["CSTUNT", "ATBRTH", "DPTCOV", "PHYSPC"], countries=["MYS", "AUT", "USA"], years=(2010, 2023))

The workflow test starts from an empty database and ingests exactly the
dataset list of the researcher guide's example (read from the guide, and
checked offline against the definition in
tests/unit/test_researcher_guide_healthcare.py). Stored scores are compared
with the legacy golden files exactly. CSTUNT stores observed scores only, as
legacy production does (production precedence, CSTUNT-4). FAMPLN cannot be
run, and no Healthcare category score exists.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from sspi import SSPI
from sspi.errors import ImputationError
from sspi.facade import INDICATOR_DTYPES
from sspi.ingestion import UNSDGClient, WHOClient, WorldBankClient
from sspi.ingestion.unsdg import PIVOT_DATA_URL
from sspi.ingestion.who import BASE_URL as WHO_URL
from sspi.ingestion.worldbank import BASE_URL as WB_URL
from tests.golden.who_real_data import MARKS as REAL_DATA_MARKS
from tests.golden.who_real_data import real_bytes
from tests.unit.test_researcher_guide_healthcare import documented_datasets, required_datasets

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"
DATASETS = list(documented_datasets())  # what the researcher guide tells a researcher to ingest
INDICATORS = ["CSTUNT", "ATBRTH", "DPTCOV", "PHYSPC"]
GHO_CODES = {"MDG_0000000025": "ATBRTH", "WHS4_100": "DPTCOV", "HWF_0001": "PHYSPC"}
UNSDG_ROWS = json.loads((FIXTURES / "unsdg" / "2_2_1_sample.json").read_text(encoding="utf-8"))["data"]
WB_CONTENT = (FIXTURES / "wb" / "NY.GDP.PCAP.CD_sample.json").read_bytes()
CSTUNT = json.loads((GOLDEN / "cstunt_cases.json").read_text())["verbatim"]


@dataclass(frozen=True, eq=False)  # hashed by identity, for the caches
class WHOData:
    """One set of GHO responses, the legacy golden files generated from them, and what the workflow yields on them."""

    name: str
    fixture: str  # path pattern of a GHO response, {code}
    golden: str  # path pattern of an indicator golden file, {indicator}
    observations: dict[str, int]  # dataset -> canonical observations
    runs: dict[str, tuple[int, int, int]]  # indicator -> observed, imputed, written
    imputed_2023: dict[tuple[str, str], bool]  # (indicator, country) -> the 2023 score is imputed
    austria_doctors_2018: float

    @cache
    def content(self, code):
        return self.read(self.fixture.format(code=code))

    @cache
    def case(self, indicator):
        return json.loads(self.read(self.golden.format(indicator=indicator.lower())))

    def read(self, path):
        return real_bytes(path) if self.name == "real" else (Path(__file__).parents[2] / path).read_bytes()


SYNTHETIC = WHOData(
    "synthetic",
    "tests/fixtures/who/{code}_synthetic.json",
    "tests/golden/{indicator}_synthetic_cases.json",
    {"WHO_ATBRTH": 46, "WHO_DPTCOV": 87, "WHO_PHYSPC": 82},
    {"ATBRTH": (46, 267, 313), "DPTCOV": (87, 0, 87), "PHYSPC": (82, 152, 234)},
    {("ATBRTH", "AUT"): True, ("ATBRTH", "USA"): True, ("PHYSPC", "USA"): True, ("DPTCOV", "AUT"): False},  # AUT reports 2022 and 2024; USA ends 2020 / 2022
    52.4,
)
REAL = WHOData(  # the GHO row subsets of 2026-10-18 (real files, checked against tests/fixtures/who/REAL_DATA.sha256)
    "real",
    "fixtures/{code}_sample.json",
    "golden/{indicator}_cases.json",
    {"WHO_ATBRTH": 148, "WHO_DPTCOV": 197, "WHO_PHYSPC": 202},
    {"ATBRTH": (148, 262, 410), "DPTCOV": (197, 0, 197), "PHYSPC": (202, 96, 298)},
    {("ATBRTH", "AUT"): True, ("ATBRTH", "USA"): False, ("PHYSPC", "USA"): True, ("DPTCOV", "AUT"): False},  # Austria reports 2022 and 2024
    95.42,  # PHYSPC-1
)


@pytest.fixture(params=[SYNTHETIC, pytest.param(REAL, marks=REAL_DATA_MARKS)], ids=lambda data: data.name)
def who(request):
    return request.param


class Servers:
    """One mock transport serving the UN SDG pivot rows, the World Bank response and the three GHO responses."""

    def __init__(self, who):
        self.requests = []
        self.who = who

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if url == PIVOT_DATA_URL and request.url.params["indicator"] == "2.2.1":
            self.requests.append("UNSDG 2.2.1")
            return httpx.Response(200, json={"size": 500, "totalElements": len(UNSDG_ROWS), "totalPages": 1, "pageNumber": 1, "attributes": [], "dimensions": [], "data": UNSDG_ROWS})
        if url == WB_URL + "NY.GDP.PCAP.CD":
            self.requests.append("WB NY.GDP.PCAP.CD")
            return httpx.Response(200, content=WB_CONTENT, headers={"content-type": "application/json"})
        if url.startswith(WHO_URL) and url.removeprefix(WHO_URL) in GHO_CODES and not request.url.params:
            self.requests.append(f"WHO {url.removeprefix(WHO_URL)}")
            return httpx.Response(200, content=self.who.content(url.removeprefix(WHO_URL)), headers={"content-type": "application/json; odata.metadata=minimal"})
        self.requests.append(str(request.url))
        return httpx.Response(404)

    def clients(self):
        http = httpx.Client(transport=httpx.MockTransport(self))
        return {"UNSDG": UNSDGClient(http=http, sleep=lambda s: None), "WB": WorldBankClient(http=http), "WHO": WHOClient(http=http)}


def legacy_scores(who):
    """(indicator, country, year) -> (score, unit, imputed), from the legacy golden files: CSTUNT's compute route only
    (production precedence, CSTUNT-4), both routes for the WHO indicators."""
    scores = {("CSTUNT", r["country_code"], r["year"]): (r["score"], r["unit"], False) for r in CSTUNT["observed_scores"]}
    for indicator in GHO_CODES.values():
        case = who.case(indicator)
        scores |= {(indicator, r["country_code"], r["year"]): (r["score"], r["unit"], key == "imputed_scores") for key in ("observed_scores", "imputed_scores") for r in case.get(key, [])}
    return scores


def counts(db):
    with db.transaction() as session:
        return tuple(session.execute(text("SELECT (SELECT count(*) FROM observation), (SELECT count(*) FROM indicator_score)")).one())


def stored(db, indicator):
    with db.transaction() as session:
        return session.execute(text("SELECT country_code, year, score, unit, imputed, inputs, provenance FROM indicator_score WHERE indicator_code = :i ORDER BY 1, 2"), {"i": indicator}).all()


def test_healthcare_workflow_from_an_empty_database(db, who):
    assert counts(db) == (0, 0)  # a fresh database: nothing ingested, nothing scored
    assert DATASETS == list(required_datasets()) == ["UNSDG_CSTUNT", "WHO_ATBRTH", "WHO_DPTCOV", "WHO_PHYSPC"]
    servers = Servers(who)
    with SSPI(database=db) as sspi:
        ingestion = sspi.ingest(DATASETS, client=servers.clients())
        assert sspi.query(indicators=INDICATORS).empty  # ingest() never runs an indicator
        fetched = list(servers.requests)
        runs = {code: sspi.run(code) for code in INDICATORS}
        assert servers.requests == fetched  # run() never ingests
        healthcare = sspi.query(indicators=INDICATORS, countries=["MYS", "AUT", "USA"], years=(2010, 2023))
        everything = sspi.query(indicators=INDICATORS, include_inputs=True, include_provenance=True)
        doctors = sspi.query(datasets=["WHO_PHYSPC"], countries=["AUT"], years=(2018, 2018), include_provenance=True)
        stunting = sspi.query(datasets=["UNSDG_CSTUNT"], countries=["MYS"], years=(2019, 2019), include_provenance=True)

    # one UN SDG request (one page here), one GHO request per indicator
    assert servers.requests == ["UNSDG 2.2.1", "WHO MDG_0000000025", "WHO WHS4_100", "WHO HWF_0001"]
    assert ingestion.counts == {"UNSDG_CSTUNT": 450, **who.observations}

    counted = {code: (len(r.observed_scores), len(r.imputed_scores), r.written) for code, r in runs.items()}
    assert counted == {"CSTUNT": (450, 0, 450), **who.runs}
    assert {(r.indicator_code, r.country_code, r.year): (r.score, r.unit, r.imputed) for r in everything.itertuples()} == legacy_scores(who)

    # the researcher-facing frame: four leaf indicators, three countries, 2010-2023; Austria has no stunting estimate and,
    # with nothing imputed (CSTUNT-4), no CSTUNT score; no category score
    assert {c: str(t) for c, t in healthcare.dtypes.items()} == INDICATOR_DTYPES and set(healthcare["indicator_code"]) == set(INDICATORS)
    assert len(healthcare) == 3 * 3 * 14 + 2 * 14
    frame = {(r.indicator_code, r.country_code, r.year): r for r in healthcare.itertuples()}
    assert {(indicator, country): bool(frame[(indicator, country, 2023)].imputed) for indicator, country in who.imputed_2023} == who.imputed_2023
    observed = {(c, y): r for (i, c, y), r in frame.items() if i == "CSTUNT"}
    assert not any(observed[("MYS", y)].imputed or observed[("USA", y)].imputed for y in range(2010, 2024))  # every year a modelled estimate
    assert not any(c == "AUT" for c, _ in observed)  # no estimate, no prediction (CSTUNT-4)

    # what is stored: the series and dimensions with each observation; the regression in the score's provenance
    (row,) = stunting.itertuples()
    assert row.unit == "PER_POP_U5" and row.provenance["source_series"] == "SH_STA_STNT" and row.provenance["source_dimensions"] == {"sex": "BOTHSEX", "age": "<5Y"}
    (row,) = doctors.itertuples()
    assert (row.value, row.unit) == (who.austria_doctors_2018, "Doctors per 10000") and row.provenance["source_indicator"] == "HWF_0001"
    assert row.provenance["source_url"] == WHO_URL + "HWF_0001" and row.provenance["spatial_dim_type"] == "COUNTRY"
    scored = {(r.country_code, r.year): r for r in everything.itertuples() if r.indicator_code == "CSTUNT"}
    assert not any(r.imputed for r in scored.values()) and not any(c == "AUT" for c, _ in scored)
    switzerland = {(r.year, r.imputed, r.score) for r in everything.itertuples() if (r.indicator_code, r.country_code) == ("ATBRTH", "CHE")}
    mean = who.case("ATBRTH")["reference_class"]["mean"]
    assert switzerland == {(y, True, (mean - 80) / 20) for y in range(2000, 2024)}  # ATBRTH-1


def test_missing_datasets_behave_as_legacy_and_reruns_converge(db, who):
    servers = Servers(who)
    with SSPI(database=db) as sspi:
        assert sspi.run("CSTUNT").written == 0  # nothing ingested: observed-only (CSTUNT-4), nothing to score, no error
        with pytest.raises(ImputationError, match="reference data for WHO_ATBRTH/CHE is empty"):
            sspi.run("ATBRTH")  # nothing to average for the five listed countries: legacy raised too
        assert sspi.run("DPTCOV").written == 0 and sspi.run("PHYSPC").written == 0  # never ingested: nothing to score, no error
        assert counts(db) == (0, 0)  # nothing written by any failed or empty run
        sspi.ingest(["UNSDG_CSTUNT"], client=servers.clients())
        assert sspi.run("CSTUNT").written == 450  # no GDP series needed (the legacy route needed it and raised without it)
        sspi.ingest(DATASETS, client=servers.clients())
        for code in INDICATORS:
            sspi.run(code)
        snapshot = {code: stored(db, code) for code in INDICATORS}
        sspi.ingest(DATASETS, client=servers.clients())  # re-ingesting replaces the observations with the same rows
        for code in INDICATORS:
            sspi.run(code)
        assert {code: stored(db, code) for code in INDICATORS} == snapshot and {code: len(rows) for code, rows in snapshot.items()} == {"CSTUNT": 450, **{code: written for code, (_, _, written) in who.runs.items()}}
