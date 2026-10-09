"""GTRANS, Green Transport Index: the executable legacy formula and impute route.

Inputs: ``IEA_TCO2EM``, the transport-sector rows of IEA indicator
``CO2BySector``, which the source publishes in million tonnes and the legacy
cleaner stored times 10**9, so in kilograms of CO2 (a national total); and
``WB_POPULN``, World Bank total population (``SP.POP.TOTL``).

Compute route (``api/core/sspi/sus/ghg/gtrans.py``): every country-year with
both is scored with

    goalpost(IEA_TCO2EM / WB_POPULN, 7000, 0)

kilograms of transport CO2 per person; lower is better, 7 tonnes or more
scores 0. The legacy unit label and description say tonnes per inhabitant
(GTRANS-1). No year filter: every year both sources have is scored. The
goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them.

Impute route: the route read back its stored complete and incomplete
groups for 2000-2023 only, carried each country's ``IEA_TCO2EM`` series
forward from its latest year in that window to 2023 (not backward, no
interpolation), and scored the carried value against that year's own
population. Population is never imputed. Only scores with a carried input
are kept. There is no reference class.
"""

from __future__ import annotations

from sspi.indicators.registry import LEGACY_IMPUTATION_YEARS, IndicatorDefinition
from sspi.indicators.strategy import ExtrapolateInputsForwardThenScore
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 7000, 0


def score_gtrans(IEA_TCO2EM, WB_POPULN):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_gtrans`` / ``impute_gtrans`` lambda."""
    return goalpost(IEA_TCO2EM / WB_POPULN, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="GTRANS",
    observed_score=score_gtrans,
    imputation=ExtrapolateInputsForwardThenScore(formula=score_gtrans, years=LEGACY_IMPUTATION_YEARS, datasets=("IEA_TCO2EM",)),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
