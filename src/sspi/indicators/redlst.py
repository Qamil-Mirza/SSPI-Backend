"""REDLST, IUCN Red List Index: the executable legacy formula.

The legacy compute route (``api/core/sspi/sus/eco/redlst.py``) scores every
clean ``UNSDG_REDLST`` row, all years and all countries, with
``goalpost(UNSDG_REDLST, lg, ug)``, where ``lg, ug`` were read from the
methodology metadata at runtime and are (0, 1). They are hard-coded here so
importing the registry reads no metadata, and declared on the definition so
``check_against`` fails at run time if the canonical metadata ever disagrees.

Legacy REDLST has no impute route. Nothing is imputed: no recipient group,
no reference-class average, no interpolation or extrapolation. A missing
observation produces no score.

Preserved, unresolved historical discrepancy: every REDLST row of the
retired 2018 static data (``local/SSPIStaticData2018.csv``) satisfies
``score = (raw - 0.5) / 0.5``, implying goalposts (0.5, 1). The executable
route, the methodology file and ``local/IndicatorDetailsStatic.csv`` all say
(0, 1). This module implements the executable behaviour. See REDLST-1 in
docs/methodology-conflicts.md.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = 0
UPPER_GOALPOST = 1


def score_redlst(UNSDG_REDLST):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_redlst`` lambda: goalpost(UNSDG_REDLST, 0, 1)."""
    return goalpost(UNSDG_REDLST, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="REDLST",
    observed_score=score_redlst,
    imputation=None,
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
