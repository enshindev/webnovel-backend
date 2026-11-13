from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChapterModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapters"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    volume_id: Mapped[UUID | None] = mapped_column(nullable=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)


class ChapterVersionModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chapter_versions"

    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    parent_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
