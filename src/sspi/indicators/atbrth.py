"""ATBRTH, Attended Births by Skilled Personnel: the executable legacy formula
and impute route.

The dataset is WHO Global Health Observatory indicator ``MDG_0000000025``,
"Births attended by skilled health personnel (%)": live births attended by
skilled health personnel (doctors, nurses or midwives) as a percentage of
all live births in the same period, mostly from household surveys, compiled
in the UNICEF/WHO joint database. The legacy cleaner keeps every country row
as served; the value is ``NumericValue``.

Compute route (``api/core/sspi/pg/hlc/atbrth.py``): every clean
``WHO_ATBRTH`` row, all years and all countries, is scored with
``goalpost(WHO_ATBRTH, 80, 100)``: 80 % or less scores 0, 100 % scores 1.
The goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy literal ``%``.

Impute route, in the legacy order:

1. series fill on the input: each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated
   across interior gaps;
2. Switzerland, the United Kingdom, the Netherlands, Belgium and Sweden,
   hard-coded in that order, each get for every year 2000-2023 the flat
   mean of every clean ``WHO_ATBRTH`` row: every country in the source,
   every year, unweighted (ATBRTH-1).

The union is scored with the same formula and the same unit ``%``. If one of
the five ever has an observed row, legacy would store two values for the
same country-years and no precedence is decided: the strategy raises before
anything is written. Legacy raised on an empty dataset too (no mean to
take).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 80, 100
UNIT = "%"  # legacy literal of both routes
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets; also the reference-class years
REFERENCE_CLASS_RECIPIENTS = ("CHE", "GBR", "NLD", "BEL", "SWE")  # legacy impute_reference_class_average calls, in order


def score_atbrth(WHO_ATBRTH):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_atbrth`` lambda, identical in the impute route."""
    return goalpost(WHO_ATBRTH, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="ATBRTH",
    observed_score=score_atbrth,
    imputation=SeriesFillThenScore(score_atbrth, SERIES_FILL_YEARS, listed_recipients=REFERENCE_CLASS_RECIPIENTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
