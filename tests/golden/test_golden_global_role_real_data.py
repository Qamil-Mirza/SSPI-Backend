"""Opt-in: SIPRI_ARMEXP, ARMEXP and RDFUND on the ORIGINAL source answers of
2026-10-26, kept outside the repository, against the pinned legacy code's
output on the same answers (untouched, and with only the approved
corrections); the legacy MILEXP cleaner on SIPRI's original
military-expenditure API answer (characterization); MILEXP's approved source,
SIPRI's revised workbook (``SIPRI-Milex-data-1949-2025_v1.2.xlsx``, revised
27 April 2026), read from the tier's directory as a configured local copy,
against an independent reading and the pinned legacy routes on the same rows;
and the comparison of the two editions.

    SSPI_SIPRI_REAL_DATA=local-data/sipri SSPI_UNSDG_REAL_DATA=local-data/unsdg \\
        .venv/bin/python -m pytest -m "sipri_real_data or unsdg_real_data"

The legacy output was generated from the same files by
``generate_global_role_cases.py --real local-data``. Every file is checked
against the committed ``REAL_DATA.sha256`` of its tier; a missing or changed
file fails. Exact equality throughout; no tolerance.
"""

import dataclasses
import hashlib
import json
from collections import Counter
from functools import cache

import pytest

from sspi.errors import ImputationError
from sspi.imputation import is_imputed
from sspi.indicators import armexp, compute_indicator, registry
from sspi.ingestion.sipri import (
    QUERIES,
    SIPRIClient,
    SIPRIResponse,
    normalize_sipri_dataset,
)
from sspi.ingestion.unsdg import normalize_unsdg_dataset
from sspi.metadata import CountryCatalog, MetadataCatalog
from sspi.scoring import score_indicator
from tests.golden.parity import (
    OBSERVATION_IDENTITY,
    assert_parity,
    observation_record,
    score_level_records,
)
from tests.golden.public_safety_real_data import PrivateTier

SIPRI = PrivateTier("SSPI_SIPRI_REAL_DATA", "sipri", "the directory of the original SIPRI answers (local-data/sipri)")
UNSDG = PrivateTier("SSPI_UNSDG_REAL_DATA", "unsdg", "the directory of the full UN SDG 9.5.1 and 9.5.2 responses (local-data/unsdg)")
CATALOG = MetadataCatalog.load()
SSPI67 = set(CountryCatalog.load().group("SSPI67").members)


@cache
def arms():
    return normalize_sipri_dataset(CATALOG.dataset("SIPRI_ARMEXP"), SIPRIResponse("armstransfers", QUERIES["armstransfers"], SIPRI.read("armexp_response_2026-10-26.json")))


