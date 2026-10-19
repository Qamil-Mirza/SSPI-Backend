"""Opt-in: parity for ATBRTH, DPTCOV and PHYSPC on REAL WHO GHO data, kept
outside the repository.

Skipped unless ``SSPI_WHO_REAL_DATA`` names the directory holding the real
files (by convention ``local-data/who``, which git ignores):

    SSPI_WHO_REAL_DATA=local-data/who .venv/bin/python -m pytest -m who_real_data

WHO extracts are not distributed with the repository while redistribution
rights are open (docs/data-governance-review.md, GOV-1); the default,
committed parity tests run on synthetic fixtures (test_golden_who.py). This
module is the real-data evidence, unchanged in substance: the GHO row
subsets of 2026-10-18 (``fixtures/<code>_sample.json``) and the golden files
the pinned legacy code produced from them (``golden/who_*_cases.json``,
``golden/{atbrth,dptcov,physpc}_cases.json``), every comparison exact. Each
file is checked first against ``tests/fixtures/who/REAL_DATA.sha256``, which
is committed; a missing or changed file fails, never skips (who_real_data.py).
"""

from collections import Counter
from functools import cache

import pytest

from sspi.errors import ImputationError
from sspi.imputation import REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import atbrth, compute_indicator, dptcov, physpc, registry
from sspi.ingestion.runner import SUPPORTED_DATASETS, fetch_and_normalize, resolve_datasets
from sspi.ingestion.who import BASE_URL, GHOIndicatorData
from sspi.metadata import CountryCatalog, MetadataCatalog
from sspi.scoring import Observation
from tests.golden.parity import (
    INTENTIONAL_DIVERGENCES,
    OBSERVATION_IDENTITY,
    PENDING_METHODOLOGY_DECISIONS,
    assert_parity,
    assert_pinned,
    legacy_inconsistency,
    observation_record,
    score_level_records,
)
from tests.golden.who_real_data import MARKS, checksums, real_bytes, real_json

pytestmark = MARKS

CATALOG = MetadataCatalog.load()
INDICATORS = {"ATBRTH": "MDG_0000000025", "DPTCOV": "WHS4_100", "PHYSPC": "HWF_0001"}
UNITS = {"ATBRTH": ("Percent", "%"), "DPTCOV": ("Percent", "%"), "PHYSPC": ("Doctors per 10000", "Rate")}  # dataset unit, score unit
GOALPOSTS = {"ATBRTH": (80, 100), "DPTCOV": (75, 100), "PHYSPC": (0, 70)}
FORMULAS = {"ATBRTH": atbrth.score_atbrth, "DPTCOV": dptcov.score_dptcov, "PHYSPC": physpc.score_physpc}
RECIPIENTS = ("CHE", "GBR", "NLD", "BEL", "SWE")


class FixtureClient:
    """Stands in for ``WHOClient``; counts fetches."""

    def __init__(self):
        self.fetches = []

    def fetch_indicator(self, code):
        self.fetches.append(code)
        payload = real_json(f"fixtures/{code}_sample.json")
        return GHOIndicatorData(code, BASE_URL + code, payload["@odata.context"], 1, tuple(payload["value"]))


@cache
def normalized(indicator):
    client = FixtureClient()
    ((dataset, result),), _ = fetch_and_normalize(resolve_datasets([f"WHO_{indicator}"], CATALOG), client, metadata=CATALOG)
    assert dataset.code == f"WHO_{indicator}" and client.fetches == [INDICATORS[indicator]]
    return result


@cache
def run(indicator):
    return compute_indicator(registry.get(indicator), normalized(indicator).observations)


def scores(indicator):
    return {(s.country_code, s.year): s for s in run(indicator).scores}


def dataset_case(indicator):
    return real_json(f"golden/who_{indicator.lower()}_cases.json")


def indicator_case(indicator):
    return real_json(f"golden/{indicator.lower()}_cases.json")


# --- the files ------------------------------------------------------------------------------------


@pytest.mark.parametrize("relative", sorted(checksums()))
def test_every_real_file_is_the_validated_one(relative):
    real_bytes(relative)


