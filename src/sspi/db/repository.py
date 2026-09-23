"""Repository: the only translation layer between SQL rows and domain objects.

* ``save_*`` is an upsert on the identity key. Rerunning a writer converges.
  For scores the database enforces observed-over-imputed precedence: an
  imputed score never replaces an observed one; everything else replaces.
* ``replace_*`` is explicit, named, destructive: "this series is now exactly
  these rows". It is the equivalent of the legacy delete-then-insert.
* ``delete_*`` removes a whole series.
* ``get_*`` returns fresh domain objects, never ORM instances.

The repository never commits, flushes, or rolls back; the caller owns the
transaction via ``Database.transaction()``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Select, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import InstrumentedAttribute, Session

from sspi.db.models import IndicatorScoreRow, ObservationRow
from sspi.errors import InvalidObservationError, InvalidScoreError, ScoreIntegrityError
from sspi.imputation import is_imputed
from sspi.scoring import ComputedValue, IndicatorScore, Observation

IDENTITY_INVARIANT = (
    "an observation is identified by (dataset_code, country_code, year) only; "
    "additional observation dimensions are not supported, mint a distinct dataset code instead"
)
RESERVED_DIMENSION_KEYS = frozenset({"AdditionalIdentifiers", "additional_identifiers", "Dimensions", "dimensions"})

YearRange = tuple[int, int]


class Repository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # Observations
    # ------------------------------------------------------------------ #

    def save_observations(self, observations: Iterable[Observation]) -> int:
        """Upsert by (dataset_code, country_code, year). Returns rows written."""
        rows = _observation_rows(observations)
        if not rows:
            return 0
        stmt = pg_insert(ObservationRow)
        stmt = stmt.on_conflict_do_update(
            index_elements=["dataset_code", "country_code", "year"],
            set_={
                "value": stmt.excluded.value,
                "unit": stmt.excluded.unit,
                "provenance": stmt.excluded.provenance,
                "written_at": func.now(),
            },
        )
        self._session.execute(stmt, rows)
        return len(rows)

    def replace_dataset(self, dataset_code: str, observations: Iterable[Observation]) -> int:
        """Delete every row of ``dataset_code`` and insert ``observations`` in its place."""
        rows = _observation_rows(observations)
        foreign = sorted({r["dataset_code"] for r in rows} - {dataset_code})
        if foreign:
            raise InvalidObservationError(
                f"replace_dataset({dataset_code!r}) received observations for other datasets: {foreign}"
            )
        self._session.execute(delete(ObservationRow).where(ObservationRow.dataset_code == dataset_code))
        if rows:
            self._session.execute(insert(ObservationRow), rows)
        return len(rows)

    def delete_dataset(self, dataset_code: str) -> int:
        result = self._session.execute(delete(ObservationRow).where(ObservationRow.dataset_code == dataset_code))
        return result.rowcount

    def get_observations(
        self,
        dataset_codes: Iterable[str] | None = None,
        countries: Iterable[str] | None = None,
        years: YearRange | None = None,
    ) -> list[Observation]:
        """Observations matching every given filter, ordered by identity.

        ``None`` means no filter; an empty iterable means no rows; ``years`` is
        an inclusive ``(start, end)``.
        """
        stmt = select(ObservationRow).order_by(ObservationRow.dataset_code, ObservationRow.country_code, ObservationRow.year)
        stmt = _filtered(stmt, [(ObservationRow.dataset_code, dataset_codes), (ObservationRow.country_code, countries)], ObservationRow.year, years)
        if stmt is None:
            return []
        return [_to_observation(row) for row in self._session.scalars(stmt)]

    # ------------------------------------------------------------------ #
    # Indicator scores
    # ------------------------------------------------------------------ #

    def save_scores(self, scores: Iterable[IndicatorScore]) -> int:
        """Upsert by (indicator_code, country_code, year) with precedence
        enforced in SQL: an imputed score does not replace an existing
        observed one (the row is left as it is); observed replaces anything,
        imputed replaces imputed. Returns the rows actually written."""
        rows = _score_rows(scores)
        if not rows:
            return 0
        stmt = pg_insert(IndicatorScoreRow)
        existing_observed_vs_new_imputed = (IndicatorScoreRow.imputed.is_(False)) & (stmt.excluded.imputed.is_(True))
        stmt = stmt.on_conflict_do_update(
            index_elements=["indicator_code", "country_code", "year"],
            set_={
                "score": stmt.excluded.score,
                "unit": stmt.excluded.unit,
                "inputs": stmt.excluded.inputs,
                "imputed": stmt.excluded.imputed,
                "written_at": func.now(),
            },
            where=~existing_observed_vs_new_imputed,
        ).returning(IndicatorScoreRow.country_code)
        return len(self._session.execute(stmt, rows).all())

    def replace_indicator_scores(self, indicator_code: str, scores: Iterable[IndicatorScore]) -> int:
        """Delete every score of ``indicator_code`` and insert ``scores`` in its place."""
        rows = _score_rows(scores)
        foreign = sorted({r["indicator_code"] for r in rows} - {indicator_code})
        if foreign:
            raise InvalidScoreError(
                f"replace_indicator_scores({indicator_code!r}) received scores for other indicators: {foreign}"
            )
        self._session.execute(delete(IndicatorScoreRow).where(IndicatorScoreRow.indicator_code == indicator_code))
        if rows:
            self._session.execute(insert(IndicatorScoreRow), rows)
        return len(rows)

    def delete_indicator_scores(self, indicator_code: str) -> int:
        result = self._session.execute(delete(IndicatorScoreRow).where(IndicatorScoreRow.indicator_code == indicator_code))
        return result.rowcount

    def get_scores(
        self,
        indicator_codes: Iterable[str] | None = None,
        countries: Iterable[str] | None = None,
        years: YearRange | None = None,
        imputed: bool | None = None,
    ) -> list[IndicatorScore]:
        """Scores matching every given filter, ordered by identity.

        ``imputed`` selects observed (``False``) or imputed (``True``) scores;
        ``None`` means both. Every returned score is re-classified from its
        inputs and checked against the stored flag; a mismatch raises
        ``ScoreIntegrityError``.
        """
        stmt = select(IndicatorScoreRow).order_by(IndicatorScoreRow.indicator_code, IndicatorScoreRow.country_code, IndicatorScoreRow.year)
        stmt = _filtered(stmt, [(IndicatorScoreRow.indicator_code, indicator_codes), (IndicatorScoreRow.country_code, countries)], IndicatorScoreRow.year, years)
        if stmt is None:
            return []
        if imputed is not None:
            stmt = stmt.where(IndicatorScoreRow.imputed.is_(bool(imputed)))
        return [_to_score(row) for row in self._session.scalars(stmt)]


# ---------------------------------------------------------------------- #
# Filters
# ---------------------------------------------------------------------- #


def _filtered(
    stmt: Select,
    code_filters: list[tuple[InstrumentedAttribute, Iterable[str] | None]],
    year_column: InstrumentedAttribute,
    years: YearRange | None,
) -> Select | None:
    for column, values in code_filters:
        if values is None:
            continue
        values = list(values)
        if not values:
            return None
        stmt = stmt.where(column.in_(values))
    if years is not None:
        start, end = _year_range(years)
        stmt = stmt.where(year_column.between(start, end))
    return stmt


def _year_range(years: YearRange) -> YearRange:
    try:
        start, end = years
    except (TypeError, ValueError):
        raise ValueError(f"years must be an inclusive (start, end) tuple, got {years!r}") from None
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
        raise ValueError(f"years must be integers, got {years!r}")
    if start > end:
        raise ValueError(f"years start must not exceed end, got {years!r}")
    return start, end


# ---------------------------------------------------------------------- #
# Domain <-> row translation
# ---------------------------------------------------------------------- #


def _json_compatible(value: Any, label: str, error: type[Exception]) -> Any:
    """Return ``value`` as plain JSON-ready data, or raise ``error``."""
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise error(f"{label} is not JSON-compatible: {exc}") from None


def _observation_dict(obs: Observation, label: str, error: type[Exception]) -> dict[str, Any]:
    if not isinstance(obs, Observation):
        raise TypeError(f"{label}: expected Observation, got {type(obs).__name__}")
    reserved = RESERVED_DIMENSION_KEYS & set(obs.provenance)
    if reserved:
        raise InvalidObservationError(f"{label}: provenance key(s) {sorted(reserved)} not allowed: {IDENTITY_INVARIANT}")
    return {
        "dataset_code": obs.dataset_code,
        "country_code": obs.country_code,
        "year": obs.year,
        "value": obs.value,
        "unit": obs.unit,
        "provenance": _json_compatible(dict(obs.provenance), f"{label}: provenance", error),
    }


def _observation_rows(observations: Iterable[Observation]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for index, obs in enumerate(observations):
        row = _observation_dict(obs, f"observation {index}", InvalidObservationError)
        key = (row["dataset_code"], row["country_code"], row["year"])
        if key in seen:
            raise InvalidObservationError(f"duplicate observation identity {key} within one write; {IDENTITY_INVARIANT}")
        seen.add(key)
        rows.append(row)
    return rows


def _to_observation(row: ObservationRow) -> Observation:
    return Observation(row.dataset_code, row.country_code, row.year, row.value, row.unit, row.provenance)


def _validated_score(score: Any, label: str) -> float | None:
    if score is None:
        return None
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise InvalidScoreError(f"{label}: score {score!r} is not numeric (only int, float or None can be stored)")
    if not math.isfinite(score):
        raise InvalidScoreError(f"{label}: score {score!r} must be finite")
    if not 0 <= score <= 1:
        raise InvalidScoreError(f"{label}: score {score!r} must be between 0 and 1")
    return float(score)


def _computed_dict(cv: ComputedValue, label: str) -> dict[str, Any]:
    if not isinstance(cv, ComputedValue):
        raise InvalidScoreError(f"{label}: expected ComputedValue, got {type(cv).__name__}")
    value = cv.value
    if isinstance(value, float) and not math.isfinite(value):
        raise InvalidScoreError(f"{label}: computed value {cv.dataset_code} must be finite, got {value!r}")
    return _json_compatible({"dataset_code": cv.dataset_code, "value": value, "unit": cv.unit}, f"{label}: computed value {cv.dataset_code}", InvalidScoreError)


def _score_rows(scores: Iterable[IndicatorScore]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for index, score in enumerate(scores):
        if not isinstance(score, IndicatorScore):
            raise TypeError(f"score {index}: expected IndicatorScore, got {type(score).__name__}")
        label = f"{score.indicator_code}/{score.country_code}/{score.year}"
        if not isinstance(score.unit, str):
            raise InvalidScoreError(f"{label}: unit must be a string, got {score.unit!r}")
        key = (score.indicator_code, score.country_code, score.year)
        if key in seen:
            raise InvalidScoreError(f"{label}: duplicate score identity within one write")
        seen.add(key)
        rows.append(
            {
                "indicator_code": score.indicator_code,
                "country_code": score.country_code,
                "year": score.year,
                "score": _validated_score(score.score, label),
                "unit": score.unit,
                "inputs": {
                    "observations": [_observation_dict(o, f"{label}: input {i}", InvalidScoreError) for i, o in enumerate(score.inputs)],
                    "computed": [_computed_dict(c, label) for c in score.computed],
                },
                "imputed": is_imputed(score),  # derived, never caller-supplied
            }
        )
    return rows


def _to_score(row: IndicatorScoreRow) -> IndicatorScore:
    inputs = tuple(
        Observation(d["dataset_code"], d["country_code"], d["year"], d["value"], d["unit"], d["provenance"])
        for d in row.inputs["observations"]
    )
    computed = tuple(ComputedValue(c["dataset_code"], c["value"], c["unit"]) for c in row.inputs["computed"])
    score = IndicatorScore(row.indicator_code, row.country_code, row.year, row.score, row.unit, inputs, computed)
    derived = is_imputed(score)
    if derived != row.imputed:
        raise ScoreIntegrityError(
            f"{row.indicator_code}/{row.country_code}/{row.year}: stored imputed={row.imputed} but the embedded inputs "
            f"classify the score as {'imputed' if derived else 'observed'}; the row was not written by this repository or was altered"
        )
    return score
