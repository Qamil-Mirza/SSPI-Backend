"""CARBON, Natural Carbon Capture: the executable legacy formula and impute route.

Compute route (``api/core/sspi/sus/lnd/carbon.py``): ``UNFAO_CRBNLV`` rows
from 2000 on and every ``UNFAO_CRBNAV`` row (the 1990s mean repeated for
every source year, derived in ``sspi.ingestion.derived``) are grouped by
country and year and scored::

    0 if UNFAO_CRBNAV == 0 else goalpost((UNFAO_CRBNLV - UNFAO_CRBNAV) / UNFAO_CRBNAV * 100, -5, 50)

The goalposts were read from metadata at runtime and are declared here so
``check_against`` verifies them. The derived average's legacy unit label
("millions of kilograms") mislabels a million-tonne series; the score is a
ratio and unaffected (PROVENANCE.yaml).

Impute route, reproduced by :class:`CarbonImputation`, imputes *inputs*
(CARBON-1): ``KWT, BEL, LUX`` receive, for 2000-2023, the mean of every
clean ``UNFAO_CRBNLV`` value and the mean of every clean ``UNFAO_CRBNAV``
value (all countries, all years including the 1990s), and those imputed
inputs are scored with the ordinary formula. No extrapolation.

The legacy route applies the three-country rule unconditionally. Current
FAO data gives Kuwait a carbon-stock series with 1990s values, so the
literal route produces imputed scores for country-years it also scores from
observations.

Production precedence (project owner 2026-11-09, CARBON-3): the registered
imputation is the legacy rule production runs: the three listed countries
always receive the imputed inputs. Where a listed country also has observed
CARBON scores (Kuwait, in production's own clean data and in the current FAO
data), legacy would store an observed and an imputed score for the same
country-years; no precedence is decided (CARBON-1, unresolved), so the run
raises ``ImputationError`` and writes nothing. Production's stored imputed
scores are this rule's values on production's rows (tests/golden/
test_golden_production.py). The reference means are every clean row of each
dataset, the recipient's own rows included, as in legacy.

The 2026-10-08 direction B (a listed country with observed scores is not a
recipient) is kept, unregistered, as ``OBSERVED_FIRST_IMPUTATION``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sspi.errors import ImputationError
from sspi.imputation import reference_class_average
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult
from sspi.scoring import Observation, goalpost, score_indicator

CRBNLV, CRBNAV = "UNFAO_CRBNLV", "UNFAO_CRBNAV"
LOWER_GOALPOST, UPPER_GOALPOST = -5, 50
LEVEL_YEARS_FROM = 2000  # the compute route keeps level rows with Year >= 2000
IMPUTATION_YEARS = (2000, 2023)
REFERENCE_CLASS_RECIPIENTS = ("KWT", "BEL", "LUX")  # literal list from the legacy route


def score_carbon(UNFAO_CRBNLV, UNFAO_CRBNAV):  # noqa: N803 - parameter names are dataset codes
    """Legacy ``score_carbon``, identical in both routes."""
    if UNFAO_CRBNAV == 0:
        return 0
    return goalpost((UNFAO_CRBNLV - UNFAO_CRBNAV) / UNFAO_CRBNAV * 100, LOWER_GOALPOST, UPPER_GOALPOST)


def keep_for_scoring(observation: Observation) -> bool:
    """The compute route's filter: level rows from 2000 on, every average row."""
    return observation.dataset_code != CRBNLV or observation.year >= LEVEL_YEARS_FROM


@dataclass(frozen=True, slots=True)
class CarbonImputation:
    """The legacy ``impute_carbon`` route as an ``ImputationStrategy``.

    ``observed_recipients`` says what happens to a listed country that has
    observed CARBON scores of its own: ``"raise"`` (production precedence,
    CARBON-3: the legacy rule, whose output would hold two scores for one
    identity, with no precedence decided) or ``"skip"`` (direction B of
    CARBON-1: it is not a recipient and is scored from its own data only).
    """

    observed_recipients: str = "raise"
    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def __post_init__(self) -> None:
        if self.observed_recipients not in ("raise", "skip"):
            raise ValueError(f"observed_recipients must be 'raise' or 'skip', got {self.observed_recipients!r}")

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        scored_countries = {s.country_code for s in context.observed_scores}
        already_scored = [c for c in REFERENCE_CLASS_RECIPIENTS if c in scored_countries]
        if already_scored and self.observed_recipients == "raise":
            raise ImputationError(
                f"CARBON cannot run on this data: the legacy methodology always imputes inputs for {list(REFERENCE_CLASS_RECIPIENTS)} "
                f"(hard-coded list), but {already_scored} now have observed carbon data and CARBON scores of their own. The legacy "
                "rule would therefore produce both a real and an imputed score for the same country-years. No precedence between "
                "them has been decided and this backend does not choose one; nothing was written. Methodology review is required: "
                "see CARBON-1 and CARBON-3 in docs/methodology-conflicts.md."
            )
        recipients = [c for c in REFERENCE_CLASS_RECIPIENTS if c not in already_scored]
        scored = score_indicator(reference_rows(context, recipients), context.definition.code, score_carbon, context.definition.unit)
        filled = {(s.country_code, s.year) for s in scored.scored}
        still_incomplete = tuple(u for u in context.observed_unscored if (u.country_code, u.year) not in filled)
        return IndicatorImputationResult(tuple(scored.scored), still_incomplete + tuple(scored.unscored))


def reference_rows(context: IndicatorImputationContext, recipients) -> list[Observation]:
    """The legacy route's imputed inputs for ``recipients``: each dataset's mean of every clean row, 2000-2023."""
    level = context.dataset(CRBNLV)
    average = context.dataset(CRBNAV)
    rows: list[Observation] = []
    for country in recipients:  # legacy order: KWT level, KWT average, BEL ..., LUX ...
        rows.extend(reference_class_average(country, CRBNLV, *IMPUTATION_YEARS, level))
        rows.extend(reference_class_average(country, CRBNAV, *IMPUTATION_YEARS, average))
    return rows


OBSERVED_FIRST_IMPUTATION = CarbonImputation(observed_recipients="skip")  # CARBON-1 direction B (2026-10-08); not registered

DEFINITION = IndicatorDefinition(
    code="CARBON",
    observed_score=score_carbon,
    imputation=CarbonImputation(observed_recipients="raise"),  # production precedence, CARBON-3
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
    observation_filter=keep_for_scoring,
)
