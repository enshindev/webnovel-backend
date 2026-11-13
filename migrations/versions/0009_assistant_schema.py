"""assistant schema and entity relations.

Revision ID: 0009_assistant_schema
Revises: 0008_usage_ledger
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_assistant_schema"
down_revision: str | None = "0008_usage_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS exp_assistant")

    op.create_table(
        "entity_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("from_entity_id", sa.Uuid(), nullable=False),
        sa.Column("to_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("since_chapter_id", sa.Uuid(), nullable=True),
        sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_entity_relations_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["from_entity_id"],
            ["entities.id"],
            name="fk_entity_relations_from_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_entity_id"],
            ["entities.id"],
            name="fk_entity_relations_to_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["since_chapter_id"],
            ["chapters.id"],
            name="fk_entity_relations_since_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_proposal_id"],
            ["change_proposals.id"],
            name="fk_entity_relations_source_proposal_id_change_proposals",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_relations"),
    )
    op.create_index("ix_entity_relations_from_entity_id", "entity_relations", ["from_entity_id"])
    op.create_index("ix_entity_relations_to_entity_id", "entity_relations", ["to_entity_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        schema="exp_assistant",
    )
    op.create_index(
        "ix_exp_assistant_conversations_scope",
        "conversations",
        ["scope"],
        schema="exp_assistant",
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["exp_assistant.conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        schema="exp_assistant",
    )
    op.create_index(
        "ix_exp_assistant_messages_conversation_id",
        "messages",
        ["conversation_id"],
        schema="exp_assistant",
    )

    op.create_table(
        "ideas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["exp_assistant.conversations.id"],
            name="fk_ideas_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ideas"),
        schema="exp_assistant",
    )

    op.create_table(
        "world_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["exp_assistant.conversations.id"],
            name="fk_world_drafts_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_world_drafts"),
        schema="exp_assistant",
    )
    op.create_index(
        "ix_exp_assistant_world_drafts_conversation_id",
        "world_drafts",
        ["conversation_id"],
        schema="exp_assistant",
    )

    op.create_table(
        "project_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("world_draft_id", sa.Uuid(), nullable=True),
        sa.Column("title_candidates", sa.JSON(), nullable=False),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("genre", sa.String(length=64), nullable=True),
        sa.Column("target_reader", sa.JSON(), nullable=False),
        sa.Column("selling_points", sa.JSON(), nullable=False),
        sa.Column("core_conflict", sa.Text(), nullable=False),
        sa.Column("character_core", sa.JSON(), nullable=False),
        sa.Column("tone", sa.String(length=64), nullable=True),
        sa.Column("pov", sa.String(length=64), nullable=True),
        sa.Column("planned_length", sa.String(length=64), nullable=True),
        sa.Column("update_cadence", sa.String(length=64), nullable=True),
        sa.Column("opening_plan", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_work_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["exp_assistant.conversations.id"],
            name="fk_project_briefs_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["world_draft_id"],
            ["exp_assistant.world_drafts.id"],
            name="fk_project_briefs_world_draft_id_world_drafts",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_briefs"),
        schema="exp_assistant",
    )
    op.create_index(
        "ix_exp_assistant_project_briefs_conversation_id",
        "project_briefs",
        ["conversation_id"],
        schema="exp_assistant",
    )


def downgrade() -> None:
    op.drop_table("project_briefs", schema="exp_assistant")
    op.drop_table("world_drafts", schema="exp_assistant")
    op.drop_table("ideas", schema="exp_assistant")
    op.drop_table("messages", schema="exp_assistant")
    op.drop_table("conversations", schema="exp_assistant")
    op.execute("DROP SCHEMA IF EXISTS exp_assistant")
    op.drop_table("entity_relations")
