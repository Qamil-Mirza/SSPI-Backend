"""Typed, immutable records for the SSPI methodology metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Where a dataset's raw data comes from.

    ``query_code`` is ``None`` for datasets whose legacy definition never
    recorded how to collect them. ``dimensions`` are exact-match source
    dimension filters (for example ``{"activity": "TOTAL"}``) that select one
    slice of a series which the source publishes in several; the normalizer
    applies them before checking for duplicate identities. ``organization_name``,
    ``base_url``, ``format`` and ``note`` are optional descriptive extras
    carried over from the legacy source blocks.

    ``published_unit`` and ``value_multiplier`` describe a legacy cleaner
    that did not store the source's own figures: ``published_unit`` is the
    unit the source labels its rows with, when that differs from the
    dataset's canonical ``unit`` (the label the legacy cleaner wrote), and
    ``value_multiplier`` is the factor the legacy cleaner multiplied each
    value by. A normalizer that honours them checks each row against
    ``published_unit``, multiplies, and writes the canonical unit. Both are
    ``None`` for a dataset stored as published.
    """

    organization_code: str
    query_code: str | None = None
    organization_series_code: str | None = None
    dimensions: dict[str, str] | None = None
    organization_name: str | None = None
    base_url: str | None = None
    format: str | None = None
    note: str | None = None
    published_unit: str | None = None
    value_multiplier: int | float | None = None


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    """A dataset with a complete definition (``status: documented``)."""

    code: str
    name: str
    dataset_type: str
    source: SourceMetadata
    description: str | None = None
    unit: str | None = None

    @property
    def organization_code(self) -> str:
        return self.source.organization_code


@dataclass(frozen=True, slots=True)
class UnresolvedDataset:
    """A dataset an indicator depends on but for which no definition exists.

    Present so that the dependency is explicit and the catalog still loads,
    without fabricating a name, source, or unit that nobody ever recorded.
    """

    code: str
    note: str


@dataclass(frozen=True, slots=True)
class IndicatorMetadata:
    """One SSPI indicator and the datasets it is computed from.

    ``score_function`` is the methodology's descriptive formula text. It is
    not parsed or executed anywhere in this package.
    """

    code: str
    name: str
    pillar_code: str
    category_code: str
    description: str
    dataset_codes: tuple[str, ...]
    policy: str | None = None
    footnote: str | None = None
    lower_goalpost: float | None = None
    upper_goalpost: float | None = None
    score_function: str | None = None
