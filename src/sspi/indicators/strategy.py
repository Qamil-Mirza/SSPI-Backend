"""Indicator-level imputation strategies: how an indicator produces its
imputed scores after the observed scoring pass.

This is orchestration owned by the indicator layer. It is distinct from
``sspi.imputation``, which imputes *observations* (series extrapolation,
interpolation, reference-class means) and whose result type is
``sspi.imputation.ImputationResult``. A strategy decides which of those
primitives to apply, to which countries, and how to turn the outcome into
``IndicatorScore`` rows; its result type is :class:`IndicatorImputationResult`.

Two kinds of strategy exist. Input-level ones impute observations and score
them with the ordinary formula (BIODIV, WATMAN, CARBON). Score-level ones
derive new ``IndicatorScore`` rows from the observed scores themselves
(DEFRST: forward extrapolation of scores, reference-class mean of scores);
the primitives for that are :func:`extrapolate_scores_forward` and
:func:`reference_class_average_scores`, and such a score says how it was
derived in its own ``provenance`` rather than in its inputs.

Every strategy is pure Python: no database, no network, no catalog access.
The generic runner supplies everything a strategy declares it needs
(:attr:`ImputationStrategy.auxiliary_datasets`,
:attr:`ImputationStrategy.recipient_group`) and calls :meth:`impute` once.
Indicator-specific behaviour, including any hard-coded recipient list the
legacy route had, lives in the strategy instance, never in the runner.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sspi.errors import ImputationError
from sspi.imputation import FORWARD_EXTRAPOLATION, REFERENCE_CLASS_AVERAGE, impute_dataset, is_imputed
from sspi.scoring import IndicatorScore, Observation, UnscoredGroup, score_indicator

if TYPE_CHECKING:
    from sspi.indicators.registry import IndicatorDefinition


@dataclass(frozen=True, slots=True)
class IndicatorImputationContext:
    """Everything a strategy may look at."""

    definition: IndicatorDefinition
    observations: tuple[Observation, ...]  # canonical rows of definition.dataset_codes
    auxiliary: Mapping[str, tuple[Observation, ...]]  # canonical rows of strategy.auxiliary_datasets, by code
    observed_scores: tuple[IndicatorScore, ...]  # the observed pass
    observed_unscored: tuple[UnscoredGroup, ...]
    recipients: tuple[str, ...]  # members of strategy.recipient_group, else ()

    def dataset(self, code: str) -> tuple[Observation, ...]:
        """Canonical rows of one dependency dataset, in input order."""
        return tuple(o for o in self.observations if o.dataset_code == code)


@dataclass(frozen=True, slots=True)
class IndicatorImputationResult:
    """What a strategy produced. Every score must classify as imputed."""

    imputed_scores: tuple[IndicatorScore, ...]
    unscored: tuple[UnscoredGroup, ...]  # groups still incomplete after imputation


@runtime_checkable
class ImputationStrategy(Protocol):
    """An indicator's executable imputation methodology."""

    @property
    def auxiliary_datasets(self) -> tuple[str, ...]: ...

    @property
    def recipient_group(self) -> str | None: ...

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult: ...


# --------------------------------------------------------------------------- #
# Score-level primitives (the legacy helpers applied to indicator documents)
# --------------------------------------------------------------------------- #


def extrapolate_scores_forward(scores: Iterable[IndicatorScore], end_year: int) -> tuple[IndicatorScore, ...]:
    """Legacy ``extrapolate_forward`` on indicator documents: per country,
    carry the latest score forward to ``end_year``. The legacy helper
    deep-copied the latest document, so each new score keeps that year's
    inputs and computed values; its own provenance says it is imputed, by
    forward extrapolation, from ``source_year``, at ``imputation_distance``.
    Scores whose own provenance already marks them imputed are not anchors."""
    by_country: dict[str, list[IndicatorScore]] = {}
    for score in scores:
        by_country.setdefault(score.country_code, []).append(score)
    added: list[IndicatorScore] = []
    for series in by_country.values():
        series.sort(key=lambda s: s.year)
        for earlier, later in zip(series, series[1:]):
            if earlier.year == later.year:
                raise ImputationError(f"duplicate score identity {earlier.indicator_code}/{earlier.country_code}/{earlier.year} in extrapolation input")
        last = series[-1]
        for year in range(last.year + 1, end_year + 1):
            provenance = {"imputed": True, "imputation_method": FORWARD_EXTRAPOLATION, "imputation_distance": year - last.year, "source_year": last.year}
            added.append(IndicatorScore(last.indicator_code, last.country_code, year, last.score, last.unit, last.inputs, last.computed, provenance))
    return tuple(added)


def reference_class_average_scores(country_code: str, indicator_code: str, start_year: int, end_year: int, reference: Iterable[IndicatorScore]) -> tuple[IndicatorScore, ...]:
    """Legacy ``impute_reference_class_average(..., "Indicator", ...)``: one
    flat mean of every reference score, assigned to each year of the range.
    The reference is used exactly as supplied; only units are checked. The
    imputed scores have no inputs; their provenance says how many scores
    the mean came from."""
    reference = list(reference)
    if not reference:
        raise ImputationError(f"reference scores for {indicator_code}/{country_code} are empty")
    unit = reference[0].unit
    if any(s.unit != unit for s in reference):
        raise ImputationError(f"units are not consistent across reference scores for {indicator_code}: {sorted({s.unit for s in reference})}")
    mean = sum(s.score for s in reference) / len(reference)
    provenance = {"imputed": True, "imputation_method": REFERENCE_CLASS_AVERAGE, "reference_score_count": len(reference), "requested_years": [start_year, end_year]}
    return tuple(IndicatorScore(indicator_code, country_code, year, mean, unit, (), (), provenance) for year in range(start_year, end_year + 1))


# --------------------------------------------------------------------------- #
# Shared strategies
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ImputeInputsThenScore:
    """The legacy impute-route shape shared by BIODIV: for each dependency
    dataset, extrapolate backward to ``years[0]``, forward to ``years[1]``,
    interpolate, and give every ``recipient_group`` member with no rows at
    all the reference-class mean; score the union with ``formula``; keep the
    scores that have at least one imputed input (legacy
    ``filter_imputations``)."""

    formula: Callable[..., Any]
    years: tuple[int, int]
    recipient_group: str
    auxiliary_datasets: tuple[str, ...] = ()

    def impute(self, context: IndicatorImputationContext) -> IndicatorImputationResult:
        start, end = self.years
        combined: list[Observation] = []
        for code in context.definition.dataset_codes:
            combined.extend(impute_dataset(context.dataset(code), code, context.recipients, start, end).combined)
        scored = score_indicator(combined, context.definition.code, self.formula, context.definition.unit)
        return IndicatorImputationResult(tuple(s for s in scored.scored if is_imputed(s)), tuple(scored.unscored))
