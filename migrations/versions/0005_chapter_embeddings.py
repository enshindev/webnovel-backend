"""chapter chunk embeddings.

Revision ID: 0005_chapter_embeddings
Revises: 0004_memory_embeddings
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0005_chapter_embeddings"
down_revision: str | None = "0004_memory_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name="fk_embedding_chunks_work_id_works", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_embedding_chunks_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["chapter_versions.id"],
            name="fk_embedding_chunks_version_id_chapter_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_embedding_chunks"),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_embedding_chunks_version_chunk"),
    )
    op.create_index("ix_embedding_chunks_work_id", "embedding_chunks", ["work_id"])
    op.create_index("ix_embedding_chunks_chapter_id", "embedding_chunks", ["chapter_id"])
    op.create_index(
        "ix_embedding_chunks_embedding_hnsw",
        "embedding_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("embedding_chunks")
