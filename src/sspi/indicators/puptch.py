"""PUPTCH, Primary Education Pupil to Teacher Ratio: the executable legacy
formula and impute route.

Compute route (``api/core/sspi/pg/edu/puptch.py``): every clean
``WB_PUPTCH`` row, all years and all countries the cleaner kept, is scored
with ``goalpost(WB_PUPTCH, 40, 9)``. Lower is better: 40 or more pupils per
teacher scores 0, 9 or fewer scores 1. The goalposts were read from
metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``Ratio``, in both routes.

The dataset is the World Bank WDI indicator ``SE.PRM.ENRL.TC.ZS``,
"Pupil-teacher ratio, primary": pupils enrolled in primary school per
primary teacher, all teachers (not only trained or qualified ones), as a
plain ratio. WDI republishes it from the UNESCO Institute for Statistics.
The value is never inverted or rescaled; the goalposts run downward. A zero
would mean no pupils and the shared World Bank cleaner drops it, as it drops
every falsy value; the source has none.

Impute route: series fill on the input. Each country's observed series is
carried forward to 2023, carried backward to 2000 and linearly interpolated
across interior gaps, and the filled observations are scored with the same
formula. There is no reference class and no country group: a country with
no observation gets no score, and forward extrapolation starts from the
last observation however old (PUPTCH-1).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 40, 9
UNIT = "Ratio"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target


def score_puptch(WB_PUPTCH):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_puptch`` lambda, identical in the impute route."""
    return goalpost(WB_PUPTCH, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="PUPTCH",
    observed_score=score_puptch,
    imputation=SeriesFillThenScore(score_puptch, SERIES_FILL_YEARS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
