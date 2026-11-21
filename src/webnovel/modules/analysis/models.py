from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class AnalysisRunModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analysis_runs"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    source_document_id: Mapped[UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="reverse_outline")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChapterAnalysisModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chapter_analysis"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    beats: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    pov: Mapped[str | None] = mapped_column(String(128), nullable=True)
    time_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    characters: Mapped[list[str]] = mapped_column(JSON, default=list)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="ready")
    progress: Mapped[int] = mapped_column(default=100)
    boundary_confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutlineDraftModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outline_drafts"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    analysis_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="draft")
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
