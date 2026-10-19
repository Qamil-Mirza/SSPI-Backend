"""PHYSPC, Physicians per 10,000: the executable legacy formula and impute
route.

The dataset is WHO Global Health Observatory indicator ``HWF_0001``,
"Medical doctors (per 10,000)": generalist and specialist medical
practitioners and medical doctors not further defined (ISCO-08 221, 2211,
2212), per 10,000 population, from the National Health Workforce Accounts
reported by member states (population denominators from the UN World
Population Prospects). The value is used as published, per 10,000: the
legacy cleaner converts nothing.

Compute route (``api/core/sspi/pg/hlc/physpc.py``): every clean
``WHO_PHYSPC`` row, all years from 1990 and all countries, is scored with
``goalpost(WHO_PHYSPC, 0, 70)``: no doctors scores 0, 70 or more per 10,000
scores 1. The goalposts were read from metadata at runtime and are declared
here so ``check_against`` verifies them. The score unit is the legacy
literal ``Rate``.

Impute route: each country's observed series is carried forward to 2023,
carried backward to 2000 and linearly interpolated across every interior
gap, wherever it lies (a gap before 2000 is filled too), each step applied
to the observed rows on their own; the filled rows are scored with the same
formula and unit. Every country in the dataset is treated; there is no
hard-coded recipient.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 70
UNIT = "Rate"  # legacy literal of both routes
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets


def score_physpc(WHO_PHYSPC):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_physpc`` lambda, identical in the impute route."""
    return goalpost(WHO_PHYSPC, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="PHYSPC",
    observed_score=score_physpc,
    imputation=SeriesFillThenScore(score_physpc, SERIES_FILL_YEARS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
