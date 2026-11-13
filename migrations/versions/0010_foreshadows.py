"""foreshadows.

Revision ID: 0010_foreshadows
Revises: 0009_assistant_schema
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_foreshadows"
down_revision: str | None = "0009_assistant_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foreshadows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("planted_chapter_id", sa.Uuid(), nullable=True),
        sa.Column("expected_recover_chapter_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
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
            ["work_id"], ["works.id"], name="fk_foreshadows_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["planted_chapter_id"],
            ["chapters.id"],
            name="fk_foreshadows_planted_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["expected_recover_chapter_id"],
            ["chapters.id"],
            name="fk_foreshadows_expected_recover_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_proposal_id"],
            ["change_proposals.id"],
            name="fk_foreshadows_source_proposal_id_change_proposals",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_foreshadows"),
    )
    op.create_index("ix_foreshadows_work_id_status", "foreshadows", ["work_id", "status"])


def downgrade() -> None:
    op.drop_table("foreshadows")