@cache
def rd_observations():
    out = []
    for code, name in (("UNSDG_RDPGDP", "9.5.1_2026-10-26.json"), ("UNSDG_NRSRCH", "9.5.2_2026-10-26.json")):
        out.extend(normalize_unsdg_dataset(CATALOG.dataset(code), json.loads(UNSDG.read(name))).observations)
    return tuple(out)


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_armexp_observations_and_observed_scores_match_legacy_on_the_original_answer():
    """ARMEXP-4: the legacy cleaner's rows with only the approved table; untouched, it dropped exactly the 8 added rows."""
    corrected, legacy, golden = SIPRI.golden("sipri_armexp_corrected_cases.json"), SIPRI.golden("sipri_armexp_cases.json"), SIPRI.golden("armexp_cases.json")
    result = arms()
    assert_parity("SIPRI_ARMEXP observations (original answer)", [observation_record(o) for o in result.observations], corrected["observations"], OBSERVATION_IDENTITY)
    untouched = [o for o in result.observations if "country_code_correction" not in o.provenance]
    assert_parity("SIPRI_ARMEXP observations, untouched legacy cleaner (original answer)", [observation_record(o) for o in untouched], legacy["observations"], OBSERVATION_IDENTITY)
    added = sorted((o.country_code, o.year, o.value, o.provenance["source_country_name"]) for o in result.observations if "country_code_correction" in o.provenance)
    assert added == [("BIH", 2002, 9.0, "Bosnia-Herzegovina"), ("BIH", 2010, 0.0, "Bosnia-Herzegovina"), ("BIH", 2011, 14.0, "Bosnia-Herzegovina"), ("BIH", 2013, 3.0, "Bosnia-Herzegovina"),
                     ("BIH", 2022, 2.0, "Bosnia-Herzegovina"), ("BIH", 2023, 7.0, "Bosnia-Herzegovina"), ("BRN", 2011, 24.0, "Brunei"), ("BRN", 2016, 12.0, "Brunei")]
    assert len(corrected["legacy_dropped_rows"]) == 8 and corrected["legacy_matcher_results"] == {"Brunei": "Brunei", "Bosnia-Herzegovina": "Bosnia-Herzegovina"}
    assert (len(result.observations), len(untouched), len({o.country_code for o in result.observations})) == (1577, 1569, 110)
    assert len({(o.country_code, o.year) for o in result.observations}) == 1577  # no identity held twice
    assert not {"Brunei", "Bosnia-Herzegovina"} & {n for _, n in result.skipped_areas} and {"House of Representatives (Libya)*", "African Union**"} <= {n for _, n in result.skipped_areas}
    observed = score_indicator(result.observations, "ARMEXP", registry.get("ARMEXP").observed_score, "Expenditure")
    assert_parity("ARMEXP observed scores (original answer)", score_level_records(observed.scored), corrected["observed_scores"])
    assert_parity("ARMEXP observed scores, untouched rows (original answer)", score_level_records([s for s in observed.scored if s.country_code not in ("BRN", "BIH")]), golden["observed_scores"])


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_armexp_runs_observed_only_where_the_legacy_impute_route_failed():
    """ARMEXP-2: legacy refused the whole imputation on the United Arab Emirates and kept its observed scores; the
    approved observed-only execution stores exactly those (and the 8 of ARMEXP-4), and the preserved legacy route still
    fails the same way on the legacy cleaner's own rows."""
    golden, corrected = SIPRI.golden("armexp_cases.json"), SIPRI.golden("sipri_armexp_corrected_cases.json")
    assert golden["legacy_impute_error"] == "InvalidDocumentFormatError: Duplicate dataset document found (document 0)" and golden["imputed_scores"] == []
    assert sorted({o.year for o in arms().observations if o.country_code == "ARE"})[:3] == [1990, 1995, 1996]
    result = compute_indicator(registry.get("ARMEXP"), arms().observations)
    assert_parity("ARMEXP observed scores, observed-only run (original answer)", score_level_records(result.observed_scores), corrected["observed_scores"])
    assert result.imputed_scores == () and result.unscored == () and len(result.observed_scores) == 1577
    assert {(s.country_code, s.year): s.score for s in result.scores if s.country_code in ("BRN", "BIH")} == {
        ("BIH", 2002): 0.982, ("BIH", 2010): 1.0, ("BIH", 2011): 0.972, ("BIH", 2013): 0.994, ("BIH", 2022): 0.996, ("BIH", 2023): 0.986, ("BRN", 2011): 0.952, ("BRN", 2016): 0.976}
    held = {(s.country_code, s.year) for s in result.scores if s.country_code in SSPI67 and 2000 <= s.year <= 2023}
    assert len(held) == 847 and len({c for c, _ in held}) == 59 and sorted(SSPI67 - {c for c, _ in held}) == ["BGD", "DZA", "ETH", "IRQ", "ISL", "KEN", "KWT"]
    with pytest.raises(ImputationError, match=r"\['ARE'\] now have observed SIPRI_ARMEXP rows"):
        compute_indicator(dataclasses.replace(registry.get("ARMEXP"), imputation=armexp.LEGACY_IMPUTATION), [o for o in arms().observations if "country_code_correction" not in o.provenance])


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_milexp_legacy_cleaner_misdates_every_country_on_the_original_answer():
    """MILEXP-1, MILEXP-2: offsets of 10 or 11 years; fractions scaled by 100 only below 1."""
    golden = SIPRI.golden("milexp_cases.json")
    assert golden["share_of_gdp_header"][2] == "1990.0" and golden["share_of_gdp_header"][-1] == "2024.0" and golden["request"]["json"]["yearList"] == [1990, 2024]
    shifts = Counter()
    for row in golden["alignment"]:
        published = {int(y): v for y, v in row["published"].items()}
        stored = {int(y): v for y, v in row["stored"].items()}
        if not stored or row["name"] == "Korea, North":
            continue
        candidates = [k for k in (10, 11) if all((y - k) in published and published[y - k] not in ("...", "xxx", ". .") and (float(published[y - k]) * 100 if float(published[y - k]) < 1 else float(published[y - k])) == v for y, v in stored.items())]
        shifts[candidates[0] if candidates else None] += 1
    assert shifts == {11: 110, 10: 51, None: 1}
    gdr = next(r for r in golden["alignment"] if r["name"] == "German Democratic Republic")
    assert gdr["country_code"] == "COD" and set(gdr["published"].values()) <= {"xxx", "..."}  # the None: the legacy "democratic republic" rule, nothing stored from it
    belarus = next(r for r in golden["alignment"] if r["name"] == "Belarus")
    assert float(belarus["published"]["1997"]) == 18.322455972209678 and belarus["stored"]["2008"] == 18.322455972209678  # a published 1832% kept as 18.3%
    kuwait = next(r for r in golden["alignment"] if r["name"] == "Kuwait")
    assert float(kuwait["published"]["1991"]) == 1.173498232086904 and kuwait["stored"]["2002"] == 1.173498232086904  # 117% of GDP stored as 1.17%
    assert golden["iceland"]["imputed_years"] == list(range(2000, 2024)) and golden["iceland"]["observed_rows"] == []


