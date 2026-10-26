"""Opt-in: the new UNODC and ITU adapters and PRISON on the ORIGINAL sources,
both kept outside the repository (docs/data-governance-review.md, GOV-3 and
GOV-4), against the pinned legacy code's output on the same files.

    SSPI_UNODC_REAL_DATA=local-data/unodc SSPI_ITU_REAL_DATA=local-data/itu SSPI_FSI_REAL_DATA=local-data/fsi \\
        .venv/bin/python -m pytest -m "unodc_real_data or itu_real_data or fsi_real_data"

The legacy output was generated from the same files by
``generate_public_safety_cases.py --real local-data``. Every file is
checked against the committed ``REAL_DATA.sha256`` of its tier; a missing or
changed file fails. Exact equality throughout; no tolerance.
"""

import hashlib
from collections import Counter

import pytest

from sspi.indicators import compute_indicator, registry
from sspi.ingestion.itu import APPROVED_NAME_CORRECTIONS, normalize_itu_dataset
from sspi.ingestion.fsi import EDITION_SETS, FSIEditions, FSIWorkbook, normalize_fsi_dataset
from sspi.ingestion.localfiles import LOCAL_FILES, LocalFile
from sspi.ingestion.unodc import WORKBOOKS, UNODCWorkbook, normalize_unodc_dataset
from sspi.metadata import CountryCatalog, MetadataCatalog
from tests.golden.parity import OBSERVATION_IDENTITY, assert_parity, observation_record, score_level_records, score_records
from tests.golden.public_safety_real_data import FSI, ITU, UNODC

CATALOG = MetadataCatalog.load()
UNODC_KEY = "data_cts_prisons_and_prisoners_2026-09-30"
ITU_KEY = "gci-local-indicator-summary"


def unodc_observations():
    content = UNODC.read(f"{UNODC_KEY}.xlsx")
    assert hashlib.sha256(content).hexdigest() == WORKBOOKS[UNODC_KEY].sha256
    return normalize_unodc_dataset(CATALOG.dataset("UNODC_PRIPOP"), UNODCWorkbook(UNODC_KEY, WORKBOOKS[UNODC_KEY], WORKBOOKS[UNODC_KEY].sha256, content))


@pytest.mark.unodc_real_data
@pytest.mark.skipif(not UNODC.directory, reason=f"set {UNODC.environment_variable} to {UNODC.guidance}")
def test_unodc_observations_match_the_legacy_collector_and_cleaner_on_the_original_workbook():
    result, golden = unodc_observations(), UNODC.golden("unodc_pripop_cases.json")
    assert_parity("UNODC_PRIPOP observations (original workbook)", [observation_record(o) for o in result.observations], golden["observations"], OBSERVATION_IDENTITY)
    assert [list(s) for s in result.skipped_areas] == golden["skipped_areas"] and result.missing_values == golden["empty_source_values"] == 0
    assert len(result.observations) == 3346 and (min(o.year for o in result.observations), max(o.year for o in result.observations)) == (2003, 2024)
    gbr = {o.year: o.provenance["unweighted_mean_of"] for o in result.observations if o.country_code == "GBR"}
    assert {str(y): r for y, r in gbr.items()} == golden["regional_mean_years"]
    assert gbr[2023] == ["GBR_NI", "GBR_S"] and gbr[2003] == ["GBR_E_W", "GBR_S"]  # PRISON-1: the jurisdictions averaged change by year
    assert sorted(o.year for o in result.observations if o.country_code == "IRQ") == [2021]  # PRISON-4


@pytest.mark.unodc_real_data
@pytest.mark.skipif(not UNODC.directory, reason=f"set {UNODC.environment_variable} to {UNODC.guidance}")
def test_prison_scores_match_both_legacy_routes_on_the_original_workbook():
    golden = UNODC.golden("prison_cases.json")
    result = compute_indicator(registry.get("PRISON"), unodc_observations().observations)
    assert_parity("PRISON observed scores (original workbook)", score_level_records(result.observed_scores), golden["observed_scores"])
    assert_parity("PRISON imputed scores (original workbook)", score_level_records(result.imputed_scores), golden["imputed_scores"])
    assert (len(result.observed_scores), len(result.imputed_scores)) == (3346, 2142) and golden["legacy_output_conflicts"] == {"observed_and_imputed": [], "duplicate_imputed": []}
    (call,) = golden["reference_class"]
    assert (call["country_code"], call["reference_count"], call["mean"]) == ("CHN", 3346, 185.76391641581256)  # PRISON-2
    sspi67 = set(CountryCatalog.load().group("SSPI67").members)
    scored = {(s.country_code, s.year) for s in result.scores}
    assert all((c, y) in scored for c in sspi67 for y in range(2000, 2024))
    assert Counter(s.inputs[0].provenance["imputation_method"] for s in result.imputed_scores) == {"Backward Extrapolation": 964, "Linear Interpolation": 945, "Forward Extrapolation": 209, "ImputeReferenceClassAverage": 24}


