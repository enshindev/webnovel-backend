"""outbox retry and dead-letter fields.

Revision ID: 0026_outbox_retry
Revises: 0025_workflow_runs
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_outbox_retry"
down_revision: str | None = "0025_workflow_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "outbox_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "next_attempt_at")
    op.drop_column("outbox_events", "last_error")
