"""DPTCOV, Infant DTP Vaccine Coverage: the executable legacy formula.

The dataset is WHO Global Health Observatory indicator ``WHS4_100``,
"Diphtheria tetanus toxoid and pertussis third-dose (DTP3) immunization
coverage among 1-year-olds (%) (WUENIC)": the WHO/UNICEF estimate of the
share of surviving infants who received the third dose of a DTP-containing
vaccine in a given year, built from administrative reports and surveys,
capped at 99 % and revised back through the series with each annual round.
It is the third dose (DTP3), not the first. The methodology text describes a
survey measure of children aged 12-23 months instead (DPTCOV-1).

The legacy compute route (``api/core/sspi/pg/hlc/dptcov.py``) scores every
clean ``WHO_DPTCOV`` row, all years and all countries, with::

    goalpost(WHO_DPTCOV, 75, 100)

75 % or less scores 0, 100 % scores 1 (the source never exceeds 99). The
goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy literal
``%``.

Legacy DPTCOV has no impute route. Nothing is imputed: a country is scored
only in the years WHO and UNICEF publish an estimate.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 75, 100
UNIT = "%"  # legacy compute-route literal


def score_dptcov(WHO_DPTCOV):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_dptcov`` lambda."""
    return goalpost(WHO_DPTCOV, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="DPTCOV",
    observed_score=score_dptcov,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
