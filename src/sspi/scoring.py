"""Indicator scoring kernel.

Pure functions that turn dataset observations into indicator scores. No
database, no metadata, no pandas, no I/O. The behaviour is a faithful port of
``score_indicator`` and its helpers from the legacy Flask application, on a
storage-independent representation.

Pipeline::

    observations
      -> validate_observations   (duplicate identity check)
      -> group_observations      (one ObservationGroup per (country_code, year))
      -> add_computed_series     (derived series appended to each group)
      -> score_groups            (bind values to the score function by name)
      -> ScoringResult(scored, unscored)

Legacy behaviours preserved on purpose (see the migration notes):

* Score-function arguments are bound **by parameter name**: each parameter
  name must equal a dataset code present in the group. Parameters with
  defaults are still required.
* A group missing a required dataset is silently unscored, no exception.
* Exceptions raised by a *score* function propagate; exceptions raised by a
  computed-series *value* function are swallowed and the series is not added.
* A computed value whose type is not exactly ``int`` or ``float`` (so ``bool``
  and numpy scalars count as non-numeric) makes the whole group unscored.
* Whatever the score function returns is recorded as the score, including
  ``None``; the kernel does not validate scores. Range checks belong to the
  persistence layer.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, NamedTuple

from sspi.errors import InvalidObservationError

__all__ = [
    "ComputedSeries",
    "ComputedValue",
    "IndicatorScore",
    "Observation",
    "ObservationGroup",
    "ScoringResult",
    "UnscoredGroup",
    "UnscoredReason",
    "add_computed_series",
    "goalpost",
    "group_observations",
    "score_groups",
    "score_indicator",
    "validate_observations",
]

_EXACT_NUMERIC_TYPES = (int, float)


def _is_exactly_numeric(value: Any) -> bool:
    """Legacy check: ``type(v) in (int, float)``. Deliberately not isinstance."""
    return type(value) in _EXACT_NUMERIC_TYPES


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Observation:
    """One cleaned data point: a dataset's value for a country and year.

    Only invariants the scoring kernel relies on are enforced here: non-empty
    string identifiers, an ``int`` year, and a finite numeric value (stored as
    ``float``). ``provenance`` is an opaque mapping carried through untouched
    (imputation flags, descriptions, source identifiers, ...).
    """

    dataset_code: str
    country_code: str
    year: int
    value: float
    unit: str
    provenance: Mapping[str, Any] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_code, str) or not self.dataset_code:
            raise InvalidObservationError("dataset_code must be a non-empty string")
        if not isinstance(self.country_code, str) or not self.country_code:
            raise InvalidObservationError("country_code must be a non-empty string")
        if isinstance(self.year, bool) or not isinstance(self.year, int):
            raise InvalidObservationError("year must be an int")
        value = self.value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise InvalidObservationError("value must be a finite int or float")
        object.__setattr__(self, "value", float(value))
        if not isinstance(self.provenance, Mapping):
            raise InvalidObservationError("provenance must be a mapping")
        # Copy, then freeze: the record cannot change under the caller's feet
        # and the caller's dict cannot change the record.
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True, slots=True)
class ComputedSeries:
    """Specification of a series derived from other datasets in the same group.

    ``value_function`` parameter names must equal dataset codes. Its return
    value is recorded as-is (legacy); a non-numeric result vetoes scoring of
    the group rather than raising.
    """

    dataset_code: str
    unit: str
    value_function: Callable[..., Any]

    def __post_init__(self) -> None:
        if not callable(self.value_function):
            raise TypeError("value_function must be callable")


@dataclass(frozen=True, slots=True)
class ComputedValue:
    """A computed series value attached to one group.

    ``value`` is ``Any`` for legacy compatibility: the old pipeline stored the
    value function's return unchecked and only vetoed scoring when it was not
    exactly ``int``/``float``.
    """

    dataset_code: str
    value: Any
    unit: str


@dataclass(frozen=True, slots=True)
class ObservationGroup:
    """All observations (and computed values) for one indicator, country and year."""

    indicator_code: str
    country_code: str
    year: int
    inputs: tuple[Observation, ...]
    computed: tuple[ComputedValue, ...] = ()


class UnscoredReason(str, Enum):
    """Machine-readable reason a group could not be scored."""

    MISSING_DATASETS = "missing_datasets"
    NON_NUMERIC_COMPUTED_VALUE = "non_numeric_computed_value"


@dataclass(frozen=True, slots=True)
class IndicatorScore:
    """A scored (indicator, country, year) with the inputs that produced it.

    ``score`` is typed ``Any`` on purpose. The legacy pipeline recorded
    whatever the score function returned, including ``None``, and validated
    the numeric range only at persistence time. That looseness is preserved
    here so the kernel characterizes the old behaviour exactly; tightening it
    is a methodology decision to be taken separately.

    ``unit`` is the string given to ``score_groups`` or, for a callable unit,
    that callable's return value recorded without validation.
    """

    indicator_code: str
    country_code: str
    year: int
    score: Any
    unit: str
    inputs: tuple[Observation, ...]
    computed: tuple[ComputedValue, ...] = ()


@dataclass(frozen=True, slots=True)
class UnscoredGroup:
    """A group that could not be scored, with a structured reason.

    ``details`` holds the dataset codes involved: the missing codes in
    score-function signature order for ``MISSING_DATASETS``, or the computed
    codes whose values were non-numeric for ``NON_NUMERIC_COMPUTED_VALUE``.
    """

    indicator_code: str
    country_code: str
    year: int
    inputs: tuple[Observation, ...]
    computed: tuple[ComputedValue, ...]
    reason: UnscoredReason
    details: tuple[str, ...]


class ScoringResult(NamedTuple):
    scored: list[IndicatorScore]
    unscored: list[UnscoredGroup]


# --------------------------------------------------------------------------- #
# Goalposting
# --------------------------------------------------------------------------- #


def goalpost(value, lower, upper) -> float:
    """Linear goalpost normalisation clamped to [0, 1].

    Formula: ``max(0, min(1, (value - lower) / (upper - lower)))``.
    ``lower > upper`` inverts the scale (less is better); there is no separate
    inversion flag anywhere in the methodology.

    Raises ``ValueError`` on a NaN value or NaN bound. Equal bounds return 0.5
    when the value equals them and clamp otherwise. An infinite intermediate
    result clamps to the corresponding bound.
    """
    if math.isnan(value):
        raise ValueError("goalpost() received NaN value - check upstream data")
    if math.isnan(lower) or math.isnan(upper):
        raise ValueError("goalpost() received NaN goalpost bounds")
    if upper == lower:
        if value == lower:
            return 0.5
        return 1.0 if value > upper else 0.0
    normalized = (value - lower) / (upper - lower)
    if math.isinf(normalized):
        return 1.0 if normalized > 0 else 0.0
    return max(0.0, min(1.0, normalized))


# --------------------------------------------------------------------------- #
# Pipeline stages
# --------------------------------------------------------------------------- #


def validate_observations(observations: Iterable[Observation]) -> None:
    """Check that every item is an ``Observation`` and identities are unique.

    Identity is ``(dataset_code, country_code, year)``. Field-level invariants
    are already enforced by ``Observation`` itself.
    """
    seen: set[tuple[str, str, int]] = set()
    for index, obs in enumerate(observations):
        if not isinstance(obs, Observation):
            raise TypeError(f"observation {index} is {type(obs).__name__}, expected Observation")
        key = (obs.dataset_code, obs.country_code, obs.year)
        if key in seen:
            raise InvalidObservationError(f"duplicate observation identity {key} at position {index}")
        seen.add(key)


def group_observations(observations: Iterable[Observation], indicator_code: str) -> list[ObservationGroup]:
    """Group observations by ``(country_code, year)``.

    Groups appear in first-seen order; inputs keep input order and duplicates.
    """
    buckets: dict[tuple[str, int], list[Observation]] = {}
    for obs in observations:
        buckets.setdefault((obs.country_code, obs.year), []).append(obs)
    return [
        ObservationGroup(indicator_code, country_code, year, tuple(inputs))
        for (country_code, year), inputs in buckets.items()
    ]


def _parameter_names(function: Callable[..., Any]) -> list[str]:
    return list(inspect.signature(function).parameters.keys())


def _bound_values(group: ObservationGroup) -> dict[str, Any]:
    """``{dataset_code: value}`` for a group; computed values come last and win."""
    values: dict[str, Any] = {obs.dataset_code: obs.value for obs in group.inputs}
    for computed in group.computed:
        values[computed.dataset_code] = computed.value
    return values


def _as_computed_series(spec: ComputedSeries | Sequence[Any]) -> ComputedSeries:
    if isinstance(spec, ComputedSeries):
        return spec
    if isinstance(spec, (tuple, list)) and len(spec) == 3:
        return ComputedSeries(*spec)
    raise TypeError("computed series spec must be a ComputedSeries or a (code, unit, function) triple")


def add_computed_series(
    groups: Iterable[ObservationGroup],
    specs: Iterable[ComputedSeries | Sequence[Any]],
) -> list[ObservationGroup]:
    """Return new groups with each computed series appended in spec order.

    For each spec and group: skip the group if any value already present is
    non-numeric, if a required dataset is missing, or if the value function
    raises. Nothing partial is recorded in those cases. Input groups are not
    mutated.
    """
    result = list(groups)
    for spec in (_as_computed_series(s) for s in specs):
        parameter_names = _parameter_names(spec.value_function)
        updated: list[ObservationGroup] = []
        for group in result:
            values = _bound_values(group)
            if any(not _is_exactly_numeric(v) for v in values.values()):
                updated.append(group)
                continue
            try:
                args = [values[name] for name in parameter_names]
            except KeyError:
                updated.append(group)
                continue
            try:
                value = spec.value_function(*args)
            except Exception:  # noqa: BLE001 - legacy: any value-function error means "no series"
                updated.append(group)
                continue
            computed = ComputedValue(spec.dataset_code, value, spec.unit)
            updated.append(replace(group, computed=group.computed + (computed,)))
        result = updated
    return result


def score_groups(
    groups: Iterable[ObservationGroup],
    score_function: Callable[..., Any],
    unit: str | Callable[..., str],
) -> ScoringResult:
    """Apply ``score_function`` to every group, binding arguments by name.

    ``unit`` is either a string used verbatim or a callable invoked with the
    same positional arguments as ``score_function``. Exceptions from either
    callable propagate.
    """
    if not (isinstance(unit, str) or callable(unit)):
        raise TypeError("unit must be a str or a callable")
    parameter_names = _parameter_names(score_function)
    scored: list[IndicatorScore] = []
    unscored: list[UnscoredGroup] = []
    for group in groups:
        values = _bound_values(group)
        non_numeric = tuple(code for code, v in values.items() if not _is_exactly_numeric(v))
        if non_numeric:
            unscored.append(_unscored(group, UnscoredReason.NON_NUMERIC_COMPUTED_VALUE, non_numeric))
            continue
        missing = tuple(name for name in parameter_names if name not in values)
        if missing:
            unscored.append(_unscored(group, UnscoredReason.MISSING_DATASETS, missing))
            continue
        args = [values[name] for name in parameter_names]
        score = score_function(*args)
        resolved_unit = unit if isinstance(unit, str) else unit(*args)
        scored.append(
            IndicatorScore(
                indicator_code=group.indicator_code,
                country_code=group.country_code,
                year=group.year,
                score=score,
                unit=resolved_unit,
                inputs=group.inputs,
                computed=group.computed,
            )
        )
    return ScoringResult(scored, unscored)


def _unscored(group: ObservationGroup, reason: UnscoredReason, details: tuple[str, ...]) -> UnscoredGroup:
    return UnscoredGroup(
        indicator_code=group.indicator_code,
        country_code=group.country_code,
        year=group.year,
        inputs=group.inputs,
        computed=group.computed,
        reason=reason,
        details=details,
    )


def score_indicator(
    observations: Iterable[Observation],
    indicator_code: str,
    score_function: Callable[..., Any],
    unit: str | Callable[..., str],
    computed_series: Iterable[ComputedSeries | Sequence[Any]] = (),
) -> ScoringResult:
    """Score one indicator from its dataset observations.

    Equivalent to the legacy ``score_indicator``: validate, group by country
    and year, add computed series, then score each group.
    """
    observations = list(observations)
    validate_observations(observations)
    groups = group_observations(observations, indicator_code)
    groups = add_computed_series(groups, computed_series)
    return score_groups(groups, score_function, unit)
