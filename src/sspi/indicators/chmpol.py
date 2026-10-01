"""CHMPOL, Chemical Pollution Convention Compliance: the executable legacy formula.

The legacy compute route (``api/core/sspi/sus/lnd/chmpol.py``) scores every
(country, year) that has all five convention-compliance datasets with the
plain mean of the five percentages divided by 100. No ``goalpost`` call, no
clamping, no year or country filter, no impute route. The source reports
these series for 2015, 2020 and 2025 only (Minamata: 2020 and 2025), so
complete groups are sparse; incomplete groups are discarded.

Open questions, in docs/methodology-conflicts.md:

* CHMPOL-1: the legacy ``UNSDG_ROTDAM`` cleaner selects the Stockholm series
  (``SG_HAZ_CMRSTHOLM``), not the Rotterdam one the source publishes. The
  canonical metadata reproduces that on purpose, so this formula averages the
  Stockholm value twice and never sees Rotterdam data.
* CHMPOL-2: the methodology text says ``average(goalpost(x, 0, 1) ...)`` and
  the indicator metadata says goalposts (0, 100); the executable ``/ 100`` is
  equivalent to goalpost(x, 0, 100) only while every input is inside
  [0, 100]. No goalposts are declared on the definition because the
  executable formula applies none.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition


def score_chmpol(UNSDG_STKHLM, UNSDG_MINMAT, UNSDG_MONTRL, UNSDG_BASELA, UNSDG_ROTDAM):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_chmpol.score_chmpol``, verbatim including summation order."""
    return (UNSDG_STKHLM + UNSDG_MINMAT + UNSDG_MONTRL + UNSDG_BASELA + UNSDG_ROTDAM) / 5 / 100


DEFINITION = IndicatorDefinition(
    code="CHMPOL",
    observed_score=score_chmpol,
    imputation=None,
    unit="Index",
)
