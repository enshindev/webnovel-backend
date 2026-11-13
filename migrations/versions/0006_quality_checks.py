"""quality checks and issues.

Revision ID: 0006_quality_checks
Revises: 0005_chapter_embeddings
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_quality_checks"
down_revision: str | None = "0005_chapter_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=True),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_quality_checks_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_quality_checks_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["chapter_versions.id"],
            name="fk_quality_checks_version_id_chapter_versions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quality_checks"),
    )
    op.create_index(
        "ix_quality_checks_work_id_created_at", "quality_checks", ["work_id", "created_at"]
    )

    op.create_table(
        "quality_issues",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("check_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(length=2), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["check_id"],
            ["quality_checks.id"],
            name="fk_quality_issues_check_id_quality_checks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quality_issues"),
    )
    op.create_index(
        "ix_quality_issues_check_id_severity", "quality_issues", ["check_id", "severity"]
    )


def downgrade() -> None:
    op.drop_table("quality_issues")
    op.drop_table("quality_checks")
