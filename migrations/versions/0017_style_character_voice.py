"""style character samples.

Revision ID: 0017_style_character_voice
Revises: 0016_knowledge_embeddings
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_style_character_voice"
down_revision: str | None = "0016_knowledge_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "style_samples",
        sa.Column("character_name", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("style_samples", "character_name")
