"""Executable indicator registry: indicator code -> Python implementation.

The metadata catalog describes indicators (name, dependencies, the formula as
text). This module is the first and only place that binds a code to code.
It is a literal mapping, not a plugin system, and importing it touches no
database, network or metadata file.

An ``IndicatorDefinition`` carries only what the runtime needs. Dataset
dependencies are not stored: the score functions bind their arguments by
parameter name, so their parameter names *are* the implementation's
dependency declaration, and :meth:`IndicatorDefinition.check_against`
verifies them against the catalog.

Imputation is optional and, where present, is an :class:`ImputationStrategy`
from ``sspi.indicators.strategy`` (or an indicator's own module): the
executable methodology of the legacy impute route. A legacy indicator with no
impute route has ``imputation=None``.

An imputation procedure may also read the persisted scores of other
indicators (legacy GINIPT regresses its scores on ISHRAT scores). Those are
declared as ``score_dependencies``; the runner loads them and hands them to
the strategy. Nothing runs a dependency automatically.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sspi.errors import IndicatorDefinitionError, UnknownCodeError
from sspi.indicators.strategy import ImputationStrategy

# The legacy impute routes that use a group hard-coded these two facts.
LEGACY_IMPUTATION_YEARS: tuple[int, int] = (2000, 2023)
LEGACY_RECIPIENT_GROUP = "SSPI67"


def _parameter_names(function: Callable[..., Any]) -> tuple[str, ...]:
    return tuple(inspect.signature(function).parameters)


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    """One executable indicator.

    ``observed_score`` is the legacy compute-route formula; its parameter
    names are dataset codes. ``imputation`` is the legacy impute route as an
    :class:`ImputationStrategy`, or ``None`` for an indicator that has none.

    ``goalposts`` declares the indicator-level (lower, upper) goalposts the
    formula hard-codes, where the legacy route read them from metadata at
    runtime; :meth:`check_against` compares them with the catalog. ``None``
    declares nothing and checks nothing.

    ``observation_filter`` is the legacy compute route's pre-selection of
    canonical rows, where one existed (DEFRST and CARBON keep level rows
    from 2000 on): a predicate on one ``Observation``, applied before the
    observed scoring pass only. The imputation strategy still receives
    every canonical row, as the legacy impute routes read the clean
    collections unfiltered. ``None`` keeps everything.

    ``computed_series`` are the series the legacy compute route derived
    inside each country-year group and stored beside the inputs (ALTNRG
    stores the percentage it scores): ``sspi.scoring.ComputedSeries``
    entries, added in the observed scoring pass only, as the legacy impute
    routes did not compute them.

    ``score_dependencies`` are the codes of other indicators whose
    persisted scores the imputation strategy reads (the legacy impute route
    queried the indicator collection for them). They must already exist
    when this indicator runs; running it never runs them. Only a definition
    with an imputation strategy may declare any.
    """

    code: str
    observed_score: Callable[..., Any]
    imputation: ImputationStrategy | None = None
    unit: str = "Index"
    goalposts: tuple[float, float] | None = None
    observation_filter: Callable[[Any], bool] | None = None
    score_dependencies: tuple[str, ...] = ()
    computed_series: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise IndicatorDefinitionError("indicator code must be a non-empty string")
        if not callable(self.observed_score):
            raise IndicatorDefinitionError(f"{self.code}: observed_score must be callable")
        if self.observation_filter is not None and not callable(self.observation_filter):
            raise IndicatorDefinitionError(f"{self.code}: observation_filter must be callable or None")
        if self.goalposts is not None and len(tuple(self.goalposts)) != 2:
            raise IndicatorDefinitionError(f"{self.code}: goalposts must be a (lower, upper) pair, got {self.goalposts!r}")
        if not isinstance(self.computed_series, tuple) or any(not hasattr(series, "value_function") for series in self.computed_series):
            raise IndicatorDefinitionError(f"{self.code}: computed_series must be a tuple of ComputedSeries, got {self.computed_series!r}")
        clash = sorted({series.dataset_code for series in self.computed_series} & set(self.dataset_codes))
        if clash:
            raise IndicatorDefinitionError(f"{self.code}: computed series must not reuse the code of a dependency dataset, got {clash}")
        dependencies = self.score_dependencies
        if not isinstance(dependencies, tuple) or any(not isinstance(code, str) or not code for code in dependencies):
            raise IndicatorDefinitionError(f"{self.code}: score_dependencies must be a tuple of indicator codes, got {dependencies!r}")
        if len(set(dependencies)) != len(dependencies) or self.code in dependencies:
            raise IndicatorDefinitionError(f"{self.code}: score dependencies must be distinct indicators other than itself, got {list(dependencies)}")
        if dependencies and self.imputation is None:
            raise IndicatorDefinitionError(f"{self.code}: score dependencies are read by the imputation strategy; a definition without one cannot declare {list(dependencies)}")
        if self.imputation is not None:
            if not isinstance(self.imputation, ImputationStrategy):
                raise IndicatorDefinitionError(
                    f"{self.code}: imputation must be an ImputationStrategy (auxiliary_datasets, recipient_group, impute), got {type(self.imputation).__name__}"
                )
            auxiliary = tuple(self.imputation.auxiliary_datasets)
            overlap = sorted(set(auxiliary) & set(self.dataset_codes))
            if overlap or len(set(auxiliary)) != len(auxiliary):
                raise IndicatorDefinitionError(f"{self.code}: auxiliary datasets must be distinct and not already dependencies, got {list(auxiliary)}")

    @property
    def imputes(self) -> bool:
        """Whether the indicator has any imputation behaviour."""
        return self.imputation is not None

    @property
    def auxiliary_datasets(self) -> tuple[str, ...]:
        """Extra datasets the imputation strategy reads; empty without a strategy."""
        return tuple(self.imputation.auxiliary_datasets) if self.imputation is not None else ()

    @property
    def recipient_group(self) -> str | None:
        """Country group the imputation strategy asks for, if any."""
        return self.imputation.recipient_group if self.imputation is not None else None

    @property
    def dataset_codes(self) -> tuple[str, ...]:
        """Dataset codes the implementation consumes, in observed-score parameter order."""
        return _parameter_names(self.observed_score)

    def check_against(self, catalog: Any) -> None:
        """Raise ``IndicatorDefinitionError`` unless the catalog declares
        exactly the datasets the implementation consumes, knows every
        auxiliary dataset the strategy reads and every indicator it depends
        on for scores and, where the definition declares goalposts, the same
        goalposts. Raises ``UnknownCodeError`` if the catalog has no such
        indicator, auxiliary dataset or score dependency."""
        indicator = catalog.indicator(self.code)
        for code in self.auxiliary_datasets:
            catalog.dataset(code)
        for code in self.score_dependencies:
            catalog.indicator(code)
        if self.goalposts is not None:
            canonical = (indicator.lower_goalpost, indicator.upper_goalpost)
            if canonical != tuple(self.goalposts):
                raise IndicatorDefinitionError(
                    f"{self.code}: executable definition and metadata disagree on goalposts; "
                    f"metadata declares {canonical}, implementation uses {tuple(self.goalposts)}"
                )
        declared = set(indicator.dataset_codes)
        implemented = set(self.dataset_codes)
        if declared != implemented:
            raise IndicatorDefinitionError(
                f"{self.code}: executable definition and metadata disagree on dataset dependencies; "
                f"metadata declares {sorted(declared)}, implementation consumes {sorted(implemented)} "
                f"(missing from implementation: {sorted(declared - implemented)}, "
                f"not declared in metadata: {sorted(implemented - declared)})"
            )


def _definitions() -> dict[str, IndicatorDefinition]:
    from sspi.indicators import airpol, altnrg, biodiv, carbon, chmpol, colbar, defrst, employ, ginipt, ishrat, nitrog, nrgint, redlst, watman  # local import keeps the module graph acyclic

    return {
        d.code: d
        for d in (
            biodiv.DEFINITION,
            redlst.DEFINITION,
            chmpol.DEFINITION,
            watman.DEFINITION,
            nitrog.DEFINITION,
            defrst.DEFINITION,
            carbon.DEFINITION,
            ishrat.DEFINITION,
            ginipt.DEFINITION,
            employ.DEFINITION,
            colbar.DEFINITION,
            altnrg.DEFINITION,
            nrgint.DEFINITION,
            airpol.DEFINITION,
        )
    }


def get(code: str) -> IndicatorDefinition:
    """The executable definition for ``code``. Raises ``UnknownCodeError``
    for an indicator with no registered implementation."""
    try:
        return _definitions()[code]
    except KeyError:
        raise UnknownCodeError(f"no executable definition registered for indicator {code!r}; registered: {list(codes())}") from None


def codes() -> tuple[str, ...]:
    """Registered indicator codes, in registration order."""
    return tuple(_definitions())
