from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.usage.alert_models import BudgetAlertModel
from webnovel.modules.usage.budget import BudgetStatus


@dataclass(frozen=True, slots=True)
class BudgetAlertRecord:
    id: int
    day: str
    limit: float
    spent: float
    ratio: float
    state: str


class BudgetAlertRepository(Protocol):
    async def record(self, status: BudgetStatus) -> None: ...

    async def list(self, limit: int) -> list[BudgetAlertRecord]: ...


class SqlAlchemyBudgetAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, status: BudgetStatus) -> None:
        if status.limit is None or status.state == "disabled":
            return
        day = datetime.now(UTC).date().isoformat()
        row = (
            await self._session.execute(
                select(BudgetAlertModel).where(
                    BudgetAlertModel.day == day,
                    BudgetAlertModel.state == status.state,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            self._session.add(
                BudgetAlertModel(
                    day=day,
                    limit=Decimal(str(status.limit)),
                    spent=Decimal(str(status.spent)),
                    ratio=status.ratio,
                    state=status.state,
                )
            )
        else:
            row.limit = Decimal(str(status.limit))
            row.spent = Decimal(str(status.spent))
            row.ratio = status.ratio
        await self._session.flush()

    async def list(self, limit: int) -> list[BudgetAlertRecord]:
        rows = (
            (
                await self._session.execute(
                    select(BudgetAlertModel).order_by(BudgetAlertModel.id.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [
            BudgetAlertRecord(
                id=row.id,
                day=row.day,
                limit=float(row.limit),
                spent=float(row.spent),
                ratio=row.ratio,
                state=row.state,
            )
            for row in rows
        ]
