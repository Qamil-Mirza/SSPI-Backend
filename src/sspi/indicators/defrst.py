"""DEFRST, Deforestation: the executable legacy formula and impute route.

Compute route (``api/core/sspi/sus/lnd/defrst.py``): ``UNFAO_FRSTLV`` rows
from 2000 on and every ``UNFAO_FRSTAV`` row (the 1990s mean repeated for
1990-2022, derived in ``sspi.ingestion.derived``) are grouped by country
and year and scored::

    0 if UNFAO_FRSTAV == 0 else goalpost((UNFAO_FRSTLV - UNFAO_FRSTAV) / UNFAO_FRSTAV * 100, -20, 40)

The ``* 100`` is executable behaviour; the methodology text omits it
(DEFRST-2). Because the average stops at 2022, no observed score exists
after 2022 (DEFRST-2). The goalposts were read from metadata at runtime
and are declared here so ``check_against`` verifies them.

Impute route, reproduced by :class:`DefrstImputation`, imputes *scores*, not
inputs (DEFRST-1):

* every country's latest observed score is carried forward to 2023
  (legacy ``extrapolate_forward`` on the indicator documents);
* ``BEL, ARE, LUX`` receive, for 2000-2023, the mean of every other
  country's observed score (legacy ``impute_reference_class_average`` with
  ``item_type="Indicator"``).

No observation is fabricated: an extrapolated score keeps the anchor year's
inputs and records ``source_year``; a reference-class score has no inputs.

The legacy route applies the three-country rule unconditionally. Current
FAO data gives the United Arab Emirates a naturally-regenerating-forest
series, so the literal route produces reference-class scores for years it
also scores from observations, and two imputed rows for ARE 2023 (the
extrapolation and the reference class). One row per identity cannot hold
that. No replacement methodology has been approved (DEFRST-1 is pending
methodology review; the WATMAN-3 canonical-first policy was approved for
WATMAN only and is deliberately NOT generalized here), so on such data the
strategy raises ``ImputationError`` and selects no result.
"""

from __future__ import annotations

from dataclasses import dataclass

from sspi.errors import ImputationError
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult, extrapolate_scores_forward, reference_class_average_scores
from sspi.scoring import Observation, goalpost

FRSTLV, FRSTAV = "UNFAO_FRSTLV", "UNFAO_FRSTAV"
LOWER_GOALPOST, UPPER_GOALPOST = -20, 40
LEVEL_YEARS_FROM = 2000  # the compute route keeps level rows with Year >= 2000
IMPUTATION_YEARS = (2000, 2023)
REFERENCE_CLASS_RECIPIENTS = ("BEL", "ARE", "LUX")  # literal list from the legacy route (DEFRST-1)


def score_defrst(UNFAO_FRSTLV, UNFAO_FRSTAV):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_defrst``, identical in the compute route."""
    if UNFAO_FRSTAV == 0:
        return 0
    return goalpost((UNFAO_FRSTLV - UNFAO_FRSTAV) / UNFAO_FRSTAV * 100, LOWER_GOALPOST, UPPER_GOALPOST)


def keep_for_scoring(observation: Observation) -> bool:
    """The compute route's filter: level rows from 2000 on, every average row."""
    return observation.dataset_code != FRSTLV or observation.year >= LEVEL_YEARS_FROM


@dataclass(frozen=True, slots=True)
class DefrstImputation:
    """The legacy ``impute_defrst`` route as an ``ImputationStrategy``."""

    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        observed = context.observed_scores
        already_scored = sorted({s.country_code for s in observed} & set(REFERENCE_CLASS_RECIPIENTS))
        if already_scored:
            raise ImputationError(
                f"DEFRST cannot run on this data: the legacy methodology always imputes scores for {list(REFERENCE_CLASS_RECIPIENTS)} "
                f"(hard-coded list), but the FAO source data has changed and {already_scored} now have observed DEFRST scores of their own. "
                "The legacy rule would therefore produce both a real and an imputed score for the same country-years. No precedence between "
                "them has been decided and this backend does not choose one; nothing was written. Methodology review is required: see DEFRST-1 "
                "in docs/methodology-conflicts.md."
            )
        extrapolated = extrapolate_scores_forward(observed, IMPUTATION_YEARS[1])
        reference = [s for s in observed if s.country_code not in REFERENCE_CLASS_RECIPIENTS]
        imputed = list(extrapolated)
        if reference:  # legacy: `if ref_data:`
            for country in REFERENCE_CLASS_RECIPIENTS:
                imputed.extend(reference_class_average_scores(country, context.definition.code, *IMPUTATION_YEARS, reference))
        filled = {(s.country_code, s.year) for s in imputed}
        return IndicatorImputationResult(tuple(imputed), tuple(u for u in context.observed_unscored if (u.country_code, u.year) not in filled))


DEFINITION = IndicatorDefinition(
    code="DEFRST",
    observed_score=score_defrst,
    imputation=DefrstImputation(),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
    observation_filter=keep_for_scoring,
)
