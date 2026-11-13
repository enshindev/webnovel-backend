"""timeline events.

Revision ID: 0020_timeline_events
Revises: 0019_library
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_timeline_events"
down_revision: str | None = "0019_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        sa.Column("event_time", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("entity_ids", sa.JSON(), nullable=False),
        sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_timeline_events_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_timeline_events_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_timeline_events"),
    )
    op.create_index(
        "ix_timeline_events_work_id_created_at", "timeline_events", ["work_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("timeline_events")
