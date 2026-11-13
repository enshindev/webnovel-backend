"""agent runs and approvals.

Revision ID: 0012_agent_runs
Revises: 0011_audit_log
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_agent_runs"
down_revision: str | None = "0011_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("experiment", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Numeric(12, 6), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_agent_runs_work_id_works", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
        sa.UniqueConstraint("thread_id", name="uq_agent_runs_thread_id"),
    )
    op.create_index("ix_agent_runs_work_id_created_at", "agent_runs", ["work_id", "created_at"])

    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_agent_approvals_run_id_agent_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_approvals"),
    )
    op.create_index("ix_agent_approvals_run_id_status", "agent_approvals", ["run_id", "status"])


def downgrade() -> None:
    op.drop_table("agent_approvals")
    op.drop_table("agent_runs")
