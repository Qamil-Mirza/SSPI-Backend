"""indicator_score.provenance: how the score itself was derived

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01

``inputs`` keeps recording what a score was computed from. ``provenance``
records how the score itself was derived: ``{}`` for a score produced
directly by the formula, and ``imputed``/``imputation_method`` details for a
score imputed at score level (an extrapolation of an earlier year's score,
or a reference-class mean of other countries' scores), which has no imputed
input observation to classify it. Every row written before this revision was
produced directly by a formula, so the default ``{}`` is the truthful value
for all of them; ``imputed`` stays derived (now from provenance or inputs)
and verified on read.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("indicator_score", sa.Column("provenance", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column("indicator_score", "provenance")
