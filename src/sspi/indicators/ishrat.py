"""ISHRAT, Income Share Ratio: the executable legacy formula.

The legacy compute route (``api/core/sspi/ms/neq/ishrat.py``) groups the two
WID pre-tax national income shares by country and year and scores every
complete group, all years the cleaner kept (2000-2024) and all its countries
(the SSPI67 members), with::

    goalpost(WID_NINCSH_PRETAX_P0P50 / WID_NINCSH_PRETAX_P90P100, 0.2, 1.25)

the bottom 50% share divided by the top 10% share. The goalposts were read
from the methodology metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy string,
doubled word included.

Legacy ISHRAT has no impute route. Nothing is imputed; a country-year with
only one of the two shares stays unscored.

The inputs carry the legacy float32 representation of the WID values
(``sspi.ingestion.wid``), so the ratio and the score are the legacy numbers
exactly.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = 0.2
UPPER_GOALPOST = 1.25
UNIT = "Ratio of Bottom 50% Income Share to to Top 10% Income Share"  # legacy literal


def score_ishrat(WID_NINCSH_PRETAX_P90P100, WID_NINCSH_PRETAX_P0P50):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_ishrat`` lambda, parameters in the legacy order."""
    return goalpost(WID_NINCSH_PRETAX_P0P50 / WID_NINCSH_PRETAX_P90P100, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="ISHRAT",
    observed_score=score_ishrat,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
