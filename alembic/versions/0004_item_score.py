"""item_score: category, pillar and SSPI scores

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16

One row per (item_code, country_code, year) for the SSPI root, the pillars
and the categories, written by ``sspi.aggregation_runner.run_aggregation``,
which replaces the whole table in one transaction (the legacy finalizer
deleted and refilled ``sspi_item_data``). ``children`` holds the codes
actually averaged and ``indicators`` every indicator underneath; whether a
score rests on imputed data is derived from ``indicator_score`` when read.
Indicator scores are not copied here: they stay in ``indicator_score``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_score",
        sa.Column("item_code", sa.Text(), primary_key=True),
        sa.Column("country_code", sa.Text(), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("children", JSONB(), nullable=False),
        sa.Column("indicators", JSONB(), nullable=False),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("item_code ~ '^[A-Z0-9_]+$'", name="ck_item_score_item_code_format"),
        sa.CheckConstraint("item_type IN ('SSPI', 'Pillar', 'Category')", name="ck_item_score_item_type"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{3}$'", name="ck_item_score_country_code_format"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_item_score_range"),
    )


def downgrade() -> None:
    op.drop_table("item_score")
