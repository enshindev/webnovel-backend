from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base


class UsageLedgerModel(Base):
    __tablename__ = "usage_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    work_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("works.id", ondelete="SET NULL"), nullable=True
    )
    generation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    task_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    price_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
