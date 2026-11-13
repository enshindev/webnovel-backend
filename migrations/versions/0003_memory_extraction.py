"""memory extraction: runs, steps, summaries, entities, proposals.

Revision ID: 0003_memory_extraction
Revises: 0002_generation_prompt
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_memory_extraction"
down_revision: str | None = "0002_generation_prompt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_extraction_runs_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_extraction_runs_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["chapter_versions.id"],
            name="fk_extraction_runs_version_id_chapter_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extraction_runs"),
    )
    op.create_index("ix_extraction_runs_chapter_id", "extraction_runs", ["chapter_id"])
    op.create_index("ix_extraction_runs_status", "extraction_runs", ["status"])

    op.create_table(
        "extraction_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["extraction_runs.id"],
            name="fk_extraction_steps_run_id_extraction_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extraction_steps"),
    )
    op.create_index("ix_extraction_steps_run_id", "extraction_steps", ["run_id"])

    op.create_table(
        "summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("based_on_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_summaries_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["based_on_version_id"],
            ["chapter_versions.id"],
            name="fk_summaries_based_on_version_id_chapter_versions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_summaries"),
        sa.UniqueConstraint("level", "scope_id", name="uq_summaries_level_scope_id"),
    )
    op.create_index("ix_summaries_work_id", "summaries", ["work_id"])

    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("first_chapter_id", sa.Uuid(), nullable=True),
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
            ["work_id"], ["works.id"], name="fk_entities_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["first_chapter_id"],
            ["chapters.id"],
            name="fk_entities_first_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
    )
    op.create_index("ix_entities_work_id_type_name", "entities", ["work_id", "type", "name"])

    op.create_table(
        "change_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("field", sa.String(length=64), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_span", sa.JSON(), nullable=True),
        sa.Column("base_entity_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_change_proposals_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["extraction_runs.id"],
            name="fk_change_proposals_run_id_extraction_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["extraction_steps.id"],
            name="fk_change_proposals_step_id_extraction_steps",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["entities.id"],
            name="fk_change_proposals_target_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_change_proposals"),
    )
    op.create_index("ix_change_proposals_work_id_status", "change_proposals", ["work_id", "status"])
    op.create_index("ix_change_proposals_run_id", "change_proposals", ["run_id"])

    op.create_table(
        "entity_revisions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("source_proposal_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            name="fk_entity_revisions_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_proposal_id"],
            ["change_proposals.id"],
            name="fk_entity_revisions_source_proposal_id_change_proposals",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_revisions"),
    )
    op.create_index(
        "ix_entity_revisions_entity_id_revision", "entity_revisions", ["entity_id", "revision"]
    )


def downgrade() -> None:
    op.drop_table("entity_revisions")
    op.drop_table("change_proposals")
    op.drop_table("entities")
    op.drop_table("summaries")
    op.drop_table("extraction_steps")
    op.drop_table("extraction_runs")
