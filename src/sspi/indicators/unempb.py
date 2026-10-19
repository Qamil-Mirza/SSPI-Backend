"""UNEMPB, Unemployment Benefits Coverage: the executable legacy formula and
impute route.

The dataset is UN SDG indicator 1.3.1, series ``SI_COV_UEMP``, "Proportion
of unemployed persons receiving unemployment cash benefit", both sexes
(``sex=BOTHSEX``), ages 15 and over, in percent. The ILO is the custodian
agency and most values are ILO estimates (``Nature`` ``E``); a reported
``0`` (no unemployment cash benefit reaches the unemployed) is kept as a
value. The 2018 static SSPI called this indicator UNEMPL and read the ILO's
own copy of the same SDG series (``DF_SDG_0131_SEX_SOC_RT``,
``SOC_CONTIG_UNE``); the executable indicator is UNEMPB on the UN series.

Compute route (``api/core/sspi/ms/wwb/unempb.py``): every clean
``UNSDG_BENFTS_UNEMP`` row, all years and all countries the cleaner kept, is
scored with ``goalpost(UNSDG_BENFTS_UNEMP, 0, 100)``. Higher is better: no
coverage scores 0, full coverage scores 1. The goalposts were read from
metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``Benefits Coverage (%)``.

Impute route, in the legacy order:

1. series fill on the input: each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated
   across interior gaps;
2. Iceland, hard-coded, gets for every year 2000-2023 the flat mean of every
   clean ``UNSDG_BENFTS_UNEMP`` row: every country in the source (not
   SSPI67), every year, unweighted (UNEMPB-2).

The union is scored with the same formula and labelled ``Tax Rate``, the
legacy impute route's literal (UNEMPB-1). If Iceland ever has an observed
row, legacy would store two values for the same country-years and no
precedence is decided: the strategy raises before anything is written.
Legacy raised on an empty dataset too (no mean to take).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 100
UNIT = "Benefits Coverage (%)"  # legacy compute-route literal
IMPUTED_UNIT = "Tax Rate"  # legacy impute-route literal (UNEMPB-1)
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets; also the reference-class years
REFERENCE_CLASS_RECIPIENTS = ("ISL",)  # legacy impute_reference_class_average call


def score_unempb(UNSDG_BENFTS_UNEMP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_unempb`` lambda, identical in the impute route."""
    return goalpost(UNSDG_BENFTS_UNEMP, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="UNEMPB",
    observed_score=score_unempb,
    imputation=SeriesFillThenScore(score_unempb, SERIES_FILL_YEARS, unit=IMPUTED_UNIT, listed_recipients=REFERENCE_CLASS_RECIPIENTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
