"""Pure imputation over ``Observation`` records, reproducing the legacy SSPI
imputation helpers exactly.

Ports of ``impute_reference_class_average``, ``extrapolate_backward``,
``extrapolate_forward`` and ``interpolate_linear`` from the legacy
``api/resources/utilities.py``, plus ``impute_dataset``, which chains them in
the order the legacy ``impute_biodiv`` route did:

    reference class (from the untouched observed rows, for every recipient
    with no observation at all) -> backward -> forward -> interpolation,
    each time-series step seeing the running combined list.

Formulas, bounds and method names are the legacy ones. Observed records are
never modified, replaced or returned as imputed. Every function returns only
the records it adds, as immutable tuples, in a deterministic order: series in
first-appearance order, years ascending, recipients sorted.

Provenance of an imputed record is the anchor record's provenance (the
legacy helpers deep-copied the anchor document) plus ``imputed: True``, the
legacy ``imputation_method`` string, the legacy ``imputation_distance`` where
one existed, and the anchor years and values needed to reconstruct the
value. Reference-class records carry no anchor provenance, as in legacy.

This module imports nothing that touches a database, the network, metadata
files or the ingestion layer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, NamedTuple

from sspi.errors import ImputationError
from sspi.scoring import Observation

# Legacy ImputationMethod strings, verbatim.
REFERENCE_CLASS_AVERAGE = "ImputeReferenceClassAverage"
BACKWARD_EXTRAPOLATION = "Backward Extrapolation"
FORWARD_EXTRAPOLATION = "Forward Extrapolation"
LINEAR_INTERPOLATION = "Linear Interpolation"


class ImputationResult(NamedTuple):
    """Observed records as given, and the records imputation added."""

    observed: tuple[Observation, ...]
    imputed: tuple[Observation, ...]

    @property
    def combined(self) -> tuple[Observation, ...]:
        return self.observed + self.imputed


# --------------------------------------------------------------------------- #
# Reference class
# --------------------------------------------------------------------------- #


def reference_class_average(
    country_code: str,
    dataset_code: str,
    start_year: int,
    end_year: int,
    reference: Iterable[Observation],
) -> tuple[Observation, ...]:
    """One flat mean of every reference value, assigned to each year from
    ``start_year`` to ``end_year`` inclusive.

    The reference is used exactly as supplied: all countries, all years,
    whether or not they fall inside the requested range, the target country
    included if present. Only units are checked, as in legacy.
    """
    reference = list(reference)
    if not reference:
        raise ImputationError(f"reference data for {dataset_code}/{country_code} is empty")
    unit = reference[0].unit
    if any(o.unit != unit for o in reference):
        raise ImputationError(f"units are not consistent across reference data for {dataset_code}: {sorted({o.unit for o in reference})}")
    mean = sum(o.value for o in reference) / len(reference)
    provenance = {
        "imputed": True,
        "imputation_method": REFERENCE_CLASS_AVERAGE,
        "reference_observation_count": len(reference),
        "requested_years": [start_year, end_year],  # lists, not tuples: provenance must survive a JSON round trip
    }
    return tuple(Observation(dataset_code, country_code, year, mean, unit, provenance) for year in range(start_year, end_year + 1))


# --------------------------------------------------------------------------- #
# Time-series helpers
# --------------------------------------------------------------------------- #


def _series(observations: Iterable[Observation]) -> dict[tuple[str, str], list[Observation]]:
    """Group by (country, dataset) in first-appearance order, each sorted by year."""
    grouped: dict[tuple[str, str], list[Observation]] = {}
    for o in observations:
        grouped.setdefault((o.country_code, o.dataset_code), []).append(o)
    for key, series in grouped.items():
        series.sort(key=lambda o: o.year)  # stable, like the legacy in-place sort
        for earlier, later in zip(series, series[1:]):
            if earlier.year == later.year:
                raise ImputationError(f"duplicate identity {key[1]}/{key[0]}/{earlier.year} in imputation input")
    return grouped


def _imputed(anchor: Observation, year: int, value: float, **fields) -> Observation:
    provenance = dict(anchor.provenance)
    provenance.update({"imputed": True, **fields})
    return Observation(anchor.dataset_code, anchor.country_code, year, value, anchor.unit, provenance)


def extrapolate_backward(observations: Iterable[Observation], start_year: int) -> tuple[Observation, ...]:
    """Carry each series' earliest value back to ``start_year``. Nothing is
    added for a series that already starts at or before ``start_year``."""
    added: list[Observation] = []
    for series in _series(observations).values():
        first = series[0]
        for year in range(start_year, first.year):
            added.append(_imputed(first, year, first.value, imputation_method=BACKWARD_EXTRAPOLATION, imputation_distance=first.year - year, anchor_year=first.year))
    return tuple(added)


def extrapolate_forward(observations: Iterable[Observation], end_year: int) -> tuple[Observation, ...]:
    """Carry each series' latest value forward to ``end_year``. Nothing is
    added for a series that already ends at or after ``end_year``."""
    added: list[Observation] = []
    for series in _series(observations).values():
        last = series[-1]
        for year in range(last.year + 1, end_year + 1):
            added.append(_imputed(last, year, last.value, imputation_method=FORWARD_EXTRAPOLATION, imputation_distance=year - last.year, anchor_year=last.year))
    return tuple(added)


def interpolate_linear(observations: Iterable[Observation]) -> tuple[Observation, ...]:
    """Fill every missing year strictly inside a series' observed span by
    linear interpolation between the nearest observed neighbours. Not
    bounded by any year range; the lower neighbour's provenance is carried."""
    added: list[Observation] = []
    for series in _series(observations).values():
        present = {o.year for o in series}
        for year in range(series[0].year, series[-1].year + 1):
            if year in present:
                continue
            prev = next(o for o in reversed(series) if o.year < year)
            nxt = next(o for o in series if o.year > year)
            slope = (nxt.value - prev.value) / (nxt.year - prev.year)
            value = prev.value + slope * (year - prev.year)
            added.append(
                _imputed(
                    prev,
                    year,
                    value,
                    imputation_method=LINEAR_INTERPOLATION,
                    imputation_distance=min(year - prev.year, nxt.year - year),
                    anchor_years=[prev.year, nxt.year],
                    anchor_values=[prev.value, nxt.value],
                )
            )
    return tuple(added)


