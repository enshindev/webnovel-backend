from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StyleProfileModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "style_profiles"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    features: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    qualitative: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    do_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    dont_list: Mapped[list[str]] = mapped_column(JSON, default=list)


class StyleSampleModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "style_samples"

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("style_profiles.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    start: Mapped[int] = mapped_column(Integer, default=0)
    end: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="narration")
    character_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StyleCheckModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "style_checks"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("style_profiles.id", ondelete="CASCADE"))
    draft_id: Mapped[UUID | None] = mapped_column(nullable=True)
    score: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    issues: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
