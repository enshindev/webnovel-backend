from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base


class BudgetAlertModel(Base):
    __tablename__ = "budget_alerts"
    __table_args__ = (UniqueConstraint("day", "state", name="uq_budget_alerts_day_state"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10))
    limit: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    spent: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    ratio: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
