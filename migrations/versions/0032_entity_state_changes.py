"""entity state changes.

Revision ID: 0032_entity_state_changes
Revises: 0031_story_state
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_entity_state_changes"
down_revision: str | None = "0031_story_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_state_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("entity_name", sa.String(length=200), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("source_span", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
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
            ["work_id"],
            ["works.id"],
            name="fk_entity_state_changes_work_id_works",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            name="fk_entity_state_changes_entity_id_entities",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["story_events.id"],
            name="fk_entity_state_changes_event_id_story_events",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_entity_state_changes_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_state_changes"),
    )
    op.create_index(
        "ix_entity_state_changes_work_id_entity_id",
        "entity_state_changes",
        ["work_id", "entity_id"],
    )
    op.create_index(
        "ix_entity_state_changes_work_id_chapter_number",
        "entity_state_changes",
        ["work_id", "chapter_number"],
    )
