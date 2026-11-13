"""prompt version and label tables.

Revision ID: 0029_prompt_tables
Revises: 0028_context_snapshot
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_prompt_tables"
down_revision: str | None = "0028_context_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prompt_id", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("defaults", sa.JSON(), nullable=False),
        sa.Column("includes", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_versions"),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_version"),
    )
    op.create_table(
        "prompt_labels",
        sa.Column("prompt_id", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("prompt_id", "label", name="pk_prompt_labels"),
    )


def downgrade() -> None:
    op.drop_table("prompt_labels")
    op.drop_table("prompt_versions")
