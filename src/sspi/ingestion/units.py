"""Source units and values for the normalizers whose legacy cleaner did not
store the source's own figures.

Canonical metadata may say, per dataset, that the source labels its rows
with a different unit from the canonical one (``source.published_unit``) and
that the legacy cleaner multiplied every value by a constant
(``source.value_multiplier``). A normalizer checks each row's unit against
:func:`expected_source_unit`, stores :func:`stored_value`, writes the
dataset's canonical unit and adds :func:`conversion_provenance`. For a
dataset with neither field nothing changes: the row's unit must be the
canonical unit and the value is stored as published.

The multiplication is the legacy one, ``value * multiplier`` on the parsed
value, nothing more: no unit arithmetic is inferred from the labels.
"""

from __future__ import annotations

from typing import Any

from sspi.metadata import DatasetMetadata


def expected_source_unit(dataset: DatasetMetadata) -> str | None:
    """The unit the source's rows must carry for this dataset."""
    return dataset.source.published_unit if dataset.source.published_unit is not None else dataset.unit


def unit_expectation(dataset: DatasetMetadata) -> str:
    """How a unit mismatch is explained in an error message."""
    if dataset.source.published_unit is None:
        return f"canonical unit {dataset.unit!r}"
    return f"published unit {dataset.source.published_unit!r} declared for canonical unit {dataset.unit!r}"


def stored_value(dataset: DatasetMetadata, value: float) -> float:
    """The value as the legacy cleaner stored it."""
    multiplier = dataset.source.value_multiplier
    return value if multiplier is None else value * multiplier


def conversion_provenance(dataset: DatasetMetadata, source_unit: Any, source_value: float) -> dict[str, Any]:
    """Provenance recording the published unit and value, only for a dataset that declares a conversion."""
    provenance: dict[str, Any] = {}
    if dataset.source.published_unit is not None:
        provenance["source_unit"] = source_unit
    if dataset.source.value_multiplier is not None:
        provenance["source_value"] = source_value
        provenance["value_multiplier"] = dataset.source.value_multiplier
    return provenance
