"""SANSRV, Basic Sanitation Services: the executable legacy formula and
impute route.

The dataset is World Bank WDI indicator ``SH.STA.BASS.ZS``, "People using at
least basic sanitation services (% of population)", from the WHO/UNICEF
Joint Monitoring Programme: improved facilities (flush or pour-flush to a
sewer, septic tank or pit latrine, ventilated pit latrines, composting
toilets, pit latrines with a slab) not shared with other households,
including safely managed services. The JMP publishes modelled annual
estimates, revised with each release; nothing here rescales them. The shared
World Bank cleaner drops zeros, as it drops every falsy value; the source
has none.

Compute route (``api/core/sspi/pg/inf/sansrv.py``): every clean row, all
years and all countries, is scored with ``goalpost(WB_SANSRV, 50, 100)``;
half the population or less scores 0, everyone scores 1. The goalposts were
read from metadata at runtime and are declared here so ``check_against``
verifies them. The 2018 static SSPI scored the same series on 0 → 100
(SANSRV-1). The score unit is the legacy literal ``Percent``, in both routes.

Impute route: each country's observed series is carried forward to 2023,
then backward to 2000, each from the observed rows, and the filled values
are scored with the same formula. There is no interpolation: an interior
gap stays empty. Every country in the dataset is treated, and a country with
no observation gets nothing; there are no hard-coded recipients and no
reference class (SANSRV-2).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import SeriesFillThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 50, 100
UNIT = "Percent"  # legacy literal, compute and impute routes alike
SERIES_FILL_YEARS = (2000, 2023)  # backward and forward extrapolation targets
SERIES_FILL_STEPS = ("forward", "backward")  # the legacy route's order; no interpolation


def score_sansrv(WB_SANSRV):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_sansrv`` lambda, identical in the impute route."""
    return goalpost(WB_SANSRV, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="SANSRV",
    observed_score=score_sansrv,
    imputation=SeriesFillThenScore(score_sansrv, SERIES_FILL_YEARS, steps=SERIES_FILL_STEPS),
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
