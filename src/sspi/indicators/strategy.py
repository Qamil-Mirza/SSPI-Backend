"""Indicator-level imputation strategies: how an indicator produces its
imputed scores after the observed scoring pass.

This is orchestration owned by the indicator layer. It is distinct from
``sspi.imputation``, which imputes *observations* (series extrapolation,
interpolation, reference-class means) and whose result type is
``sspi.imputation.ImputationResult``. A strategy decides which of those
primitives to apply, to which countries, and how to turn the outcome into
``IndicatorScore`` rows; its result type is :class:`IndicatorImputationResult`.

Every strategy is pure Python: no database, no network, no catalog access.
The generic runner supplies everything a strategy declares it needs
(:attr:`ImputationStrategy.auxiliary_datasets`,
:attr:`ImputationStrategy.recipient_group`) and calls :meth:`impute` once.
Indicator-specific behaviour, including any hard-coded recipient list the
legacy route had, lives in the strategy instance, never in the runner.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sspi.imputation import impute_dataset, is_imputed
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
