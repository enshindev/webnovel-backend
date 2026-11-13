"""eval runs and case results.

Revision ID: 0021_eval_runs
Revises: 0020_timeline_events
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_eval_runs"
down_revision: str | None = "0020_timeline_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.String(length=128), nullable=False),
        sa.Column("prompt_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("report_path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_eval_runs"),
    )
    op.create_table(
        "eval_case_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["eval_runs.id"],
            name="fk_eval_case_results_run_id_eval_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_eval_case_results"),
        sa.UniqueConstraint("run_id", "case_id", name="uq_eval_case_results_run_case"),
    )


def downgrade() -> None:
    op.drop_table("eval_case_results")
    op.drop_table("eval_runs")
