"""YRSEDU, Years of Compulsory Education: the executable legacy formula and
impute route.

Compute route (``api/core/sspi/pg/edu/yrsedu.py``): every clean
``UIS_YRSEDU`` row, all years and all countries the cleaner kept, is scored
with ``goalpost(UIS_YRSEDU, 6, 12)``: six years or fewer scores 0, twelve or
more scores 1. The goalposts were read from metadata at runtime and are
declared here so ``check_against`` verifies them. The score unit is the
legacy literal ``Years``, in both routes.

The dataset is the UIS series ``YEARS.FC.COMP.1T3``, "Number of years of
compulsory primary and secondary education guaranteed in legal frameworks":
a whole number of years, 0 to 13, one value per country and year. A 0 is a
real value (UIS marks it ``NIL``: no compulsory schooling in law), but the
shared UIS cleaner drops every falsy value, so a 0 never reaches scoring.
The years before a country's law then take its first later value through
backward extrapolation, and a 0 after an earlier value leaves no score at
all (YRSEDU-1).

Impute route: backward extrapolation on the input only. Each country's
observed series is carried back from its first observation to 2000; nothing
is carried forward and no gap is interpolated. There is no reference class.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 6, 12
UNIT = "Years"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward extrapolation target; the forward target is unused (no forward step)
SERIES_FILL_STEPS = ("backward",)  # the only step of the legacy impute route


def score_yrsedu(UIS_YRSEDU):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_yrsedu`` lambda, identical in the impute route."""
    return goalpost(UIS_YRSEDU, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="YRSEDU",
    observed_score=score_yrsedu,
    imputation=SeriesFillThenScore(score_yrsedu, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
