"""The result type every source normalizer returns."""

from __future__ import annotations

from typing import NamedTuple

from sspi.scoring import Observation


class NormalizationResult(NamedTuple):
    observations: list[Observation]
    skipped_areas: tuple[tuple[str, str], ...]  # (source area code, source area name) with no ISO3 mapping
    missing_values: int  # empty source values dropped, mapped areas only
