"""CRPTAX, Corporate Tax Rate: the executable legacy formula and impute route.

Compute route (``api/core/sspi/ms/tax/crptax.py``): every clean
``TF_CRPTAX`` row, all years and all areas the cleaner kept, is scored with
``goalpost(TF_CRPTAX, 0, 40)``. A higher rate scores higher: 0 % scores 0,
40 % or more scores 1. The goalposts were read from metadata at runtime and
are declared here so ``check_against`` verifies them. The score unit is the
legacy literal ``Tax Rate``, in both routes.

The dataset is the Tax Foundation's worldwide corporate tax rates, January
2025 edition: the combined statutory corporate income tax rate (central
government plus the average subnational rate, surtaxes included, as the
source defines it), in percent. The source already reports a percentage and
nothing rescales it. A reported 0 % is a value: the cleaner keeps it and it
scores 0. The 2018 static SSPI used central-government rates for some
countries (CRPTAX-1); the executable source is kept.

Impute route, in the legacy order: each country's observed series is
carried backward to 2000, then linearly interpolated across interior gaps
(any year), each step from the observed rows on their own, and the filled
observations are scored with the same formula. There is no forward
extrapolation, no reference class and no country group.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 40
UNIT = "Tax Rate"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target; the legacy route does not extrapolate forward


def score_crptax(TF_CRPTAX):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_crptax`` lambda, identical in the impute route."""
    return goalpost(TF_CRPTAX, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="CRPTAX",
    observed_score=score_crptax,
    imputation=SeriesFillThenScore(score_crptax, SERIES_FILL_YEARS, steps=("backward", "interpolate")),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
