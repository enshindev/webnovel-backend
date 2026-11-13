"""export jobs.

Revision ID: 0007_export_jobs
Revises: 0006_quality_checks
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_export_jobs"
down_revision: str | None = "0006_quality_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("chapter_range", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("download_token", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_export_jobs_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_export_jobs"),
    )
    op.create_index("ix_export_jobs_work_id_created_at", "export_jobs", ["work_id", "created_at"])


def downgrade() -> None:
    op.drop_table("export_jobs")
