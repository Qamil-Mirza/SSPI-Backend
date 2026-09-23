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
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sspi.errors import IndicatorDefinitionError, UnknownCodeError

# Every legacy compute/impute route hard-coded these two facts.
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
    """

    code: str
    observed_score: Callable[..., Any]
    imputed_score: Callable[..., Any]
    unit: str = "Index"
    imputation_years: tuple[int, int] = LEGACY_IMPUTATION_YEARS
    recipient_group: str = LEGACY_RECIPIENT_GROUP

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise IndicatorDefinitionError("indicator code must be a non-empty string")
        for name in ("observed_score", "imputed_score"):
            if not callable(getattr(self, name)):
                raise IndicatorDefinitionError(f"{self.code}: {name} must be callable")
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
    def dataset_codes(self) -> tuple[str, ...]:
        """Dataset codes the implementation consumes, in observed-score parameter order."""
        return _parameter_names(self.observed_score)

    def check_against(self, catalog: Any) -> None:
        """Raise ``IndicatorDefinitionError`` unless the catalog declares
        exactly the datasets the implementation consumes. Raises
        ``UnknownCodeError`` if the catalog has no such indicator."""
        declared = set(catalog.indicator(self.code).dataset_codes)
        implemented = set(self.dataset_codes)
        if declared != implemented:
            raise IndicatorDefinitionError(
                f"{self.code}: executable definition and metadata disagree on dataset dependencies; "
                f"metadata declares {sorted(declared)}, implementation consumes {sorted(implemented)} "
                f"(missing from implementation: {sorted(declared - implemented)}, "
                f"not declared in metadata: {sorted(implemented - declared)})"
            )


def _definitions() -> dict[str, IndicatorDefinition]:
    from sspi.indicators import biodiv  # local import keeps the module graph acyclic

    return {d.code: d for d in (biodiv.DEFINITION,)}


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
