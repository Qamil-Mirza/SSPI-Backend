"""MURDER, Intentional Homicide: the executable legacy formula and impute
route.

The dataset is World Bank WDI indicator ``VC.IHR.PSRC.P5``, "Intentional
homicides (per 100,000 people)", compiled by UNODC from criminal-justice
and public-health records. The shared World Bank cleaner drops a zero, as
it drops every falsy value: a country-year with no recorded homicide is
missing, and the impute route then fills it (MURDER-1). The observation
unit is the cleaner's literal ``Per 100,000 people``.

Compute route (``api/core/sspi/pg/saf/murder.py``): every clean row, all
years and all countries, is scored with ``goalpost(WB_MURDER, 20, 0)``.
Lower is better: no homicide scores 1, twenty or more per 100,000 scores 0.
The goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy literal
``Index``, in both routes.

Impute route, in the legacy order: each country's observed series is
linearly interpolated across every interior gap (any year, not only
2000-2023), carried forward to 2023 and carried backward to 2000, each step
from the observed rows on their own, and the filled values are scored with
the same formula. The three steps never fill the same year. Every country
in the dataset is treated, however far a value is carried (MURDER-2); a
country with no observation gets nothing. There are no hard-coded
recipients and no reference class.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 20, 0
UNIT = "Index"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets
SERIES_FILL_STEPS = ("interpolate", "forward", "backward")  # the legacy route's order


def score_murder(WB_MURDER):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_murder`` lambda, identical in the impute route."""
    return goalpost(WB_MURDER, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="MURDER",
    observed_score=score_murder,
    imputation=SeriesFillThenScore(score_murder, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
