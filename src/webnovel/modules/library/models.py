from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class LibraryCollectionModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "library_collections"

    work_id: Mapped[UUID | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LibraryDocumentModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "library_documents"

    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("library_collections.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LibraryChunkModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "library_chunks"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("library_documents.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    chunk_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
