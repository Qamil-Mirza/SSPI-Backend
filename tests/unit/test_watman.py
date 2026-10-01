"""WATMAN indicator: registry entry, formula, the strategy's declared needs and
its hard-coded legacy recipient behaviour on handcrafted data. Parity with
the legacy routes is in tests/golden/test_golden_watman.py."""

import pytest

from sspi.errors import ImputationError
from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.strategy import ImputationStrategy
from sspi.indicators.watman import DEFINITION, REFERENCE_CLASS_RECIPIENTS, SYNTHETIC_CWUEFF_RECIPIENTS, SYNTHETIC_METHOD, WatmanImputation, score_watman, synthetic_cwueff
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation


def cwueff(country, year, value, **prov):
    return Observation("UNSDG_CWUEFF", country, year, value, "Percent", prov)


def wtstrs(country, year, value):
    return Observation("UNSDG_WTSTRS", country, year, value, "PERCENT")


def wuseff(country, year, value):
    return Observation("UNSDG_WUSEFF", country, year, value, "USD/m3")


def test_registry_entry(metadata=MetadataCatalog.load()):
    definition = registry.get("WATMAN")
    assert definition is DEFINITION and isinstance(definition.imputation, WatmanImputation) and isinstance(definition.imputation, ImputationStrategy)
    assert definition.dataset_codes == ("UNSDG_CWUEFF", "UNSDG_WTSTRS") and definition.auxiliary_datasets == ("UNSDG_WUSEFF",)
    assert definition.recipient_group is None and definition.goalposts is None and definition.unit == "Index"
    definition.check_against(metadata)
    assert (metadata.indicator("WATMAN").pillar_code, metadata.indicator("WATMAN").category_code) == ("SUS", "LND")


@pytest.mark.parametrize("c, w, expected", [(-20, 100, 0.0), (50, 0, 1.0), (15, 50, 0.5), (-30, 120, 0.0), (80, -5, 1.0)])
def test_formula_and_goalposts(c, w, expected):
    assert score_watman(c, w) == expected  # CWUEFF (-20, 50); WTSTRS inverted (100, 0); both clamped


def test_compute_route_scores_every_complete_group_without_year_filter():
    result = compute_indicator(DEFINITION, [cwueff("MYS", 1999, 10), wtstrs("MYS", 1999, 50), cwueff("MYS", 2030, 10), wtstrs("MYS", 2030, 50), wtstrs("AUT", 2010, 5)], auxiliary=[])
    assert [(s.country_code, s.year) for s in result.observed_scores] == [("MYS", 1999), ("MYS", 2030)]


def test_series_are_extrapolated_to_2000_2023_without_interpolation():
    observations = [cwueff("MYS", 2010, 10), cwueff("MYS", 2012, 20), wtstrs("MYS", 2010, 5), wtstrs("MYS", 2012, 5)]
    result = compute_indicator(DEFINITION, observations, auxiliary=[])
    imputed_years = sorted(s.year for s in result.imputed_scores)
    assert imputed_years == list(range(2000, 2010)) + list(range(2013, 2024))  # 2011 is NOT filled: legacy did not interpolate
    # 2011 never becomes a group; SGP's unconditional reference-class series has no WTSTRS partner here
    assert sorted({(u.country_code, u.year) for u in result.unscored}) == [("SGP", y) for y in range(2000, 2024)]
    methods = {o.provenance["imputation_method"] for s in result.imputed_scores for o in s.inputs}
    assert methods == {"Backward Extrapolation", "Forward Extrapolation"}


