"""PRISON, Incarceration Rates: the executable legacy formula and impute
route.

The dataset is UNODC's Crime Trends Survey series "Persons held" in prisons,
total (all sexes, ages and categories), as a rate per 100,000 population,
read from the data portal workbook "Prisons and prisoners"
(:mod:`sspi.ingestion.unodc`). The United Kingdom reports as three
jurisdictions; the legacy cleaner stored for ``GBR`` their unweighted mean,
not a population-weighted rate (PRISON-1). Iraq reports as two units and is
not combined (PRISON-4).

Compute route (``api/core/sspi/pg/saf/prison.py``): every clean row, all
years and all countries, is scored with ``goalpost(UNODC_PRIPOP, 540, 40)``.
Lower is better: 40 or fewer prisoners per 100,000 scores 1, 540 or more
scores 0. The goalposts were read from metadata at runtime and are declared
here so ``check_against`` verifies them. The score unit is the legacy
literal ``Prisoners per 100,000 population``, in both routes.

Impute route, in the legacy order:

1. series fill on the input: each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated
   across interior gaps, each step from the observed rows on their own
   (PRISON-3);
2. China, hard-coded, gets for every year 2000-2023 the flat mean of every
   clean ``UNODC_PRIPOP`` row: every area in the workbook (not SSPI67),
   every year, unweighted (PRISON-2).

The union is scored with the same formula. If China ever has an observed
row, its series fill and its reference-class rows overlap: the legacy
route then failed ("Duplicate dataset document found") and stored no
imputed PRISON score for any country. No precedence is decided, so the
strategy raises before anything is written (PRISON-2). Legacy raised on an
empty dataset too (no mean to take).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 540, 40
UNIT = "Prisoners per 100,000 population"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets; also the reference-class years
SERIES_FILL_STEPS = ("forward", "backward", "interpolate")  # the legacy route's order
REFERENCE_CLASS_RECIPIENTS = ("CHN",)  # the legacy impute_reference_class_average call


def score_prison(UNODC_PRIPOP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_prison`` lambda, identical in the impute route."""
    return goalpost(UNODC_PRIPOP, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="PRISON",
    observed_score=score_prison,
    imputation=SeriesFillThenScore(score_prison, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS, listed_recipients=REFERENCE_CLASS_RECIPIENTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