@pytest.mark.parametrize("indicator", INDICATORS)
def test_the_real_golden_files_come_from_the_pinned_commit_and_name_their_fixture(indicator):
    code = INDICATORS[indicator]
    for case in (dataset_case(indicator), indicator_case(indicator)):
        assert_pinned(case, indicator)
        assert case["generated_from"]["fixture"] == f"tests/fixtures/who/{code}_sample.json"  # where the subset lived when the legacy code ran on it


# --- facts ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", INDICATORS)
def test_golden_files_record_the_legacy_facts(indicator):
    definition, case, source = registry.get(indicator), indicator_case(indicator), CATALOG.dataset(f"WHO_{indicator}").source
    code = INDICATORS[indicator]
    assert (source.organization_code, source.query_code, source.organization_series_code, source.dimensions) == ("WHO", code, code, None)
    assert dataset_case(indicator)["source_indicator"] == code and f"WHO_{indicator}" in SUPPORTED_DATASETS
    lower, upper = GOALPOSTS[indicator]
    assert case["goalposts"] == [lower, upper] == list(definition.goalposts) and case["formula"] == f"goalpost(WHO_{indicator}, {lower}, {upper})"
    assert case["methodology_score_function"] == f"Score = goalpost(WHO_{indicator}, {lower}, {upper})"
    assert case["unit"] == definition.unit == UNITS[indicator][1] and CATALOG.dataset(f"WHO_{indicator}").unit == UNITS[indicator][0]
    assert case["impute_route_exists"] is definition.imputes is (indicator != "DPTCOV")
    assert definition.dataset_codes == (f"WHO_{indicator}",) and definition.auxiliary_datasets == () and definition.score_dependencies == ()
    assert dataset_case(indicator)["datasources"] == ["None"]  # no DataSourceDim on any row


@pytest.mark.parametrize("indicator", INDICATORS)
def test_legacy_output_is_consistent_so_exact_parity_is_required(indicator):
    assert legacy_inconsistency(indicator_case(indicator)) is None
    if indicator != "DPTCOV":
        assert indicator_case(indicator)["legacy_output_conflicts"] == {"observed_and_imputed": [], "duplicate_imputed": []}
    assert not any(code == indicator for code, _ in list(INTENTIONAL_DIVERGENCES) + list(PENDING_METHODOLOGY_DECISIONS))


# --- datasets -------------------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", INDICATORS)
def test_observations_match_the_legacy_cleaner_exactly(indicator):
    result, case = normalized(indicator), dataset_case(indicator)
    assert_parity(f"WHO_{indicator} observations", [observation_record(o) for o in result.observations], case["observations"], OBSERVATION_IDENTITY)
    assert sorted(list(a) for a in result.skipped_areas) == case["skipped_areas"] and result.missing_values == case["no_data_rows"] == 0
    assert {o.unit for o in result.observations} == {UNITS[indicator][0]}
    assert {o.provenance["source_indicator"] for o in result.observations} == {INDICATORS[indicator]} and not any("source_dimensions" in o.provenance for o in result.observations)


def test_aggregates_are_skipped_and_the_value_is_the_unrounded_number():
    assert {code for code, _ in normalized("ATBRTH").skipped_areas} == {"GLOBAL", "EUR"}
    assert {kind for _, kind in normalized("DPTCOV").skipped_areas} == {"GLOBAL", "REGION", "WORLDBANKINCOMEGROUP"}
    rows = real_json("fixtures/MDG_0000000025_sample.json")["value"]
    rounded = [r for r in rows if r["SpatialDimType"] == "COUNTRY" and r["Value"] != str(r["NumericValue"])]
    assert rounded  # "Value" is a display string ("96" for 95.7); the legacy cleaner read NumericValue
    by_id = {(o.country_code, o.year): o for o in normalized("ATBRTH").observations}
    assert all(by_id[(r["SpatialDim"], r["TimeDim"])].value == r["NumericValue"] for r in rounded)


