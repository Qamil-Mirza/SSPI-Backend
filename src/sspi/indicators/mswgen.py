"""MSWGEN, Municipal Solid Waste Generation: production's formula.

The legacy compute route (``api/core/sspi/sus/wst/mswgen.py``) scores every
clean ``EPI_MSWGEN`` row, all years and all countries, with
``goalpost(EPI_MSWGEN, lg, ug)``, where ``lg, ug`` are read from the
methodology metadata at runtime. They are hard-coded here so importing the
registry reads no metadata, and declared on the definition so
``check_against`` fails at run time if the canonical metadata ever
disagrees.

Production precedence (project owner decision 2026-11-09, MSWGEN-1
resolved): the goalposts are (0, 100), the values production's metadata
serves and every production MSWGEN score satisfies. The pinned commit holds
(100, 0), introduced by legacy commit ff1b6e68e on 2025-11-15 and never
adopted by production; the canonical metadata carries the PROVENANCE edit.

The source series is the 2024 EPI's waste-generated-per-capita indicator
*score* (``WPC_ind_na.csv``, 0-100, higher = less waste per person), not
kilograms per person, so (0, 100) keeps the EPI's direction: less waste
scores higher. A reported 0 is a valid EPI score and scores 0.0.

Legacy MSWGEN has no impute route. Nothing is imputed; a missing source
value produces no score.

Source: the legacy archive is no longer served and the current EPI edition
publishes no WPC series, so ``EPI_MSWGEN`` has no live ingestion path
(``sspi.ingestion.UNAVAILABLE_SOURCES``). The committed 2024 fixture and the
2026-11-09 production snapshot are the historical parity references.
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST = 0  # production precedence, MSWGEN-1 (the pinned commit: 100)
UPPER_GOALPOST = 100  # (the pinned commit: 0)
PINNED_GOALPOSTS = (100, 0)  # the pinned legacy commit's metadata, kept for its parity test


def score_mswgen(EPI_MSWGEN):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_mswgen`` lambda with production's goalposts: goalpost(EPI_MSWGEN, 0, 100)."""
    return goalpost(EPI_MSWGEN, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="MSWGEN",
    observed_score=score_mswgen,
    imputation=None,
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
