"""COLBAR, Collective Bargaining Coverage: the executable legacy formula and
impute route.

Compute route (``api/core/sspi/ms/wen/colbar.py``): every clean
``ILO_COLBAR`` row (ILO dataflow ``DF_ILR_CBCT_NOC_RT``, a percentage), all
years and all areas the cleaner kept, is scored with
``goalpost(ILO_COLBAR, 0, 100)``. The goalposts were read from metadata at
runtime and are declared here so ``check_against`` verifies them. The score
unit is the legacy literal ``%``.

Impute route: series fill on the inputs. Each area's observed series is
carried forward to 2023, carried backward to 2000 and linearly interpolated
across interior gaps, and the filled observations are scored with the same
formula. The legacy impute route labelled its scores ``Tax Rate``; that is
reproduced (COLBAR-2).

The methodology file lists ten countries under "Imputations" with no text,
and the legacy route carries the comment "Implement Country by Country Value
Imputations Here" with nothing after it. Nothing is implemented for them, so
a country the ILO series does not cover has no COLBAR score (COLBAR-1).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 100
UNIT = "%"  # legacy compute-route literal
IMPUTED_UNIT = "Tax Rate"  # legacy impute-route literal (COLBAR-2)
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target


def score_colbar(ILO_COLBAR):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_colbar`` lambda, identical in the impute route."""
    return goalpost(ILO_COLBAR, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="COLBAR",
    observed_score=score_colbar,
    imputation=SeriesFillThenScore(score_colbar, SERIES_FILL_YEARS, unit=IMPUTED_UNIT),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