# --- observed scores ------------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", INDICATORS)
def test_observed_scores_match_the_compute_route(indicator):
    result = run(indicator)
    assert_parity(f"{indicator} observed scores", score_level_records(result.observed_scores), indicator_case(indicator)["observed_scores"])
    assert not any(is_imputed(s) for s in result.observed_scores) and {s.unit for s in result.observed_scores} == {UNITS[indicator][1]}
    assert len(result.observed_scores) == {"ATBRTH": 148, "DPTCOV": 197, "PHYSPC": 202}[indicator]


def test_goalpost_boundaries_and_extremes():
    a, d, p = scores("ATBRTH"), scores("DPTCOV"), scores("PHYSPC")
    assert a[("IRQ", 2007)].inputs[0].value == 80.0 and a[("IRQ", 2007)].score == 0.0  # at the lower goalpost
    assert a[("ETH", 2000)].inputs[0].value == 6.0 and a[("ETH", 2000)].score == 0.0  # the smallest value
    assert a[("PLW", 2014)].inputs[0].value == 100.0 and a[("PLW", 2014)].score == 1.0
    assert d[("ARG", 2024)].inputs[0].value == 75.0 and d[("ARG", 2024)].score == 0.0
    assert d[("UKR", 2016)].inputs[0].value == 19.0 and d[("UKR", 2000)].inputs[0].value == 99.0 and d[("UKR", 2000)].score == 0.96
    assert max(o.value for o in normalized("DPTCOV").observations) == 99.0  # WUENIC caps coverage at 99 %: no DPTCOV score reaches 1
    assert p[("LBR", 2008)].inputs[0].value == 0.13 and p[("LBR", 2008)].score == 0.13 / 70
    assert p[("CUB", 2021)].inputs[0].value == 95.42 and p[("CUB", 2021)].score == 1.0  # above the upper goalpost: clamped


def test_physpc_austria_2018_is_scored_as_published():
    """PHYSPC-1: WHO's series has Austria at 95.42 doctors per 10,000 in 2018 (51.56 in 2017, 52.91 in 2019)."""
    p = scores("PHYSPC")
    assert [p[("AUT", y)].inputs[0].value for y in (2017, 2018, 2019)] == [51.56, 95.42, 52.91]
    assert p[("AUT", 2018)].score == 1.0 and not is_imputed(p[("AUT", 2018)])


# --- imputation -----------------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", ["ATBRTH", "PHYSPC"])
def test_imputed_scores_match_the_impute_route(indicator):
    result, case = run(indicator), indicator_case(indicator)
    assert_parity(f"{indicator} imputed scores", score_level_records(result.imputed_scores), case["imputed_scores"])
    assert all(is_imputed(s) for s in result.imputed_scores) and case["imputed_unit"] == [UNITS[indicator][1]]
    assert len(result.imputed_scores) == {"ATBRTH": 262, "PHYSPC": 96}[indicator]


def test_dptcov_imputes_nothing():
    assert run("DPTCOV").imputed_scores == () and registry.get("DPTCOV").imputation is None
    d = scores("DPTCOV")
    assert min(y for c, y in d if c == "SSD") == 2011  # South Sudan has no score before its first estimate


@pytest.mark.parametrize("indicator", INDICATORS)
def test_final_identity_set_classification_and_provenance(indicator):
    result, case = run(indicator), indicator_case(indicator)
    legacy = {(r["country_code"], r["year"]) for key in ("observed_scores", "imputed_scores") for r in case.get(key, [])}
    identities = [(s.country_code, s.year) for s in result.scores]
    assert len(identities) == len(set(identities)) and set(identities) == legacy and result.unscored == ()
    assert all(s.provenance == {} for s in result.scores)  # imputation is on the input, never on the score
    for s in result.imputed_scores:
        (source,) = s.inputs
        assert source.provenance["imputed"] is True and s.score == FORMULAS[indicator](source.value)


