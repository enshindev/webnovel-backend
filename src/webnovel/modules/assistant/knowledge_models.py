from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class KnowledgeEmbeddingModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_embeddings"
    __table_args__ = (UniqueConstraint("source", "ref", name="uq_knowledge_source_ref"),)

    source: Mapped[str] = mapped_column(String(256))
    ref: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    content_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
