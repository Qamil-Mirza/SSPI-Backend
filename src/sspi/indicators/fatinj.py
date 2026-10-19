"""FATINJ, Fatal Workplace Injuries: the executable legacy formula.

The dataset is ILOSTAT dataflow ``DF_SDG_F881_SEX_MIG_RT``, SDG indicator
8.8.1, "Fatal occupational injuries per 100,000 workers", both sexes
(``SEX_T``) and every migrant status (``MIG_STATUS_TOTAL``): a rate, as
published. The ILO compiles it from national administrative registers,
labour inspection and insurance records; the reference group and the kind of
case counted (reported or compensated injuries, with or without
occupational disease) differ by country and are recorded only in the
observation notes, which nothing filters on (FATINJ-2).

The legacy compute route (``api/core/sspi/ms/wwb/fatinj.py``) scores every
clean ``ILO_FATINJ`` row, all years and all areas the cleaner kept, with::

    goalpost(ILO_FATINJ, 25, 0)

Lower is better: no fatal injury scores 1, 25 or more per 100,000 workers
scores 0. The goalposts were read from metadata at runtime and are declared
here so ``check_against`` verifies them. The score unit is the legacy
literal ``Rate``.

Legacy FATINJ has no impute route. Nothing is imputed: a country is scored
only in the years the ILO reports (FATINJ-1).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 25, 0
UNIT = "Rate"  # legacy compute-route literal


def score_fatinj(ILO_FATINJ):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_fatinj`` lambda."""
    return goalpost(ILO_FATINJ, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="FATINJ",
    observed_score=score_fatinj,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
