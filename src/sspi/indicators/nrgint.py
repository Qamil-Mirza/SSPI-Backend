"""NRGINT, Energy Intensity: the executable legacy formula and impute route.

Compute route (``api/core/sspi/sus/nrg/nrgint.py``): every clean
``UNSDG_NRGINT`` row, all years and all countries the cleaner kept, is
scored with ``goalpost(UNSDG_NRGINT, 15, 0)``: lower is better. The
goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The score unit is the legacy literal
``Index``.

The dataset is SDG 7.3.1, series ``EG_EGY_PRIM``: megajoules of primary
energy per dollar of GDP at constant purchasing power parity. The legacy
description says 2017 dollars; the source now publishes the series in 2021
dollars, with the same goalposts applied (NRGINT-1 in
docs/methodology-conflicts.md).

Impute route: each country's latest observed *score* is carried forward to
2023 (legacy ``extrapolate_forward`` on the indicator documents). Nothing is
carried backward or interpolated, and there is no reference class: a
country with no observation gets no score.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import ExtrapolateScores
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 15, 0
EXTRAPOLATE_FORWARD_TO = 2023


def score_nrgint(UNSDG_NRGINT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_nrgint`` lambda."""
    return goalpost(UNSDG_NRGINT, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="NRGINT",
    observed_score=score_nrgint,
    imputation=ExtrapolateScores(forward_to=EXTRAPOLATE_FORWARD_TO),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
