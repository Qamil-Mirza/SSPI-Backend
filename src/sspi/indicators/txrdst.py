"""TXRDST, Tax Redistribution: the executable legacy formula.

The legacy compute route (``api/core/sspi/ms/tax/txrdst.py``) groups four
WID national income shares by country and year and scores every complete
group, all years the cleaners kept (2000-2024) and all their countries (the
SSPI67 members)::

    pretax  = WID_NINCSH_PRETAX_P0P50 / WID_NINCSH_PRETAX_P90P100
    posttax = WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50 / WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100
    score   = goalpost((posttax - pretax) / pretax * 100, -10, 100)

the percentage change in the bottom-50%-to-top-10% share ratio between
pre-tax national income (``sptincj992``) and post-tax national income
(``sdiincj992``), both for equal-split adults aged 20 and over. Post-tax
national income counts cash transfers and public spending as well as taxes,
so this is redistribution by the whole tax-and-transfer system, not by the
tax code alone (TXRDST-2). It reads the four share datasets directly; it
does not read ISHRAT or GINIPT scores.

A pre-tax ratio of exactly zero is scored as ``goalpost(0, -10, 100)``
(legacy logged a warning and did that); the post-tax ratio is computed
first, so a zero top-10% share raises ``ZeroDivisionError`` as in legacy.

The goalposts were read from metadata at runtime (``LowerGoalpost: -10``,
``UpperGoalpost: 100``) and are declared here so ``check_against`` verifies
them; the methodology's ``ScoreFunction`` text says ``-10, -100``
(TXRDST-1). The score unit is the legacy string, copied from ISHRAT,
doubled word included.

Legacy TXRDST has no impute route. Nothing is imputed; a country-year
missing any of the four shares stays unscored.

The inputs carry the legacy float32 representation of the WID values
(``sspi.ingestion.wid``), so the ratios and the score are the legacy
numbers exactly.
"""

from __future__ import annotations

import logging

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = -10
UPPER_GOALPOST = 100
UNIT = "Ratio of Bottom 50% Income Share to to Top 10% Income Share"  # legacy literal

log = logging.getLogger(__name__)


def score_txrdst(WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50, WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100, WID_NINCSH_PRETAX_P0P50, WID_NINCSH_PRETAX_P90P100):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_txrdst`` closure, parameters and operations in the legacy order."""
    pretax_ratio = WID_NINCSH_PRETAX_P0P50 / WID_NINCSH_PRETAX_P90P100
    posttax_ratio = WID_NINCSH_POSTTAX_EQUALSPLIT_P0P50 / WID_NINCSH_POSTTAX_EQUALSPLIT_P90P100
    if pretax_ratio == 0:
        log.warning("Pretax ratio is zero, cannot compute TXRDST.")
        return goalpost(0, LOWER_GOALPOST, UPPER_GOALPOST)
    return goalpost((posttax_ratio - pretax_ratio) / pretax_ratio * 100, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="TXRDST",
    observed_score=score_txrdst,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
