"""The Education leaf indicators ENRPRI, ENRSEC, PUPTCH and YRSEDU:
definitions, formulas, goalposts and strategies, ENRSEC's hard-coded
reference class and its collision rule, YRSEDU's backward-only fill and
dropped zeros, and what each does when its dataset is missing. Pure, no
database, no network."""

import pytest

from sspi.errors import ImputationError, UnknownCodeError
from sspi.imputation import REFERENCE_CLASS_AVERAGE, is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.enrpri import score_enrpri
from sspi.indicators.enrsec import score_enrsec
from sspi.indicators.puptch import score_puptch
from sspi.indicators.yrsedu import score_yrsedu
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.ingestion import SUPPORTED_DATASETS
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation, goalpost

EDUCATION = ("ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU")


@pytest.fixture(scope="module")
def catalog():
    return MetadataCatalog.load()


def test_the_executable_education_indicators(catalog):
    assert {(catalog.indicator(c).pillar_code, catalog.indicator(c).category_code) for c in EDUCATION} == {("PG", "EDU")}
    assert {c: registry.get(c).dataset_codes for c in EDUCATION} == {"ENRPRI": ("UIS_ENRPRI",), "ENRSEC": ("UIS_ENRSEC",), "PUPTCH": ("WB_PUPTCH",), "YRSEDU": ("UIS_YRSEDU",)}
    assert {"UIS_ENRPRI", "UIS_ENRSEC", "WB_PUPTCH", "UIS_YRSEDU"} <= set(SUPPORTED_DATASETS)
    for code in EDUCATION:
        registry.get(code).check_against(catalog)


def test_education_is_exactly_the_four_leaf_indicators(catalog):
    assert tuple(i.code for i in catalog.indicators() if i.category_code == "EDU") == ("ENRPRI", "ENRSEC", "PUPTCH", "YRSEDU")
    assert set(EDUCATION) <= set(registry.codes())


def test_formulas_and_goalposts():
    assert score_enrpri(90.0) == goalpost(90.0, 80, 100) == 0.5 and score_enrpri(79.9) == 0.0 and score_enrpri(100.0) == 1.0
    assert score_enrsec(85.0) == goalpost(85.0, 70, 100) == 0.5 and score_enrsec(69.9) == 0.0 and score_enrsec(100.0) == 1.0
    assert score_puptch(24.5) == 0.5 and score_puptch(40) == 0.0 and score_puptch(9) == 1.0  # fewer pupils per teacher is better
    assert score_yrsedu(9) == goalpost(9, 6, 12) == 0.5 and score_yrsedu(6) == score_yrsedu(0) == 0.0 and score_yrsedu(13) == 1.0
    assert {c: (registry.get(c).goalposts, registry.get(c).unit) for c in EDUCATION} == {"ENRPRI": ((80, 100), "%"), "ENRSEC": ((70, 100), "Percent"), "PUPTCH": ((40, 9), "Ratio"), "YRSEDU": ((6, 12), "Years")}


def test_strategies():
    assert registry.get("ENRPRI").imputation == SeriesFillThenScore(score_enrpri, (2000, 2023))
    assert registry.get("ENRSEC").imputation == SeriesFillThenScore(score_enrsec, (2000, 2023), listed_recipients=("CHN", "NGA"))
    assert registry.get("PUPTCH").imputation == SeriesFillThenScore(score_puptch, (2000, 2023))
    assert registry.get("YRSEDU").imputation == SeriesFillThenScore(score_yrsedu, (2000, 2023), steps=("backward",))
    assert {registry.get(c).imputation.steps for c in ("ENRPRI", "ENRSEC", "PUPTCH")} == {("forward", "backward", "interpolate")}


@pytest.mark.parametrize("steps", [(), ("backward", "backward"), ("sideways",)])
def test_series_fill_steps_are_validated(steps):
    with pytest.raises(ImputationError, match="steps must be distinct"):
        SeriesFillThenScore(score_yrsedu, (2000, 2023), steps=steps)


