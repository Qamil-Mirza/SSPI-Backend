"""observation and indicator_score tables

Revision ID: 0001
Revises: None
Create Date: 2026-09-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observation",
        sa.Column("dataset_code", sa.Text(), nullable=False),
        sa.Column("country_code", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("dataset_code", "country_code", "year"),
        sa.CheckConstraint("dataset_code ~ '^[A-Z0-9_]+$'", name="ck_observation_dataset_code_format"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{3}$'", name="ck_observation_country_code_format"),
        sa.CheckConstraint("value <> 'NaN'::double precision AND abs(value) <> 'Infinity'::double precision", name="ck_observation_value_finite"),
    )
    op.create_table(
        "indicator_score",
        sa.Column("indicator_code", sa.Text(), nullable=False),
        sa.Column("country_code", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("score", sa.Double(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("indicator_code", "country_code", "year"),
        sa.CheckConstraint("indicator_code ~ '^[A-Z0-9_]+$'", name="ck_indicator_score_indicator_code_format"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{3}$'", name="ck_indicator_score_country_code_format"),
        sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="ck_indicator_score_range"),
    )


def downgrade() -> None:
    op.drop_table("indicator_score")
    op.drop_table("observation")