@pytest.mark.unsdg_real_data
@pytest.mark.skipif(not UNSDG.directory, reason=f"set {UNSDG.environment_variable} to {UNSDG.guidance}")
def test_rdfund_matches_both_legacy_routes_on_the_full_un_sdg_responses():
    golden = UNSDG.golden("rdfund_cases.json")
    result = compute_indicator(registry.get("RDFUND"), rd_observations())
    assert_parity("RDFUND observed scores (full responses)", score_level_records(result.observed_scores), golden["observed_scores"])
    assert_parity("RDFUND imputed scores (full responses)", score_level_records(result.imputed_scores), golden["imputed_scores"])
    observed_pass = score_indicator(rd_observations(), "RDFUND", registry.get("RDFUND").observed_score, "Index")
    assert sorted([u.country_code, u.year] for u in observed_pass.unscored) == golden["incomplete_identities"]
    assert (len(result.observed_scores), len(golden["incomplete_identities"]), len(result.imputed_scores)) == (1719, 567, 1763)
    assert golden["legacy_output_conflicts"] == {"observed_and_imputed": [], "duplicate_imputed": []} and golden["legacy_impute_error"] is None


@pytest.mark.unsdg_real_data
@pytest.mark.skipif(not UNSDG.directory, reason=f"set {UNSDG.environment_variable} to {UNSDG.guidance}")
def test_rdfund_sspi67_coverage():
    result = compute_indicator(registry.get("RDFUND"), rd_observations())
    held = {(s.country_code, s.year): s for s in result.scores if s.country_code in SSPI67 and 2000 <= s.year <= 2023}
    observed = sum(1 for s in held.values() if not is_imputed(s))
    assert (len(held), observed) == (1584, 1109)


WORKBOOK_KEY = "SIPRI-Milex-data-1949-2025_v1.2"


