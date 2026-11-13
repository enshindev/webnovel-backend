"""generation context snapshot.

Revision ID: 0028_context_snapshot
Revises: 0027_prompt_snapshot
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_context_snapshot"
down_revision: str | None = "0027_prompt_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("context_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "context_snapshot")
