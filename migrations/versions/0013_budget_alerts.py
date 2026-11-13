"""budget alert history.

Revision ID: 0013_budget_alerts
Revises: 0012_agent_runs
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_budget_alerts"
down_revision: str | None = "0012_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("limit", sa.Numeric(12, 6), nullable=False),
        sa.Column("spent", sa.Numeric(12, 6), nullable=False),
        sa.Column("ratio", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_budget_alerts"),
        sa.UniqueConstraint("day", "state", name="uq_budget_alerts_day_state"),
    )


def downgrade() -> None:
    op.drop_table("budget_alerts")
