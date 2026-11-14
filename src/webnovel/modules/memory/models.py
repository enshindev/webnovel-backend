from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionRunModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "extraction_runs"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    trigger: Mapped[str] = mapped_column(String(32), default="accept")
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExtractionStepModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "extraction_steps"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("extraction_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(nullable=True)
    tokens: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SummaryModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "summaries"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), default="chapter")
    scope_id: Mapped[UUID] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    based_on_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="fresh")
    content_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EntityModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entities"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    first_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )


class EntityRevisionModel(Base):
    __tablename__ = "entity_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column()
    before: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, object]] = mapped_column(JSON)
    source_proposal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChangeProposalModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "change_proposals"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("extraction_runs.id", ondelete="CASCADE"))
    step_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extraction_steps.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    target_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True
    )
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, object]] = mapped_column(JSON)
    diff: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_span: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    base_entity_version: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryEmbeddingModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "memory_embeddings"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[UUID] = mapped_column()
    chunk_no: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    content_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChapterEmbeddingModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "embedding_chunks"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="fresh")
    model: Mapped[str] = mapped_column(String(128))
    chunk_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EntityRelationModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "entity_relations"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    from_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    to_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(64))
    since_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    source_proposal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ForeshadowModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "foreshadows"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text)
    planted_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    expected_recover_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="planted")
    source_proposal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="SET NULL"), nullable=True
    )


class TimelineEventModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "timeline_events"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    event_time: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_proposal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StoryEventModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "story_events"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id", ondelete="CASCADE"))
    chapter_number: Mapped[int] = mapped_column()
    event_index: Mapped[int] = mapped_column()
    summary: Mapped[str] = mapped_column(Text)
    time_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    participants: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    source_span: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="inferred")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KnowledgeStateModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_states"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    character_name: Mapped[str] = mapped_column(String(200))
    fact_key: Mapped[str] = mapped_column(String(300))
    fact_value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32))
    learned_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_events.id", ondelete="SET NULL"), nullable=True
    )
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    chapter_number: Mapped[int] = mapped_column()
    source_span: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="inferred")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
