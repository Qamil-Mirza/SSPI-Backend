"""Test-only adapter between the legacy Mongo document shape and the new
scoring-kernel types.

The old pipeline consumed and produced lists of dicts shaped like the
`sspi_clean_api_data` / `sspi_indicator_data` Mongo documents. The new kernel
does not know that shape. These helpers let the ported characterization tests
and the golden fixture keep using the old fixtures while asserting against the
new API. Nothing here is production code.

Boundary behaviour reproduced on purpose (it is what the old
`convert_data_types` + `validate_dataset_list` did before scoring):

- ``Year`` is coerced with ``int()`` and ``Value`` with ``float()``; so a
  ``None`` value raises ``TypeError`` and junk text raises ``ValueError``,
  exactly as the old tests pin.
- Missing ``DatasetCode`` / ``CountryCode`` / ``Year`` / ``Value`` / ``Unit``
  keys raise ``InvalidObservationError`` (old: ``InvalidDocumentFormatError``).
- Every other key is carried into ``Observation.provenance``.
"""

from __future__ import annotations

from typing import Any

from sspi.errors import InvalidObservationError
from sspi.scoring import (
    ComputedValue,
    IndicatorScore,
    Observation,
    ScoringResult,
    UnscoredGroup,
)

CORE_KEYS = ("DatasetCode", "CountryCode", "Year", "Value", "Unit")


def observation_from_document(doc: dict[str, Any]) -> Observation:
    for key in ("DatasetCode", "CountryCode", "Year", "Value", "Unit"):
        if key not in doc:
            raise InvalidObservationError(f"'{key}' is a required argument")
    provenance = {k: v for k, v in doc.items() if k not in CORE_KEYS}
    return Observation(
        dataset_code=doc["DatasetCode"],
        country_code=doc["CountryCode"],
        year=int(doc["Year"]),
        value=float(doc["Value"]),
        unit=doc["Unit"],
        provenance=provenance,
    )


def observations_from_documents(docs: list[dict[str, Any]]) -> list[Observation]:
    return [observation_from_document(d) for d in docs]


def document_from_observation(obs: Observation) -> dict[str, Any]:
    doc = {
        "DatasetCode": obs.dataset_code,
        "CountryCode": obs.country_code,
        "Year": obs.year,
        "Value": obs.value,
        "Unit": obs.unit,
    }
    doc.update(obs.provenance)
    return doc


def document_from_computed(group_country: str, group_year: int, cv: ComputedValue) -> dict[str, Any]:
    return {
        "DatasetCode": cv.dataset_code,
        "CountryCode": group_country,
        "Year": group_year,
        "Value": cv.value,
        "Unit": cv.unit,
        "Computed": True,
    }


def _datasets(country: str, year: int, inputs, computed) -> list[dict[str, Any]]:
    return [document_from_observation(o) for o in inputs] + [
        document_from_computed(country, year, c) for c in computed
    ]


def document_from_score(score: IndicatorScore) -> dict[str, Any]:
    return {
        "IndicatorCode": score.indicator_code,
        "CountryCode": score.country_code,
        "Year": score.year,
        "Datasets": _datasets(score.country_code, score.year, score.inputs, score.computed),
        "Unit": score.unit,
        "Score": score.score,
    }


def document_from_unscored(group: UnscoredGroup) -> dict[str, Any]:
    return {
        "IndicatorCode": group.indicator_code,
        "CountryCode": group.country_code,
        "Year": group.year,
        "Datasets": _datasets(group.country_code, group.year, group.inputs, group.computed),
    }


def documents_from_result(result: ScoringResult) -> tuple[list[dict], list[dict]]:
    """Return ``(complete, incomplete)`` in the old `score_indicator` shape."""
    return (
        [document_from_score(s) for s in result.scored],
        [document_from_unscored(u) for u in result.unscored],
    )
