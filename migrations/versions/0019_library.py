"""author library collections and documents.

Revision ID: 0019_library
Revises: 0018_analysis
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_library"
down_revision: str | None = "0018_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_library_collections"),
    )
    op.create_table(
        "library_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["library_collections.id"],
            name="fk_library_documents_collection_id_library_collections",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_library_documents"),
    )
    op.create_index("ix_library_documents_collection_id", "library_documents", ["collection_id"])


def downgrade() -> None:
    op.drop_table("library_documents")
    op.drop_table("library_collections")
