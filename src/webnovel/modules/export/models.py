from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class ExportJobModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "export_jobs"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    format: Mapped[str] = mapped_column(String(16))
    chapter_range: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    download_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
