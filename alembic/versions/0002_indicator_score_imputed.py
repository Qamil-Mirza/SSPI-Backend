"""indicator_score.imputed: derived observed/imputed classification

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

The flag is derived data: the repository computes it from the embedded
inputs on every write (legacy ``filter_imputations`` rule: any input with a
truthy ``imputed`` provenance value) and verifies it on every read. The
backfill below applies the same rule to rows written before this revision,
matching JSON ``true`` or ``1``. The column has no default on purpose so
that no write path can omit it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("indicator_score", sa.Column("imputed", sa.Boolean(), nullable=True))
    op.execute("UPDATE indicator_score SET imputed = (inputs @? '$.observations[*].provenance.imputed ? (@ == true || @ == 1)')")
    op.alter_column("indicator_score", "imputed", nullable=False)


def downgrade() -> None:
    op.drop_column("indicator_score", "imputed")
