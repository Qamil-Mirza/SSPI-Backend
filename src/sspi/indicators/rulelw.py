"""RULELW, Rule of Law Index: the executable legacy formula and impute route.

The dataset is V-Dem's rule of law index, column ``v2x_rule`` of the
Country-Year Full+Others archive, version 13 (``VDEM_RULELW``): the point
estimate of a Bayesian factor-analysis model, an interval scale from 0 (low)
to 1 (high). The cleaner kept the years 1991 to the year before the run and
the unit literal ``Index`` (:mod:`sspi.ingestion.vdem`).

Compute route (``api/core/sspi/pg/rts/rulelw.py``): every clean row, all
years and all countries, is scored with ``goalpost(VDEM_RULELW, 0, 1)``: the
index itself, clamped to [0, 1]. The goalposts were read from metadata at
runtime and are declared here so ``check_against`` verifies them. The score
unit is the legacy literal ``Index``, in both routes.

Impute route: each country's series is carried forward from its latest
observation to 2023 and the carried values are scored with the same
formula. Nothing is carried backward and no gap is interpolated; a country
with no observation gets nothing. The route cleared the imputed collection
but wrote its scores into the OBSERVED collection, where legacy readers
labelled them observed and a second run of the route added them again.
Here they are imputed scores, the approved storage correction (RULELW-1,
2026-10-26): each one's input is marked imputed exactly as in the legacy row
and keeps the value and source year it is carried from, and a run replaces
every score of the indicator. Whether RULELW should be imputed at all is
open (RULELW-3).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 1
UNIT = "Index"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # forward extrapolation target; the backward target is unused (no backward step)
SERIES_FILL_STEPS = ("forward",)  # extrapolate_forward(..., 2023, series_id=["CountryCode", "DatasetCode"], impute_only=True)


def score_rulelw(VDEM_RULELW):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_rulelw`` lambda, identical in the impute route."""
    return goalpost(VDEM_RULELW, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="RULELW",
    observed_score=score_rulelw,
    imputation=SeriesFillThenScore(score_rulelw, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
