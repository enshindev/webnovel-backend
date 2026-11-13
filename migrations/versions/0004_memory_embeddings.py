"""memory embeddings: pgvector chunks and HNSW index.

Revision ID: 0004_memory_embeddings
Revises: 0003_memory_extraction
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0004_memory_embeddings"
down_revision: str | None = "0003_memory_extraction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_no", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_memory_embeddings_work_id_works", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_memory_embeddings"),
        sa.UniqueConstraint(
            "work_id",
            "source_type",
            "source_id",
            "chunk_no",
            name="uq_memory_embeddings_source_chunk",
        ),
    )
    op.create_index("ix_memory_embeddings_work_id", "memory_embeddings", ["work_id"])
    op.create_index(
        "ix_memory_embeddings_embedding_hnsw",
        "memory_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("memory_embeddings")
