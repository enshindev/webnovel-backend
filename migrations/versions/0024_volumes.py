"""volumes and chapter volume assignment.

Revision ID: 0024_volumes
Revises: 0023_outline_drafts
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_volumes"
down_revision: str | None = "0023_outline_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "volumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_volumes_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_volumes"),
        sa.UniqueConstraint("work_id", "number", name="uq_volumes_work_number"),
    )
    op.create_index("ix_volumes_work_id_number", "volumes", ["work_id", "number"])
    op.create_foreign_key(
        "fk_chapters_volume_id_volumes",
        "chapters",
        "volumes",
        ["volume_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chapters_volume_id_volumes", "chapters", type_="foreignkey")
    op.drop_index("ix_volumes_work_id_number", table_name="volumes")
    op.drop_table("volumes")
