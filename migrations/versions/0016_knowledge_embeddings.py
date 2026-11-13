"""knowledge embeddings.

Revision ID: 0016_knowledge_embeddings
Revises: 0015_style_profiles
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0016_knowledge_embeddings"
down_revision: str | None = "0015_style_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("ref", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_embeddings"),
        sa.UniqueConstraint("source", "ref", name="uq_knowledge_source_ref"),
    )
    op.create_index(
        "ix_knowledge_embeddings_embedding_hnsw",
        "knowledge_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("knowledge_embeddings")
