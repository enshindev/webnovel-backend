"""S1 core: works, chapters, versions, generations, drafts, preferences.

Revision ID: 0001_s1_core
Revises:
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_s1_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "works",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("genre", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_works"),
    )
    op.create_index("ix_works_created_at", "works", ["created_at"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("volume_id", sa.Uuid(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_chapters_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapters"),
        sa.UniqueConstraint("work_id", "number", name="uq_chapters_work_id_number"),
    )
    op.create_index("ix_chapters_work_id_number", "chapters", ["work_id", "number"])

    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_chapter_versions_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapter_versions"),
    )
    op.create_index(
        "ix_chapter_versions_chapter_id_created_at",
        "chapter_versions",
        ["chapter_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_versions_chapter_id_content_hash",
        "chapter_versions",
        ["chapter_id", "content_hash"],
    )

    op.create_table(
        "generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("target_words", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_generations_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_generations_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generations"),
    )
    op.create_index(
        "ix_generations_chapter_id_created_at", "generations", ["chapter_id", "created_at"]
    )
    op.create_index("ix_generations_status", "generations", ["status"])
    op.create_index(
        "uq_generations_one_active_per_chapter",
        "generations",
        ["chapter_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running','streaming','cancelling')"),
    )

    op.create_table(
        "drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_drafts_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_drafts_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name="fk_drafts_generation_id_generations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_drafts"),
        sa.UniqueConstraint("generation_id", name="uq_drafts_generation_id"),
    )
    op.create_index("ix_drafts_chapter_id_created_at", "drafts", ["chapter_id", "created_at"])

    op.create_table(
        "candidate_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("shown_order", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name="fk_candidate_sets_generation_id_generations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_sets"),
    )
    op.create_index("ix_candidate_sets_generation_id", "candidate_sets", ["generation_id"])

    op.create_table(
        "preference_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_set_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("edit_distance", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["candidate_set_id"],
            ["candidate_sets.id"],
            name="fk_preference_events_candidate_set_id_candidate_sets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_preference_events"),
    )
    op.create_index(
        "ix_preference_events_candidate_set_id_event_type",
        "preference_events",
        ["candidate_set_id", "event_type"],
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name="fk_idempotency_keys_generation_id_generations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name="pk_idempotency_keys"),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("preference_events")
    op.drop_table("candidate_sets")
    op.drop_table("drafts")
    op.drop_table("generations")
    op.drop_table("chapter_versions")
    op.drop_table("chapters")
    op.drop_table("works")
