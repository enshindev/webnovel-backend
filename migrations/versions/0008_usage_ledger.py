"""usage ledger.

Revision ID: 0008_usage_ledger
Revises: 0007_export_jobs
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_usage_ledger"
down_revision: str | None = "0007_export_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("price_snapshot", sa.JSON(), nullable=False),
        sa.Column("cost", sa.Numeric(12, 6), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_usage_ledger_work_id_works", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name="fk_usage_ledger_generation_id_generations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_ledger"),
    )
    op.create_index("ix_usage_ledger_ts", "usage_ledger", ["ts"])
    op.create_index("ix_usage_ledger_generation_id", "usage_ledger", ["generation_id"])
    op.create_index("ix_usage_ledger_work_id_ts", "usage_ledger", ["work_id", "ts"])


def downgrade() -> None:
    op.drop_table("usage_ledger")
