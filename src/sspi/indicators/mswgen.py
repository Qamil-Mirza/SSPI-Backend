"""MSWGEN, Municipal Solid Waste Generation: the executable legacy formula.

The legacy compute route (``api/core/sspi/sus/wst/mswgen.py``) scores every
clean ``EPI_MSWGEN`` row, all years and all countries, with
``goalpost(EPI_MSWGEN, lg, ug)``, where ``lg, ug`` were read from the
methodology metadata at runtime and are (100, 0). They are hard-coded here
so importing the registry reads no metadata, and declared on the definition
so ``check_against`` fails at run time if the canonical metadata ever
disagrees.

The source series is the 2024 EPI's waste-generated-per-capita indicator
*score* (``WPC_ind_na.csv``, 0-100, higher = less waste per person), not
kilograms per person. A 100 -> 0 goalpost therefore turns it around: the
most waste-intensive countries score highest. That is the executable legacy
behaviour and is preserved; MSWGEN-1 in docs/methodology-conflicts.md lays
out the question. A reported 0 is a valid EPI score and scores 1.0.

Legacy MSWGEN has no impute route. Nothing is imputed; a missing source
value produces no score.

Source: the legacy archive is no longer served and the current EPI edition
publishes no WPC series, so ``EPI_MSWGEN`` has no live ingestion path
(``sspi.ingestion.UNAVAILABLE_SOURCES``). The committed 2024 fixture is the
historical parity reference.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = 100
UPPER_GOALPOST = 0


def score_mswgen(EPI_MSWGEN):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_mswgen`` lambda: goalpost(EPI_MSWGEN, 100, 0)."""
    return goalpost(EPI_MSWGEN, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="MSWGEN",
    observed_score=score_mswgen,
    imputation=None,
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
