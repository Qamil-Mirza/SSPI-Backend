"""SECAPP, Security Apparatus: the executable legacy formula.

The dataset is component C1, "Security Apparatus", of the Fund for Peace's
Fragile States Index, one value per country per annual edition (2006-2023),
read from the official workbooks (:mod:`sspi.ingestion.fsi`). It scores the
security threats to a state (bombings, battle-related deaths, rebel
movements, mutinies, coups, terrorism) from 0 (best) to 10 (worst). It is
not the overall FSI total. The edition is the year; which calendar year an
edition assesses is an open question (SECAPP-2).

The legacy compute route (``api/core/sspi/pg/saf/secapp.py``) scores every
clean ``FSI_SECAPP`` row with ``goalpost(FSI_SECAPP, lg, ug)``, where
``lg, ug`` were read from the methodology metadata at runtime and are
(10, 0): 10 scores 0, 0 scores 1. They are declared on the definition so
``check_against`` verifies them. The score unit is the legacy literal
``Index``. Legacy SECAPP has no impute route; nothing before 2006 or
between editions is filled.

The pinned legacy acquisition never stored an FSI value; the approved FSI
adapter repairs it (SECAPP-1). The formula here is the legacy one,
unchanged.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 10, 0
UNIT = "Index"  # legacy compute-route literal


def score_secapp(FSI_SECAPP):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_secapp`` lambda, with the metadata goalposts."""
    return goalpost(FSI_SECAPP, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="SECAPP",
    observed_score=score_secapp,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
