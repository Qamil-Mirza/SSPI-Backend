"""ENRPRI, Primary School Net Enrollment: the executable legacy formula and
impute route.

Compute route (``api/core/sspi/pg/edu/enrpri.py``): every clean
``UIS_ENRPRI`` row, all years and all countries the cleaner kept, is scored
with ``goalpost(UIS_ENRPRI, 80, 100)``. The goalposts were read from
metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``%``, in both routes.

The dataset is the UIS series ``NERT.1.CP``, "Total net enrolment rate,
primary, both sexes (%)": children of official primary age enrolled in
primary *or higher* education, as a percentage, both sexes. It is not a
gross rate and not a plain net rate; the canonical description reads like a
plain net rate (ENRPRI-1). The source already reports a percentage and
nothing divides it. A value above 100 would be clamped by the goalpost
only; the series has none.

Impute route: series fill on the input. Each country's observed series is
carried forward to 2023, carried backward to 2000 and linearly interpolated
across interior gaps, and the filled observations are scored with the same
formula. There is no reference class: the route's China reference-class
line is commented out and stays inactive, so a country with no observation
gets no score. Forward extrapolation starts from the last observation
however old (China's last value is 1997).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 80, 100
UNIT = "%"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target, forward extrapolation target


def score_enrpri(UIS_ENRPRI):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_enrpri`` lambda, identical in the impute route."""
    return goalpost(UIS_ENRPRI, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="ENRPRI",
    observed_score=score_enrpri,
    imputation=SeriesFillThenScore(score_enrpri, SERIES_FILL_YEARS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
