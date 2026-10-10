"""ENRSEC, Lower Secondary Net Enrollment: the executable legacy formula and
impute route.

Compute route (``api/core/sspi/pg/edu/enrsec.py``): every clean
``UIS_ENRSEC`` row, all years and all countries the cleaner kept, is scored
with ``goalpost(UIS_ENRSEC, 70, 100)``. The goalposts were read from
metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``Percent``, in both routes.

The dataset is the UIS series ``NERT.2.CP``, "Total net enrolment rate,
lower secondary, both sexes (%)": lower secondary, not all of secondary, and
a total net rate, not a gross or plain net rate (ENRPRI-1). The source
already reports a percentage and nothing divides it.

Impute route, in the legacy order:

1. series fill on the input: each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated
   across interior gaps;
2. China and Nigeria, hard-coded, each get for every year 2000-2023 the
   flat mean of every clean ``UIS_ENRSEC`` row: every country in the source
   (not SSPI67), every year from the first (not only 2000-2023), unweighted
   (ENRSEC-1).

The union is scored with the same formula. If China or Nigeria ever has an
observed row, legacy would store two values for the same country-years and
no precedence is decided: the strategy raises before anything is written.
Legacy raised on an empty dataset too (no mean to take).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 70, 100
UNIT = "Percent"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets; also the reference-class years
REFERENCE_CLASS_RECIPIENTS = ("CHN", "NGA")  # legacy impute_reference_class_average calls, in order


def score_enrsec(UIS_ENRSEC):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_enrsec`` lambda, identical in the impute route."""
    return goalpost(UIS_ENRSEC, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="ENRSEC",
    observed_score=score_enrsec,
    imputation=SeriesFillThenScore(score_enrsec, SERIES_FILL_YEARS, listed_recipients=REFERENCE_CLASS_RECIPIENTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