@pytest.mark.itu_real_data
@pytest.mark.skipif(not ITU.directory, reason=f"set {ITU.environment_variable} to {ITU.guidance}")
def test_the_original_transcription_legacy_refused_is_normalized_with_the_approved_correction_only():
    """CYBSEC-1. (A) the legacy cleaner leaves five names uncoded and the legacy clean collection refused the whole
    dataset; (B) the new adapter's observations equal the legacy cleaner's own rows with only the approved correction
    applied; (C) CYBSEC equals the legacy compute route's scores on those rows. Canada is not in the file (CYBSEC-3)."""
    golden, scores = ITU.golden("itu_cybsec_cases.json"), ITU.golden("cybsec_cases.json")
    names = ["Cote d'Ivoire", "Macedonia", "Micronesia", "State of Palestine", "Vatican"]
    assert golden["legacy_clean_error"] == "InvalidDocumentFormatError: 'CountryCode' must be 3 characters long (document 87)" and golden["observations"] is None
    assert golden["unmatched_country_names"] == names and len(golden["cleaner_output_before_validation"]) == 968
    assert golden["corrected_source"]["corrections_applied"] == [[n, APPROVED_NAME_CORRECTIONS[n]] for n in names]
    content = ITU.read(f"{ITU_KEY}.csv")
    assert hashlib.sha256(content).hexdigest() == LOCAL_FILES[ITU_KEY].sha256
    result = normalize_itu_dataset(CATALOG.dataset("ITU_CYBSEC"), LocalFile(ITU_KEY, LOCAL_FILES[ITU_KEY], "real", LOCAL_FILES[ITU_KEY].sha256, content))
    assert_parity("ITU_CYBSEC observations (original, approved correction)", [observation_record(o) for o in result.observations], golden["corrected_source"]["observations"], OBSERVATION_IDENTITY)
    assert len(result.observations) == 968 and result.missing_values == golden["empty_source_values"] == 17
    run = compute_indicator(registry.get("CYBSEC"), result.observations)
    assert_parity("CYBSEC scores (original, approved correction)", score_records(run.observed_scores, imputation=False), scores["corrected_source_scores"]["scores"])
    assert scores["scores"] is None  # legacy itself stored no CYBSEC score
    sspi67 = set(CountryCatalog.load().group("SSPI67").members)
    covered = {(s.country_code, s.year) for s in run.scores}
    assert {c for c in sspi67 if not any((c, y) in covered for y in (2014, 2017, 2018, 2020, 2024))} == {"CAN"}
    assert all((c, y) in covered for c in sspi67 - {"CAN"} for y in (2014, 2017, 2018, 2020, 2024))


@pytest.mark.fsi_real_data
@pytest.mark.skipif(not FSI.directory, reason=f"set {FSI.environment_variable} to {FSI.guidance}")
def test_the_original_fsi_workbooks_match_the_legacy_cleaner_with_only_the_approved_repair():
    """SECAPP-1 on the 18 original editions: (A) the pinned cleaner refuses them; (B) the adapter equals the pinned
    cleaner's own rows with only the approved repair; (C) SECAPP equals the legacy compute route on those rows."""
    dataset_case, scores_case = FSI.golden("fsi_secapp_cases.json"), FSI.golden("secapp_cases.json")
    key = "fsi-excel_2006-2023"
    workbooks = tuple(FSIWorkbook(s, s.sha256, FSI.read(s.url.rsplit("/", 1)[1])) for s in EDITION_SETS[key])
    assert all(hashlib.sha256(w.content).hexdigest() == w.source.sha256 for w in workbooks)
    assert dataset_case["legacy_clean_error"] == "InvalidDocumentFormatError: 'DatasetCode' is a required argument (document 0)"
    assert [k for k, _ in dataset_case["legacy_duplicate_identities"]] == ["KOR"] * 18 and len(dataset_case["legacy_unmatched_names"]) == 99
    assert {str(e): v["year_cells"] for e, v in ((int(e), v) for e, v in dataset_case["edition_years"].items())} == {str(y): [str(y)] for y in range(2006, 2024)}
    result = normalize_fsi_dataset(CATALOG.dataset("FSI_SECAPP"), FSIEditions(key, workbooks))
    assert_parity("FSI_SECAPP observations (original workbooks)", [observation_record(o) for o in result.observations], dataset_case["observations"], OBSERVATION_IDENTITY)
    assert len(result.observations) == 3170 and len({o.country_code for o in result.observations}) == 179
    legacy = Counter((r["country_code"], r["year"], r["value"]) for r in dataset_case["cleaner_output_before_validation"])
    untouched = Counter((o.country_code, o.year, o.value) for o in result.observations if "country_code_correction" not in o.provenance)
    assert not untouched - legacy  # every row needing no repair is the pinned cleaner's own row
    corrected = Counter(o.provenance["source_country_name"].strip() for o in result.observations if "country_code_correction" in o.provenance)
    assert sum(corrected.values()) == 118 and corrected["North Korea"] == 18
    run = compute_indicator(registry.get("SECAPP"), result.observations)
    assert_parity("SECAPP scores (original workbooks)", score_records(run.observed_scores, imputation=False), scores_case["scores"])
    sspi67 = set(CountryCatalog.load().group("SSPI67").members)
    covered = {(s.country_code, s.year) for s in run.scores}
    assert {(c, y) for c in sspi67 for y in range(2006, 2024)} - covered == {("ARE", 2006), ("ISL", 2006), ("LUX", 2006)}
