"""AIRPOL, Urban Air Pollution: the executable legacy formula and impute route.

Compute route (``api/core/sspi/sus/nrg/airpol.py``): every clean
``UNSDG_AIRPOL`` row, all years and all countries the cleaner kept, is
scored with ``goalpost(UNSDG_AIRPOL, 40, 0)``: lower is better. The
goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy literal
``Index``.

The dataset is SDG 11.6.2, series ``EN_ATM_PM25``, the ``ALLAREA`` location
slice: population-weighted annual mean PM2.5 over the whole country. The
indicator's name and description speak of PM2.5 and PM10 in cities
(AIRPOL-1 in docs/methodology-conflicts.md).

Impute route, on *scores*: each country's earliest observed score is
carried back to 2000 and its latest forward to 2023 (legacy
``extrapolate_backward`` / ``extrapolate_forward`` on the indicator
documents; no interpolation). The source starts in 2010, so every score for
2000-2009 is the 2010 score (AIRPOL-2). Each SSPI67 member with no observed
score at all then receives, for 2000-2023, the mean of every observed score
of every country and year (legacy ``impute_reference_class_average``).
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, LEGACY_RECIPIENT_GROUP, IndicatorDefinition
from sspi.indicators.strategy import ExtrapolateScores
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 40, 0


def score_airpol(UNSDG_AIRPOL):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_airpol`` lambda."""
    return goalpost(UNSDG_AIRPOL, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="AIRPOL",
    observed_score=score_airpol,
    imputation=ExtrapolateScores(
        forward_to=LEGACY_IMPUTATION_YEARS[1],
        backward_to=LEGACY_IMPUTATION_YEARS[0],
        recipient_group=LEGACY_RECIPIENT_GROUP,
        reference_years=LEGACY_IMPUTATION_YEARS,
    ),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
