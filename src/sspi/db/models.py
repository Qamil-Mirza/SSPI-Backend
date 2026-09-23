"""SQLAlchemy persistence models. These are rows, not domain objects.

The scoring dataclasses (``Observation``, ``IndicatorScore``) stay independent
of SQLAlchemy; ``sspi.db.repository`` translates between the two.

Canonical-data invariant: an observation is identified by
``(dataset_code, country_code, year)`` and nothing else. There is no extra
dimension column and none may be added by ingestion; a disaggregated source
gets one dataset code per slice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Double, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sspi.db.base import Base


class ObservationRow(Base):
    __tablename__ = "observation"
    __table_args__ = (
        CheckConstraint("dataset_code ~ '^[A-Z0-9_]+$'", name="ck_observation_dataset_code_format"),
        CheckConstraint("country_code ~ '^[A-Z]{3}$'", name="ck_observation_country_code_format"),
        # PostgreSQL treats NaN as equal to itself, so `value = value` would not catch it.
        CheckConstraint("value <> 'NaN'::double precision AND abs(value) <> 'Infinity'::double precision", name="ck_observation_value_finite"),
    )

    dataset_code: Mapped[str] = mapped_column(Text, primary_key=True)
    country_code: Mapped[str] = mapped_column(Text, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[float] = mapped_column(Double, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class IndicatorScoreRow(Base):
    __tablename__ = "indicator_score"
    __table_args__ = (
        CheckConstraint("indicator_code ~ '^[A-Z0-9_]+$'", name="ck_indicator_score_indicator_code_format"),
        CheckConstraint("country_code ~ '^[A-Z]{3}$'", name="ck_indicator_score_country_code_format"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="ck_indicator_score_range"),
    )

    indicator_code: Mapped[str] = mapped_column(Text, primary_key=True)
    country_code: Mapped[str] = mapped_column(Text, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[float | None] = mapped_column(Double, nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Derived from ``inputs`` by the repository on write and verified on read;
    # never supplied by a caller. Observed rows take precedence over imputed
    # ones in ``save_scores``. No default: every write path must derive it.
    imputed: Mapped[bool] = mapped_column(Boolean, nullable=False)
