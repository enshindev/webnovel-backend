"""analysis runs and chapter analysis.

Revision ID: 0018_analysis
Revises: 0017_style_character_voice
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_analysis"
down_revision: str | None = "0017_style_character_voice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_analysis_runs_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_runs"),
    )
    op.create_index(
        "ix_analysis_runs_work_id_created_at", "analysis_runs", ["work_id", "created_at"]
    )

    op.create_table(
        "chapter_analysis",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("beats", sa.JSON(), nullable=False),
        sa.Column("pov", sa.String(length=128), nullable=True),
        sa.Column("time_text", sa.String(length=128), nullable=True),
        sa.Column("characters", sa.JSON(), nullable=False),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("hook_type", sa.String(length=64), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name="fk_chapter_analysis_run_id_analysis_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_chapter_analysis_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["chapter_versions.id"],
            name="fk_chapter_analysis_version_id_chapter_versions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapter_analysis"),
    )
    op.create_index("ix_chapter_analysis_run_id", "chapter_analysis", ["run_id"])


def downgrade() -> None:
    op.drop_table("chapter_analysis")
    op.drop_table("analysis_runs")
