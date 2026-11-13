"""generation prompt snapshot.

Revision ID: 0027_prompt_snapshot
Revises: 0026_outbox_retry
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_prompt_snapshot"
down_revision: str | None = "0026_outbox_retry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("prompt_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "prompt_snapshot")
