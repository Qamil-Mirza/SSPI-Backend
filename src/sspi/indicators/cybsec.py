"""CYBSEC, Global Cybersecurity Index: the executable legacy formula.

The dataset is the SSPI's hand transcription of the ITU Global
Cybersecurity Index country scores for the 2014, 2017, 2018, 2020 and 2024
editions (:mod:`sspi.ingestion.itu`); the edition is the year. The legacy
cleaner divided the 2020 and 2024 scores, published on 0-100, by 100, and
left the earlier editions, published on 0-1, as they were; the editions
were built with different questionnaires and weights (CYBSEC-2). The
observation unit is the cleaner's literal ``Percentage``.

The legacy compute route (``api/core/sspi/pg/saf/cybsec.py``) scores every
clean ``ITU_CYBSEC`` row with ``goalpost(ITU_CYBSEC, lg, ug)``, where
``lg, ug`` were read from the methodology metadata at runtime and are
(0, 1). They are declared on the definition so ``check_against`` verifies
them. The score unit is the legacy literal ``Index``.

Legacy CYBSEC has no impute route: a country is scored in the edition years
only. Legacy could never store the transcription: five of its country
names have no code under the legacy name matcher, and the legacy clean
collection refused the whole dataset for them. The approved correction of
those five names (CYBSEC-1) is a source-representation repair in the ITU
normalizer; the scores are the legacy formula's on the corrected rows.
Canada is not in the transcription (CYBSEC-3).
"""

from __future__ import annotations

from sspi.indicators.registry import IndicatorDefinition
from sspi.scoring import goalpost

LOWER_GOALPOST, UPPER_GOALPOST = 0, 1
UNIT = "Index"  # legacy compute-route literal


def score_cybsec(ITU_CYBSEC):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``compute_cybsec`` lambda, with the metadata goalposts."""
    return goalpost(ITU_CYBSEC, LOWER_GOALPOST, UPPER_GOALPOST)


DEFINITION = IndicatorDefinition(
    code="CYBSEC",
    observed_score=score_cybsec,
    imputation=None,
    unit=UNIT,
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
)
