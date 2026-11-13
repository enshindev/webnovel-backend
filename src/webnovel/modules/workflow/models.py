from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowRunModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    template: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="waiting_confirmation")
    current_stage: Mapped[str] = mapped_column(String(64))
    stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