def test_atbrth_series_fill_and_reference_class():
    result, case = run("ATBRTH"), indicator_case("ATBRTH")
    methods = Counter(s.inputs[0].provenance["imputation_method"] for s in result.imputed_scores)
    assert methods == {REFERENCE_CLASS_AVERAGE: 120, "Linear Interpolation": 64, "Backward Extrapolation": 45, "Forward Extrapolation": 33}
    observations = normalized("ATBRTH").observations
    mean = sum(o.value for o in observations) / len(observations)  # every country, every year, unweighted
    reference = case["reference_class"]
    assert (tuple(reference["recipients"]), reference["years"], reference["reference_count"], reference["mean"]) == (RECIPIENTS, [2000, 2023], 148, mean)
    assert atbrth.REFERENCE_CLASS_RECIPIENTS == RECIPIENTS
    a = scores("ATBRTH")
    for country in RECIPIENTS:
        theirs = [s for s in result.scores if s.country_code == country]
        assert {s.year for s in theirs} == set(range(2000, 2024)) and all(is_imputed(s) for s in theirs)
        assert {(s.inputs[0].value, s.inputs[0].provenance["reference_observation_count"], s.score) for s in theirs} == {(mean, 148, atbrth.score_atbrth(mean))}
    assert a[("TCA", 2000)].inputs[0].provenance["anchor_year"] == 2020 and a[("TCA", 2023)].inputs[0].provenance["anchor_year"] == 2020  # one value, both ways
    assert a[("AUT", 2023)].inputs[0].provenance["imputation_method"] == "Linear Interpolation"  # 2022 and 2024 reported
    assert a[("SVN", 2023)].inputs[0].provenance["anchor_year"] == 2012  # carried eleven years
    assert ("AUT", 2024) in a and not any(y > 2023 for (c, y), s in a.items() if is_imputed(s))


def test_atbrth_raises_when_a_listed_recipient_has_data():
    """No precedence is decided between a hard-coded recipient's mean and its own data (ATBRTH-1)."""
    gbr = Observation("WHO_ATBRTH", "GBR", 2019, 99.1, "Percent", {})
    with pytest.raises(ImputationError, match=r"\['GBR'\] now have observed WHO_ATBRTH rows"):
        compute_indicator(registry.get("ATBRTH"), (*normalized("ATBRTH").observations, gbr))


def test_physpc_series_fill():
    result = run("PHYSPC")
    methods = Counter(s.inputs[0].provenance["imputation_method"] for s in result.imputed_scores)
    assert methods == {"Linear Interpolation": 49, "Backward Extrapolation": 33, "Forward Extrapolation": 14}
    p = scores("PHYSPC")
    assert [y for (c, y), s in sorted(p.items()) if c == "MCO" and is_imputed(s) and y < 2000] == list(range(1993, 2000))  # a 1992-2011 gap: interpolation before 2000 too
    assert p[("CAN", 2000)].inputs[0].provenance["anchor_year"] == 2018  # Canada's series starts in 2018 and is carried back eighteen years
    assert p[("USA", 2023)].inputs[0].provenance["anchor_year"] == 2022 and p[("NRU", 2023)].inputs[0].provenance["anchor_year"] == 2015
    assert min(y for (c, y) in p) == 1990 and not any(y > 2023 for (c, y), s in p.items() if is_imputed(s))  # observed from 1990, no year filter


# --- missing data ---------------------------------------------------------------------------------


def test_empty_datasets_behave_as_legacy():
    assert indicator_case("ATBRTH")["empty_dataset"] == {"observed_scores": [], "imputed_scores": None, "legacy_impute_error": "ValueError: Reference data cannot be empty."}
    with pytest.raises(ImputationError, match="reference data for WHO_ATBRTH/CHE is empty"):
        compute_indicator(registry.get("ATBRTH"), ())
    assert indicator_case("PHYSPC")["empty_dataset"] == {"observed_scores": [], "imputed_scores": [], "legacy_impute_error": None}
    assert indicator_case("DPTCOV")["empty_dataset"] == {"observed_scores": [], "imputed_scores": None, "legacy_impute_error": None}
    for indicator in ("DPTCOV", "PHYSPC"):
        empty = compute_indicator(registry.get(indicator), ())
        assert empty.scores == () and empty.unscored == ()


def test_the_listed_recipients_are_sspi67_members_without_who_data_in_the_fixture():
    sspi67 = set(CountryCatalog.load().group("SSPI67").members)
    assert set(RECIPIENTS) <= sspi67 and not {o.country_code for o in normalized("ATBRTH").observations} & set(RECIPIENTS)
