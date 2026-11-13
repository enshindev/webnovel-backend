"""outline drafts from analysis.

Revision ID: 0023_outline_drafts
Revises: 0022_library_chunks
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_outline_drafts"
down_revision: str | None = "0022_library_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outline_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_outline_drafts_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name="fk_outline_drafts_analysis_run_id_analysis_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outline_drafts"),
    )
    op.create_index(
        "ix_outline_drafts_work_id_created_at", "outline_drafts", ["work_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("outline_drafts")
