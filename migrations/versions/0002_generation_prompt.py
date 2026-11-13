"""generation prompt metadata

Revision ID: 0002_generation_prompt
Revises: 0001_s1_core
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_generation_prompt"
down_revision: str | None = "0001_s1_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generations", sa.Column("prompt_name", sa.String(length=128), nullable=True))
    op.add_column("generations", sa.Column("prompt_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "prompt_version")
    op.drop_column("generations", "prompt_name")