# --------------------------------------------------------------------------- #
# Dataset-level composition
# --------------------------------------------------------------------------- #


def missing_countries(recipients: Iterable[str], observations: Iterable[Observation]) -> tuple[str, ...]:
    """Recipients with no observation at all in any year, sorted."""
    represented = {o.country_code for o in observations}
    return tuple(sorted(set(recipients) - represented))


def impute_dataset(
    observations: Iterable[Observation],
    dataset_code: str,
    recipients: Iterable[str],
    start_year: int,
    end_year: int,
) -> ImputationResult:
    """Legacy ``impute_biodiv`` treatment of one dataset.

    Recipients absent from the data get the reference-class average of every
    observed record for ``start_year``..``end_year``; every series present
    is then extrapolated backward to ``start_year``, forward to ``end_year``,
    and interpolated across interior gaps, in that order.
    """
    observed = tuple(observations)
    foreign = sorted({o.dataset_code for o in observed} - {dataset_code})
    if foreign:
        raise ImputationError(f"impute_dataset({dataset_code}) received observations for {foreign}")
    reference: list[Observation] = []
    for country in missing_countries(recipients, observed):
        reference.extend(reference_class_average(country, dataset_code, start_year, end_year, observed))
    backward = extrapolate_backward(observed, start_year)
    forward = extrapolate_forward(observed + backward, end_year)
    interpolated = interpolate_linear(observed + backward + forward)
    return ImputationResult(observed, tuple(reference) + backward + forward + interpolated)


# --------------------------------------------------------------------------- #
# Score classification
# --------------------------------------------------------------------------- #


def is_imputed(score_or_inputs: Any) -> bool:
    """Legacy ``filter_imputations`` rule: a score is imputed iff any input
    observation carries a truthy ``imputed`` provenance value.

    Accepts an ``IndicatorScore`` (its ``inputs`` are inspected; computed
    values carry no provenance and never count) or any iterable of
    ``Observation``. Classification is derived, never supplied by a caller.
    """
    inputs = getattr(score_or_inputs, "inputs", score_or_inputs)
    return any(bool(o.provenance.get("imputed", False)) for o in inputs)