@cache
def milex_workbook():
    """The pinned workbook from the configured local copy (the tier's directory), checksum-verified by the client."""
    with SIPRIClient(local_workbook_directory=SIPRI.directory) as client:
        workbook = client.fetch(WORKBOOK_KEY)
    return workbook, normalize_sipri_dataset(CATALOG.dataset("SIPRI_MILEXP"), workbook)


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_milexp_b_workbook_observations_on_the_revised_workbook():
    """B: the backend's reading of SIPRI's revised workbook against the generator's independent reading (not legacy
    output: the legacy collector read the API)."""
    workbook, result = milex_workbook()
    golden = SIPRI.golden("milexp_workbook_cases.json")
    assert workbook.source.sha256 == hashlib.sha256(workbook.content).hexdigest() == "6cc3a30b1064f9f02e60236667eef82e08cad42910ce630909d004ad2c398a9d"
    assert workbook.origin.startswith("local copy: ") and workbook.origin.endswith("SIPRI-Milex-data-1949-2025_v1.2.xlsx")
    assert_parity("SIPRI_MILEXP observations (revised workbook)", [observation_record(o) for o in result.observations], golden["observations"], OBSERVATION_IDENTITY)
    assert [n for _, n in result.skipped_areas] == golden["skipped_names"] == ["Czechoslovakia", "German Democratic Republic", "Yugoslavia", "USSR", "European Union", "Yemen, North"]
    assert result.missing_values == golden["missing_cells"] == 661
    values = {(o.country_code, o.year): o for o in result.observations}
    assert (len(values), len({c for c, _ in values}), min(y for _, y in values), max(y for _, y in values)) == (5219, 167, 1990, 2024)
    assert set(SSPI67) <= {c for c, _ in values}
    assert (values[("KWT", 1991)].value, values[("KWT", 1991)].provenance["source_value"]) == (117.34982320869041, "1.173498232086904")  # kept above 100%
    assert [k for k in values if values[k].value >= 100] == [("KWT", 1991)]
    belarus = {y: values[("BLR", y)].value for y in range(1992, 2014)}
    assert belarus[1992] == 2.210173027030375 and belarus[2000] == 1.373838971861861 and max(belarus.values()) < 10  # the revised figures, as published
    zeros = sorted({c for (c, _), o in values.items() if o.value == 0.0})
    assert zeros == ["CRI", "ISL", "PAN"] and {values[(c, 2010)].provenance["source_notes"] for c in zeros} == {"37", "86", "43"}
    assert not [y for y in range(2018, 2024) if ("VEN", y) in values]  # "..." in the workbook: missing, not taken from the API
    assert {(o.country_code, o.provenance["source_country_name"]) for o in result.observations if "country_code_correction" in o.provenance} == {("BRN", "Brunei"), ("COG", "Congo, Republic"), ("CIV", "Cote d'Ivoire"), ("GMB", "Gambia, The")}
    corrected = Counter(o.country_code for o in result.observations if "country_code_correction" in o.provenance)
    assert corrected == {"BRN": 35, "GMB": 31, "CIV": 29, "COG": 22}  # Korea, North and the GDR have no value in 1990-2024


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_milexp_c_legacy_scoring_on_the_workbook_and_the_approved_iceland_correction():
    """C: the pinned legacy routes on the same observations. The compute route is reproduced exactly. The impute route
    stored, for Iceland 2000-2023, an imputed fixed zero beside each published zero; under the approved storage and
    provenance correction (MILEXP-5) the registered definition keeps the observations and stores no second score.
    Every other imputed score is the legacy route's exactly."""
    _, result = milex_workbook()
    golden = SIPRI.golden("milexp_workbook_cases.json")
    assert golden["legacy_impute_error"] is None and len(golden["imputed_scores"]) == 424
    conflicts = {tuple(i) for i in golden["legacy_output_conflicts"]["observed_and_imputed"]}
    assert conflicts == {("ISL", y) for y in range(2000, 2024)} and golden["legacy_output_conflicts"]["duplicate_imputed"] == []
    assert golden["iceland"] == {"observed_years": list(range(1990, 2025)), "imputed_years": list(range(2000, 2024))}
    run = compute_indicator(registry.get("MILEXP"), result.observations)
    assert_parity("MILEXP observed scores (revised workbook)", score_level_records(run.observed_scores), golden["observed_scores"])
    assert_parity("MILEXP imputed scores, the decided rule applied to legacy (revised workbook)", score_level_records(run.imputed_scores), [s for s in golden["imputed_scores"] if (s["country_code"], s["year"]) not in conflicts])
    assert (len(run.observed_scores), len(run.imputed_scores)) == (5219, 400)
    identities = [(s.country_code, s.year) for s in run.scores]
    assert len(identities) == len(set(identities)) == 5619
    iceland = {s.year: s for s in run.scores if s.country_code == "ISL"}
    assert sorted(iceland) == list(range(1990, 2025)) and not any(is_imputed(s) for s in iceland.values()) and {s.score for s in iceland.values()} == {1.0}
    assert {(s.inputs[0].value, s.inputs[0].provenance["source_value"], s.inputs[0].provenance["source_notes"]) for s in iceland.values()} == {(0.0, "0", "86")}
    held = {(s.country_code, s.year): s for s in run.scores if s.country_code in SSPI67 and 2000 <= s.year <= 2023}
    assert (len(held), sum(not is_imputed(s) for s in held.values())) == (1584, 1562)
    scores = {(s.country_code, s.year): round(s.score, 4) for s in run.scores if s.country_code in ("MYS", "AUT", "USA") and s.year in (2010, 2018, 2023)}
    assert scores == {("MYS", 2010): 0.702, ("MYS", 2018): 0.808, ("MYS", 2023): 0.804, ("AUT", 2010): 0.8347, ("AUT", 2018): 0.8502, ("AUT", 2023): 0.8275, ("USA", 2010): 0.0192, ("USA", 2018): 0.3392, ("USA", 2023): 0.3413}


