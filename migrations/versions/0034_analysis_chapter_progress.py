"""analysis chapter progress and boundary confidence.

Revision ID: 0034_analysis_chapter_progress
Revises: 0033_preference_saved_idea
Create Date: 2026-11-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_analysis_chapter_progress"
down_revision: str | None = "0033_preference_saved_idea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chapter_analysis",
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False),
    )
    op.add_column(
        "chapter_analysis",
        sa.Column("progress", sa.Integer(), server_default="100", nullable=False),
    )
    op.add_column(
        "chapter_analysis",
        sa.Column("boundary_confidence", sa.Float(), nullable=True),
    )
