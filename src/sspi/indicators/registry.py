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

Imputation is optional. A legacy indicator with no impute route is declared
with ``imputed_score=None, imputation_years=None, recipient_group=None``;
the three are present together or absent together.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sspi.errors import IndicatorDefinitionError, UnknownCodeError

# Every legacy impute route hard-coded these two facts.
LEGACY_IMPUTATION_YEARS: tuple[int, int] = (2000, 2023)
LEGACY_RECIPIENT_GROUP = "SSPI67"


def _parameter_names(function: Callable[..., Any]) -> tuple[str, ...]:
    return tuple(inspect.signature(function).parameters)


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    """One executable indicator.

    ``observed_score`` is the legacy compute-route formula and
    ``imputed_score`` the legacy impute-route formula; where a legacy route
    used one formula for both, the same callable is passed twice. Both take
    dataset codes as parameter names, in the same set.

    An indicator whose legacy implementation has no impute route passes
    ``None`` for ``imputed_score``, ``imputation_years`` and
    ``recipient_group``, all three.

    ``goalposts`` declares the indicator-level (lower, upper) goalposts the
    formula hard-codes, where the legacy route read them from metadata at
    runtime; :meth:`check_against` compares them with the catalog. ``None``
    declares nothing and checks nothing.
    """

    code: str
    observed_score: Callable[..., Any]
    imputed_score: Callable[..., Any] | None
    unit: str = "Index"
    imputation_years: tuple[int, int] | None = LEGACY_IMPUTATION_YEARS
    recipient_group: str | None = LEGACY_RECIPIENT_GROUP
    goalposts: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise IndicatorDefinitionError("indicator code must be a non-empty string")
        if not callable(self.observed_score):
            raise IndicatorDefinitionError(f"{self.code}: observed_score must be callable")
        if self.goalposts is not None and len(tuple(self.goalposts)) != 2:
            raise IndicatorDefinitionError(f"{self.code}: goalposts must be a (lower, upper) pair, got {self.goalposts!r}")
        configuration = {"imputed_score": self.imputed_score, "imputation_years": self.imputation_years, "recipient_group": self.recipient_group}
        absent = sorted(name for name, value in configuration.items() if value is None)
        if len(absent) == len(configuration):
            return
        if absent:
            raise IndicatorDefinitionError(
                f"{self.code}: imputation configuration must be complete or entirely absent; "
                f"missing {absent} while {sorted(set(configuration) - set(absent))} are set"
            )
        if not callable(self.imputed_score):
            raise IndicatorDefinitionError(f"{self.code}: imputed_score must be callable")
        observed, imputed = _parameter_names(self.observed_score), _parameter_names(self.imputed_score)
        if set(observed) != set(imputed):
            raise IndicatorDefinitionError(
                f"{self.code}: observed_score and imputed_score must take the same parameter names "
                f"(dataset codes), got {list(observed)} and {list(imputed)}"
            )
        start, end = self.imputation_years
        if start > end:
            raise IndicatorDefinitionError(f"{self.code}: imputation_years start must not exceed end, got {self.imputation_years!r}")

    @property
    def imputes(self) -> bool:
        """Whether the indicator has any imputation behaviour."""
        return self.imputed_score is not None

    @property
    def dataset_codes(self) -> tuple[str, ...]:
        """Dataset codes the implementation consumes, in observed-score parameter order."""
        return _parameter_names(self.observed_score)

    def check_against(self, catalog: Any) -> None:
        """Raise ``IndicatorDefinitionError`` unless the catalog declares
        exactly the datasets the implementation consumes and, where the
        definition declares goalposts, the same goalposts. Raises
        ``UnknownCodeError`` if the catalog has no such indicator."""
        indicator = catalog.indicator(self.code)
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
    from sspi.indicators import biodiv, redlst  # local import keeps the module graph acyclic

    return {d.code: d for d in (biodiv.DEFINITION, redlst.DEFINITION)}


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
