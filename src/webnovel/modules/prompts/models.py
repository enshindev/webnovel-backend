from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class PromptVersionModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_version"),
    )

    prompt_id: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)
    variables: Mapped[list[str]] = mapped_column(JSON, default=list)
    defaults: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    includes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PromptLabelModel(Base):
    __tablename__ = "prompt_labels"

    prompt_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
