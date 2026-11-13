from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "exp_assistant"


class ConversationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": SCHEMA}  # noqa: RUF012

    scope: Mapped[str] = mapped_column(String(16))
    work_id: Mapped[UUID | None] = mapped_column(nullable=True)
    mode: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class MessageModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": SCHEMA}  # noqa: RUF012

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    tool_calls: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    usage: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdeaModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ideas"
    __table_args__ = {"schema": SCHEMA}  # noqa: RUF012

    scope: Mapped[str] = mapped_column(String(16))
    work_id: Mapped[UUID | None] = mapped_column(nullable=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id", ondelete="CASCADE")
    )
    message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorldDraftModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "world_drafts"
    __table_args__ = {"schema": SCHEMA}  # noqa: RUF012

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    summary: Mapped[str] = mapped_column(Text, default="")
    nodes: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    edges: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProjectBriefModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_briefs"
    __table_args__ = {"schema": SCHEMA}  # noqa: RUF012

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id", ondelete="CASCADE")
    )
    world_draft_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.world_drafts.id", ondelete="SET NULL"), nullable=True
    )
    title_candidates: Mapped[list[str]] = mapped_column(JSON, default=list)
    premise: Mapped[str] = mapped_column(Text)
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_reader: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    selling_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    core_conflict: Mapped[str] = mapped_column(Text)
    character_core: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    tone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pov: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planned_length: Mapped[str | None] = mapped_column(String(64), nullable=True)
    update_cadence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opening_plan: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    sources: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_work_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
