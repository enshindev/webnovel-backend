from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class QualityCheckModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quality_checks"

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True
    )
    version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="succeeded")
    rule_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage: Mapped[str] = mapped_column(String(16), default="chapter")
    channel: Mapped[str] = mapped_column(String(16), default="male")
    summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QualityIssueModel(Base):
    __tablename__ = "quality_issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[UUID] = mapped_column(ForeignKey("quality_checks.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(String(2))
    type: Mapped[str] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvalRunModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "eval_runs"

    task: Mapped[str] = mapped_column(String(128))
    prompt_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    params: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvalCaseResultModel(Base):
    __tablename__ = "eval_case_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"))
    case_id: Mapped[str] = mapped_column(String(128))
    passed: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