def test_listed_countries_get_a_synthetic_series_from_wuseff():
    assert "CHE" in SYNTHETIC_CWUEFF_RECIPIENTS and "SGP" in REFERENCE_CLASS_RECIPIENTS
    aux = [wuseff("CHE", y, 100.0 + 10 * (y - 2012)) for y in range(2012, 2024)]  # no 2000-2005 values: no derived CWUEFF
    observations = [wtstrs("CHE", y, 10.0) for y in range(2012, 2024)] + [cwueff("MYS", 2006, 5.0), wtstrs("MYS", 2006, 1.0)]
    result = compute_indicator(DEFINITION, observations, auxiliary=aux)
    che = {s.year: s for s in result.imputed_scores if s.country_code == "CHE"}
    assert sorted(che) == list(range(2000, 2024))
    series = synthetic_cwueff("CHE", aux)
    assert sorted(o.year for o in series) == list(range(2000, 2024)) and all(o.provenance["imputation_method"] == SYNTHETIC_METHOD for o in series)
    # extrapolated WUSEFF is flat at 100 for 2000-2011, so the baseline is 100 and the baseline years are 0% change
    by_year = {o.year: o for o in series}
    assert all(by_year[y].value == 0.0 for y in range(2000, 2006)) and by_year[2023].value == ((210.0 - 100.0) / 100.0) * 100  # legacy arithmetic, verbatim
    assert by_year[2000].provenance["source_imputed"] is True and by_year[2000].provenance["source_imputation_method"] == "Backward Extrapolation"
    assert by_year[2015].provenance["source_imputed"] is False


def test_listed_country_without_wuseff_rows_is_skipped_and_non_listed_countries_get_nothing():
    aux = [wuseff("ALB", y, 5.0) for y in range(2010, 2024)]  # ALB is not listed: no synthetic series despite no baseline
    result = compute_indicator(DEFINITION, [wtstrs("ALB", 2010, 1.0), wtstrs("DEU", 2010, 1.0), cwueff("MYS", 2010, 1.0), wtstrs("MYS", 2010, 2.0)], auxiliary=aux)
    assert {s.country_code for s in result.imputed_scores} == {"MYS"}
    assert sorted({(u.country_code, u.year) for u in result.unscored}) == [(c, y) for c in ("ALB", "DEU", "SGP") for y in range(2000, 2024)]


def test_singapore_receives_the_mean_of_all_canonical_cwueff():
    observations = [cwueff("MYS", 2010, 10.0), cwueff("USA", 2020, 30.0), wtstrs("MYS", 2010, 1.0), wtstrs("USA", 2020, 1.0), wtstrs("SGP", 2010, 50.0)]
    result = compute_indicator(DEFINITION, observations, auxiliary=[])
    sgp = {s.year: s for s in result.imputed_scores if s.country_code == "SGP"}
    assert sorted(sgp) == list(range(2000, 2024))
    value = next(o for o in sgp[2010].inputs if o.dataset_code == "UNSDG_CWUEFF")
    assert value.value == 20.0 and value.provenance["imputation_method"] == "ImputeReferenceClassAverage" and value.provenance["reference_observation_count"] == 2


def test_singapore_with_canonical_cwueff_keeps_it_and_gets_no_reference_class_row():
    """Canonical-first policy, WATMAN-3: the literal legacy route would duplicate SGP and fail here."""
    observations = [cwueff("SGP", 2010, 10.0), wtstrs("SGP", 2010, 1.0), cwueff("MYS", 2010, 90.0), wtstrs("MYS", 2010, 1.0)]
    result = compute_indicator(DEFINITION, observations, auxiliary=[])
    sgp = {s.year: s for s in result.scores if s.country_code == "SGP"}
    assert sorted(sgp) == list(range(2000, 2024)) and is_imputed(sgp[2010]) is False
    values = {next(o for o in s.inputs if o.dataset_code == "UNSDG_CWUEFF").value for s in sgp.values()}
    assert values == {10.0}  # extrapolated canonical value everywhere; never the reference mean (50.0)


def test_synthetic_recipient_with_canonical_cwueff_still_fails_like_legacy():
    """No policy has been decided for the twelve synthetic-series countries (WATMAN-3)."""
    aux = [wuseff("CHE", y, 100.0) for y in range(2000, 2024)]
    observations = [cwueff("CHE", 2010, 1.0), wtstrs("CHE", 2010, 1.0)]
    with pytest.raises(ImputationError, match="CHE.*WATMAN-3"):
        compute_indicator(DEFINITION, observations, auxiliary=aux)


def test_only_scores_with_an_imputed_input_are_kept():
    observations = [cwueff("MYS", y, 1.0) for y in range(2000, 2024)] + [wtstrs("MYS", y, 1.0) for y in range(2000, 2024)]
    result = compute_indicator(DEFINITION, observations, auxiliary=[])
    assert len(result.observed_scores) == 24 and result.imputed_scores == () and all(not is_imputed(s) for s in result.observed_scores)