def enrolment(dataset, country, year, value):
    return Observation(dataset, country, year, value, "Percent")


def test_enrsec_reference_class_uses_every_row_unweighted_and_every_target_year():
    rows = [enrolment("UIS_ENRSEC", "AAA", 1990, 60.0), enrolment("UIS_ENRSEC", "AAA", 2010, 80.0), enrolment("UIS_ENRSEC", "BBB", 2015, 100.0)]
    run = compute_indicator(registry.get("ENRSEC"), rows)
    by_country = {}
    for s in run.imputed_scores:
        by_country.setdefault(s.country_code, []).append(s)
    for country in ("CHN", "NGA"):
        assert {s.year for s in by_country[country]} == set(range(2000, 2024))
        assert {s.inputs[0].value for s in by_country[country]} == {80.0}  # (60 + 80 + 100) / 3: a 1990 row counts, rows are not weighted by country
        assert {s.inputs[0].provenance["imputation_method"] for s in by_country[country]} == {REFERENCE_CLASS_AVERAGE}
    assert all(is_imputed(s) for s in run.imputed_scores)


@pytest.mark.parametrize("country", ["CHN", "NGA"])
def test_enrsec_raises_before_scoring_if_a_listed_recipient_gains_data(country):
    rows = [enrolment("UIS_ENRSEC", "AAA", 2010, 80.0), enrolment("UIS_ENRSEC", country, 1995, 50.0)]  # even a pre-2000 row collides
    with pytest.raises(ImputationError, match=rf"\['{country}'\] now have observed UIS_ENRSEC rows"):
        compute_indicator(registry.get("ENRSEC"), rows)


def test_without_their_dataset_enrpri_puptch_and_yrsedu_score_nothing_and_enrsec_raises_as_legacy_did():
    for code in ("ENRPRI", "PUPTCH", "YRSEDU"):
        run = compute_indicator(registry.get(code), ())
        assert run.scores == () and run.unscored == ()
    with pytest.raises(ImputationError, match="reference data for UIS_ENRSEC/CHN is empty"):  # legacy: ValueError("Reference data cannot be empty.")
        compute_indicator(registry.get("ENRSEC"), ())


def test_enrpri_series_fill_has_no_reference_class():
    rows = [enrolment("UIS_ENRPRI", "AAA", 1997, 93.0), enrolment("UIS_ENRPRI", "BBB", 2005, 90.0), enrolment("UIS_ENRPRI", "BBB", 2007, 94.0)]
    run = compute_indicator(registry.get("ENRPRI"), rows, ("AAA", "BBB", "CHN"))
    imputed = {(s.country_code, s.year): s for s in run.imputed_scores}
    assert {y for c, y in imputed if c == "AAA"} == set(range(1998, 2024))  # carried 26 years from 1997; nothing backward (1997 < 2000)
    assert imputed[("BBB", 2006)].inputs[0].value == 92.0 and {y for c, y in imputed if c == "BBB"} == {*range(2000, 2005), 2006, *range(2008, 2024)}
    assert not any(c == "CHN" for c, _ in imputed)  # the commented-out China line stays inactive


def test_yrsedu_only_extrapolates_backward_to_2000():
    rows = [Observation("UIS_YRSEDU", "AAA", 2004, 9.0, "Years"), Observation("UIS_YRSEDU", "AAA", 2008, 12.0, "Years"), Observation("UIS_YRSEDU", "AAA", 2010, 10.0, "Years")]
    run = compute_indicator(registry.get("YRSEDU"), rows)
    assert {s.year for s in run.imputed_scores} == {2000, 2001, 2002, 2003}  # no interpolation of 2005-2007 or 2009, nothing after 2010
    assert {s.inputs[0].value for s in run.imputed_scores} == {9.0} and {s.inputs[0].provenance["imputation_method"] for s in run.imputed_scores} == {"Backward Extrapolation"}
