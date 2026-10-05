"""ISHRAT: formula, goalposts, missing data and the registered definition. No database."""

import pytest

from sspi.imputation import is_imputed
from sspi.indicators import compute_indicator, registry
from sspi.indicators.ishrat import DEFINITION, LOWER_GOALPOST, UPPER_GOALPOST, UNIT, score_ishrat
from sspi.metadata import MetadataCatalog
from sspi.scoring import Observation, UnscoredReason, goalpost

TOP, BOTTOM = "WID_NINCSH_PRETAX_P90P100", "WID_NINCSH_PRETAX_P0P50"


def obs(dataset, country, year, value):
    return Observation(dataset, country, year, value, f"share; percentile {'p90p100' if dataset == TOP else 'p0p50'}; sptincj992")


def test_formula_is_bottom_half_share_over_top_tenth_share():
    assert score_ishrat(0.4, 0.2) == goalpost(0.2 / 0.4, 0.2, 1.25) == (0.5 - 0.2) / 1.05
    assert score_ishrat(WID_NINCSH_PRETAX_P90P100=0.3653, WID_NINCSH_PRETAX_P0P50=0.1921) == (0.1921 / 0.3653 - 0.2) / 1.05


@pytest.mark.parametrize(("top", "bottom", "expected"), [(0.5, 0.1, 0.0), (0.6, 0.05, 0.0), (0.2, 0.25, 1.0), (0.2, 0.3, 1.0), (0.4, 0.29, (0.29 / 0.4 - 0.2) / 1.05)])
def test_goalposts_clamp_the_ratio(top, bottom, expected):
    """Ratio 0.2 or below scores 0; 1.25 or above scores 1."""
    assert score_ishrat(top, bottom) == expected


def test_definition_matches_the_canonical_metadata():
    catalog = MetadataCatalog.load()
    DEFINITION.check_against(catalog)
    indicator = catalog.indicator("ISHRAT")
    assert registry.get("ISHRAT") is DEFINITION
    assert DEFINITION.dataset_codes == tuple(indicator.dataset_codes) == (TOP, BOTTOM)  # legacy parameter order
    assert DEFINITION.goalposts == (LOWER_GOALPOST, UPPER_GOALPOST) == (indicator.lower_goalpost, indicator.upper_goalpost) == (0.2, 1.25)
    assert (indicator.pillar_code, indicator.category_code) == ("MS", "NEQ")
    assert DEFINITION.unit == UNIT and DEFINITION.imputation is None and DEFINITION.score_dependencies == () and DEFINITION.observation_filter is None


def test_complete_groups_score_and_nothing_is_imputed():
    result = compute_indicator(DEFINITION, [obs(TOP, "MYS", 2020, 0.4), obs(BOTTOM, "MYS", 2020, 0.2), obs(TOP, "AUT", 2024, 0.3), obs(BOTTOM, "AUT", 2024, 0.24)])
    assert [(s.country_code, s.year, s.score, s.unit) for s in result.scores] == [("AUT", 2024, (0.24 / 0.3 - 0.2) / 1.05, UNIT), ("MYS", 2020, (0.5 - 0.2) / 1.05, UNIT)]
    assert result.imputed_scores == () and not any(is_imputed(s) for s in result.scores) and all(s.provenance == {} for s in result.scores)


def test_a_country_year_with_one_share_stays_unscored():
    result = compute_indicator(DEFINITION, [obs(TOP, "MYS", 2020, 0.4), obs(BOTTOM, "MYS", 2020, 0.2), obs(TOP, "MYS", 2021, 0.41), obs(BOTTOM, "AUT", 2021, 0.24)])
    assert [(s.country_code, s.year) for s in result.scores] == [("MYS", 2020)]
    assert sorted((u.country_code, u.year, u.reason, u.details) for u in result.unscored) == [
        ("AUT", 2021, UnscoredReason.MISSING_DATASETS, (TOP,)),
        ("MYS", 2021, UnscoredReason.MISSING_DATASETS, (BOTTOM,)),
    ]
