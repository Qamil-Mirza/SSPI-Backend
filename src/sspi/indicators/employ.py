"""EMPLOY, Participation in Paid Employment: the executable legacy formula
and impute route.

Compute route (``api/core/sspi/ms/wen/employ.py``): every clean
``ILO_EMPLOY_TO_POP`` row, all years and all areas the cleaner kept, is
scored with ``goalpost(ILO_EMPLOY_TO_POP, 50, 95)``. The goalposts were read
from metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``Percentage``.

The dataset is the ILO employment-to-population ratio, both sexes, ages
15-64 (dataflow ``DF_EMP_DWAP_SEX_AGE_RT``), requested from 2000 on. The
indicator's own description speaks of ages 25-54, and the indicator was
called LFPART (labour force participation) before it was renamed; see
EMPLOY-1 in docs/methodology-conflicts.md.

Impute route: series fill on the inputs. Each area's observed series is
carried forward to 2023, carried backward to 2000 and linearly interpolated
across interior gaps, and the filled observations are scored with the same
formula. There is no reference class: an area with no observation gets no
score. The legacy impute route labelled its scores ``Tax Rate``, a different
unit literal from the compute route's; that is reproduced (EMPLOY-2).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 50, 95
UNIT = "Percentage"  # legacy compute-route literal
IMPUTED_UNIT = "Tax Rate"  # legacy impute-route literal (EMPLOY-2)
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target


def score_employ(ILO_EMPLOY_TO_POP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_employ`` lambda, identical in the impute route."""
    return goalpost(ILO_EMPLOY_TO_POP, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="EMPLOY",
    observed_score=score_employ,
    imputation=SeriesFillThenScore(score_employ, SERIES_FILL_YEARS, unit=IMPUTED_UNIT),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
