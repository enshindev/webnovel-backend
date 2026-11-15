from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GenerationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generations"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(nullable=True)
    prompt_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    context_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_words: Mapped[int | None] = mapped_column(nullable=True)
    draft_id: Mapped[UUID | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DraftModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "drafts"
    __table_args__ = (
        UniqueConstraint(
            "generation_id", "candidate_index", name="uq_drafts_generation_id_candidate_index"
        ),
    )

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    generation_id: Mapped[UUID] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="generating")
    candidate_index: Mapped[int] = mapped_column(default=0, server_default="0")


class CandidateSetModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "candidate_sets"

    generation_id: Mapped[UUID] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String(32))
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    shown_order: Mapped[list[int]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PreferenceEventModel(Base):
    __tablename__ = "preference_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_sets.id", ondelete="CASCADE")
    )
    candidate_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32))
    edit_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyKeyModel(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32))
    payload_hash: Mapped[str] = mapped_column(String(64))
    generation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
