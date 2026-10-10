"""TAXREV, Tax Revenue: the executable legacy formula and impute route.

Compute route (``api/core/sspi/ms/tax/taxrev.py``): every clean
``WB_TAXREV`` row, all years and all countries the cleaner kept, is scored
with ``goalpost(WB_TAXREV, 0, 50)``. Higher is better: no tax revenue
scores 0, half of GDP or more scores 1. The goalposts were read from
metadata at runtime and are declared here so ``check_against`` verifies
them. The score unit is the legacy literal ``Percentage``, in both routes.

The dataset is the World Bank WDI indicator ``GC.TAX.TOTL.GD.ZS``, "Tax
revenue (% of GDP)": compulsory transfers to the central government (not
general government), excluding most social security contributions, as a
percentage of GDP. The source already reports a percentage and nothing
rescales it. The shared World Bank cleaner drops zeros, as it drops every
falsy value; the source has none.

Impute route, in the legacy order:

1. series fill on the input: each country's observed series is carried
   forward to 2023, carried backward to 2000 and linearly interpolated
   across interior gaps;
2. Vietnam, Nigeria, Venezuela and Algeria, hard-coded, each get for every
   year 2000-2023 the flat mean of every clean ``WB_TAXREV`` row: every
   country in the source (not SSPI67), every year from the first (not only
   2000-2023), unweighted (TAXREV-1).

The union is scored with the same formula. If one of the four ever has an
observed row, legacy would store two values for the same country-years and
no precedence is decided: the strategy raises before anything is written.
Legacy raised on an empty dataset too (no mean to take).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 50
UNIT = "Percentage"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets; also the reference-class years
REFERENCE_CLASS_RECIPIENTS = ("VNM", "NGA", "VEN", "DZA")  # legacy impute_reference_class_average calls, in order


def score_taxrev(WB_TAXREV):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_taxrev`` lambda, identical in the impute route."""
    return goalpost(WB_TAXREV, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="TAXREV",
    observed_score=score_taxrev,
    imputation=SeriesFillThenScore(score_taxrev, SERIES_FILL_YEARS, listed_recipients=REFERENCE_CLASS_RECIPIENTS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
