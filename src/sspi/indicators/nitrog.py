"""NITROG, Sustainable Nitrogen Management: the executable legacy formula.

The legacy compute route (``api/core/sspi/sus/lnd/nitrog.py``) scores every
clean ``EPI_NITROG`` row, all years and all countries, with
``goalpost(EPI_NITROG, lg, ug)``, where ``lg, ug`` were read from the
methodology metadata at runtime and are (0, 100). They are hard-coded here
so importing the registry reads no metadata, and declared on the definition
so ``check_against`` fails at run time if the canonical metadata ever
disagrees. The source series is already a 0-100 EPI indicator score, so the
goalposts only clamp it to [0, 1].

Legacy NITROG has no impute route. Nothing is imputed; a missing source
value produces no score.

Source editions: the legacy route read the 2024 EPI archive, which is no
longer served; production ingestion reads the current 2026 archive. Whether
the two editions define the series identically is open (NITROG-1 in
docs/methodology-conflicts.md); this module is edition-agnostic.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = 0
UPPER_GOALPOST = 100


def score_nitrog(EPI_NITROG):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_nitrog`` lambda: goalpost(EPI_NITROG, 0, 100)."""
    return goalpost(EPI_NITROG, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="NITROG",
    observed_score=score_nitrog,
    imputation=None,
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
