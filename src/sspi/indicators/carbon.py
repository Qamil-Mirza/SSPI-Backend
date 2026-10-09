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

Resolved methodology (CARBON-1, direction B, project owner 2026-10-08):
impute only when observed data is unavailable. A listed country that has
observed CARBON scores of its own is not a recipient; it is scored from its
own data only. The rule is per country, not per year, and CARBON has no
extrapolation, so such a country's unscored years stay unscored. The
reference means are unchanged: every clean row of each dataset, the
recipient's own rows included, as in legacy (their composition is a
separate open question, CARBON-2). Belgium and Luxembourg have level rows
from 2000 but no 1990s mean, hence no observed score; they still receive
the imputed inputs. On data where no listed country has observed scores the
result is exactly the legacy result.
"""

from __future__ import annotations

from dataclasses import dataclass

from sspi.imputation import reference_class_average
from sspi.indicators.registry import IndicatorDefinition
from sspi.indicators.strategy import IndicatorImputationContext, IndicatorImputationResult
from sspi.scoring import Observation, goalpost, score_indicator

CRBNLV, CRBNAV = "UNFAO_CRBNLV", "UNFAO_CRBNAV"
LOWER_GOALPOST, UPPER_GOALPOST = -5, 50
LEVEL_YEARS_FROM = 2000  # the compute route keeps level rows with Year >= 2000
IMPUTATION_YEARS = (2000, 2023)
REFERENCE_CLASS_RECIPIENTS = ("KWT", "BEL", "LUX")  # literal list from the legacy route; only those without observed scores receive (CARBON-1)


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
    """The legacy ``impute_carbon`` route as an ``ImputationStrategy``."""

    auxiliary_datasets: tuple[str, ...] = ()
    recipient_group: str | None = None

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        level = context.dataset(CRBNLV)
        average = context.dataset(CRBNAV)
        scored_countries = {s.country_code for s in context.observed_scores}
        recipients = [c for c in REFERENCE_CLASS_RECIPIENTS if c not in scored_countries]  # CARBON-1: impute only without observed data
        rows: list[Observation] = []
        for country in recipients:  # legacy order: KWT level, KWT average, BEL ..., LUX ...
            rows.extend(reference_class_average(country, CRBNLV, *IMPUTATION_YEARS, level))
            rows.extend(reference_class_average(country, CRBNAV, *IMPUTATION_YEARS, average))
        scored = score_indicator(rows, context.definition.code, score_carbon, context.definition.unit)
        filled = {(s.country_code, s.year) for s in scored.scored}
        still_incomplete = tuple(u for u in context.observed_unscored if (u.country_code, u.year) not in filled)
        return IndicatorImputationResult(tuple(scored.scored), still_incomplete + tuple(scored.unscored))


DEFINITION = IndicatorDefinition(
    code="CARBON",
    observed_score=score_carbon,
    imputation=CarbonImputation(),
    unit="Index",
    goalposts=(LOWER_GOALPOST, UPPER_GOALPOST),
    observation_filter=keep_for_scoring,
)
