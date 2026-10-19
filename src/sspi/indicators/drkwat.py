"""DRKWAT, Safely Managed Water: the executable legacy formula.

The dataset is World Bank WDI indicator ``SH.H2O.SMDW.ZS``, "People using
safely managed drinking water services (% of population)", from the
WHO/UNICEF Joint Monitoring Programme: water from an improved source that is
accessible on premises, available when needed and free from faecal and
priority chemical contamination. It is not basic or improved water access
and not piped-water coverage. The JMP publishes modelled annual estimates
where it can estimate all three criteria, revised with each release; many
countries have none.

The legacy compute route (``api/core/sspi/pg/inf/drkwat.py``) scores every
clean ``WB_DRKWAT`` row, all years and all countries, with
``goalpost(WB_DRKWAT, lg, ug)``, where ``lg, ug`` were read from the
methodology metadata at runtime and are (0, 100). They are declared on the
definition so ``check_against`` verifies them. The score unit is the legacy
literal ``%``.

Legacy DRKWAT has no impute route, anywhere in the pinned repository. A
country-year without an estimate has no score (DRKWAT-1).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 100
UNIT = "%"  # legacy compute-route literal


def score_drkwat(WB_DRKWAT):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_drkwat`` lambda, with the metadata goalposts."""
    return goalpost(WB_DRKWAT, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="DRKWAT",
    observed_score=score_drkwat,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
