"""Canonical datasets derived from another canonical dataset's observations.

Some legacy cleaners did not select a source series; they selected one and
then computed a new series from it. Those transforms are executable
methodology, so they live here as plain Python, one named function per
transform, bound to a dataset code in :data:`DERIVATIONS`. There is no
expression language and no discovery: a derived dataset is one that appears
in that mapping.

Ingesting a derived dataset means: fetch the base dataset's source query,
normalize it exactly as the base dataset, then apply the transform. The base
dataset itself is written only if it was requested too.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sspi.errors import NormalizationError
from sspi.metadata import DatasetMetadata
from sspi.scoring import Observation

Transform = Callable[[DatasetMetadata, Sequence[Observation]], list[Observation]]


@dataclass(frozen=True, slots=True)
class Derivation:
    """How one canonical dataset is computed from another."""

    code: str  # the derived dataset
    base: str  # the canonical dataset whose normalized observations feed the transform
    transform: Transform


def baseline_change_2000_2005(dataset: DatasetMetadata, base: Sequence[Observation]) -> list[Observation]:
    """Legacy ``clean_unsdg_cwueff`` transform: per country, the mean of the
    2000-2005 values is the baseline; every year from 2006 on becomes the
    percent change from that baseline, ``(value - baseline) / baseline * 100``,
    or 0 when the baseline is 0. Countries with no 2000-2005 value produce
    nothing. Years before 2006 are not emitted."""
    baseline_years, first_year = (2000, 2005), 2006
    by_country: dict[str, list[Observation]] = {}
    for observation in base:
        by_country.setdefault(observation.country_code, []).append(observation)

    derived: list[Observation] = []
    for country, observations in by_country.items():
        if len({o.dataset_code for o in observations}) != 1:
            raise NormalizationError(f"{dataset.code}: base observations for {country} mix datasets")
        baseline_values = [o.value for o in observations if baseline_years[0] <= o.year <= baseline_years[1]]
        if not baseline_values:
            continue
        baseline = sum(baseline_values) / len(baseline_values)
        for observation in observations:
            if observation.year < first_year:
                continue
            change = ((observation.value - baseline) / baseline) * 100 if baseline != 0 else 0
            provenance = dict(observation.provenance)
            provenance.update(
                {
                    "derived_from": observation.dataset_code,
                    "derivation": "baseline_change_2000_2005",
                    "baseline_years": list(baseline_years),
                    "baseline_value": baseline,
                    "baseline_observation_count": len(baseline_values),
                    "source_value": observation.value,
                    "source_unit": observation.unit,
                }
            )
            derived.append(Observation(dataset.code, country, observation.year, float(change), dataset.unit, provenance))
    derived.sort(key=lambda o: (o.country_code, o.year))
    return derived


DERIVATIONS: dict[str, Derivation] = {
    "UNSDG_CWUEFF": Derivation("UNSDG_CWUEFF", "UNSDG_WUSEFF", baseline_change_2000_2005),
}