@pytest.mark.sipri_real_data
@pytest.mark.skipif(not SIPRI.directory, reason=f"set {SIPRI.environment_variable} to {SIPRI.guidance}")
def test_the_api_and_the_revised_workbook_are_different_editions():
    """The comparison report (recorded by the generator from the two original files) and its summary: the workbook
    replaces the API answer as a whole; nothing is mixed."""
    comparison = SIPRI.golden("milexp_workbook_cases.json")["api_comparison"]
    assert comparison["api_title"].endswith("1990-2024     © SIPRI 2025") and comparison["workbook_title"].endswith("1949–2025  © SIPRI 2026")
    kinds = Counter(d["kind"] for d in comparison["differences"])
    assert (comparison["identical"], kinds) == (4927, {"differ": 196, "workbook only": 96, "api only": 6})
    differ = Counter(d["name"] for d in comparison["differences"] if d["kind"] == "differ")
    assert len(differ) == 18 and differ["Belarus"] == 30 and sum(differ.values()) == 196
    assert {d["name"] for d in comparison["differences"] if d["kind"] == "workbook only"} == {"Costa Rica", "Iceland", "Panama", "Zimbabwe"}
    assert {(d["name"], d["year"]) for d in comparison["differences"] if d["kind"] == "api only"} == {("Venezuela", y) for y in range(2018, 2024)}
    belarus = {d["year"]: (float(d["api"]), d["workbook"]) for d in comparison["differences"] if d["name"] == "Belarus" and 1992 <= d["year"] <= 2013}
    ratios = [a / w for a, w in belarus.values()]
    assert len(belarus) == 22 and 141 < min(ratios) < 142 and 2475 < max(ratios) < 2476  # the withdrawn API values: no fixed factor
    kuwait = [d for d in comparison["differences"] if d["name"] == "Kuwait"]
    assert kuwait == []  # Kuwait 1991 is identical in both editions
