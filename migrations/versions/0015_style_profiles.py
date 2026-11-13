"""style profiles, samples and checks.

Revision ID: 0015_style_profiles
Revises: 0014_outbox_events
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_style_profiles"
down_revision: str | None = "0014_outbox_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "style_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("qualitative", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("do_list", sa.JSON(), nullable=False),
        sa.Column("dont_list", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_style_profiles_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_style_profiles"),
    )
    op.create_index("ix_style_profiles_work_id_version", "style_profiles", ["work_id", "version"])

    op.create_table(
        "style_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["style_profiles.id"],
            name="fk_style_samples_profile_id_style_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_style_samples_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["chapter_versions.id"],
            name="fk_style_samples_version_id_chapter_versions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_style_samples"),
    )
    op.create_index("ix_style_samples_profile_id", "style_samples", ["profile_id"])

    op.create_table(
        "style_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_style_checks_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["style_profiles.id"],
            name="fk_style_checks_profile_id_style_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_style_checks"),
    )
    op.create_index("ix_style_checks_work_id_created_at", "style_checks", ["work_id", "created_at"])


def downgrade() -> None:
    op.drop_table("style_checks")
    op.drop_table("style_samples")
    op.drop_table("style_profiles")
