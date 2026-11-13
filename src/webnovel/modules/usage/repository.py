from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.usage.contract import (
    UsageBucket,
    UsageEntry,
    UsageOverview,
    UsageSummary,
)
from webnovel.modules.usage.models import UsageLedgerModel


class UsageRepository(Protocol):
    async def add(
        self,
        *,
        work_id: UUID | None,
        generation_id: UUID | None,
        provider: str,
        model: str,
        task_type: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
        price_snapshot: dict[str, Any],
        cost: float,
        currency: str,
        estimated: bool,
    ) -> None: ...

    async def list(self, work_id: UUID, limit: int) -> Sequence[UsageEntry]: ...

    async def summary(self, work_id: UUID) -> UsageSummary: ...

    async def daily_cost(self) -> float: ...

    async def breakdown(self, work_id: UUID, group_by: str, days: int) -> Sequence[UsageBucket]: ...

    async def overview(self, days: int) -> UsageOverview: ...


def _to_domain(model: UsageLedgerModel) -> UsageEntry:
    return UsageEntry(
        id=model.id,
        ts=model.ts,
        work_id=model.work_id,
        generation_id=model.generation_id,
        provider=model.provider,
        model=model.model,
        task_type=model.task_type,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        cached_tokens=model.cached_tokens,
        cost=float(model.cost),
        currency=model.currency,
        estimated=model.estimated,
    )


class SqlAlchemyUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        work_id: UUID | None,
        generation_id: UUID | None,
        provider: str,
        model: str,
        task_type: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
        price_snapshot: dict[str, Any],
        cost: float,
        currency: str,
        estimated: bool,
    ) -> None:
        self._session.add(
            UsageLedgerModel(
                work_id=work_id,
                generation_id=generation_id,
                provider=provider,
                model=model,
                task_type=task_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                price_snapshot=price_snapshot,
                cost=cost,
                currency=currency,
                estimated=estimated,
            )
        )
        await self._session.flush()

    async def list(self, work_id: UUID, limit: int) -> Sequence[UsageEntry]:
        stmt = (
            select(UsageLedgerModel)
            .where(UsageLedgerModel.work_id == work_id)
            .order_by(UsageLedgerModel.ts.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(row) for row in rows]

    async def daily_cost(self) -> float:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.coalesce(func.sum(UsageLedgerModel.cost), 0)).where(
            UsageLedgerModel.ts >= start
        )
        return float((await self._session.execute(stmt)).scalar_one())

    async def breakdown(self, work_id: UUID, group_by: str, days: int) -> Sequence[UsageBucket]:
        key: Any
        if group_by == "model":
            key = UsageLedgerModel.model
        elif group_by == "task":
            key = func.coalesce(UsageLedgerModel.task_type, "unknown")
        elif group_by == "day":
            key = func.date_trunc("day", UsageLedgerModel.ts)
        else:
            raise ValueError(f"unsupported group_by: {group_by}")
        start = datetime.now(UTC) - timedelta(days=max(1, days))
        stmt = (
            select(
                key.label("key"),
                func.count(UsageLedgerModel.id),
                func.coalesce(func.sum(UsageLedgerModel.prompt_tokens), 0),
                func.coalesce(func.sum(UsageLedgerModel.completion_tokens), 0),
                func.coalesce(func.sum(UsageLedgerModel.cost), 0),
            )
            .where(UsageLedgerModel.work_id == work_id, UsageLedgerModel.ts >= start)
            .group_by(key)
            .order_by(func.sum(UsageLedgerModel.cost).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            UsageBucket(
                key=str(row[0]),
                calls=int(row[1]),
                prompt_tokens=int(row[2]),
                completion_tokens=int(row[3]),
                cost=float(row[4]),
                currency="CNY",
            )
            for row in rows
        ]

    async def overview(self, days: int) -> UsageOverview:
        summary = await self._summary(None)
        return UsageOverview(
            summary=summary,
            by_model=list(await self._breakdown(None, "model", days)),
            by_task=list(await self._breakdown(None, "task", days)),
            by_day=list(await self._breakdown(None, "day", days)),
        )

    async def _summary(self, work_id: UUID | None) -> UsageSummary:
        stmt = select(
            func.count(UsageLedgerModel.id),
            func.coalesce(func.sum(UsageLedgerModel.prompt_tokens), 0),
            func.coalesce(func.sum(UsageLedgerModel.completion_tokens), 0),
            func.coalesce(func.sum(UsageLedgerModel.cached_tokens), 0),
            func.coalesce(func.sum(UsageLedgerModel.cost), 0),
        )
        if work_id is not None:
            stmt = stmt.where(UsageLedgerModel.work_id == work_id)
        row = (await self._session.execute(stmt)).one()
        return UsageSummary(
            calls=int(row[0]),
            prompt_tokens=int(row[1]),
            completion_tokens=int(row[2]),
            cached_tokens=int(row[3]),
            cost=float(row[4]),
            currency="CNY",
        )

    async def _breakdown(
        self, work_id: UUID | None, group_by: str, days: int
    ) -> Sequence[UsageBucket]:
        key: Any
        if group_by == "model":
            key = UsageLedgerModel.model
        elif group_by == "task":
            key = func.coalesce(UsageLedgerModel.task_type, "unknown")
        elif group_by == "day":
            key = func.date_trunc("day", UsageLedgerModel.ts)
        else:
            raise ValueError(f"unsupported group_by: {group_by}")
        start = datetime.now(UTC) - timedelta(days=max(1, days))
        stmt = select(
            key.label("key"),
            func.count(UsageLedgerModel.id),
            func.coalesce(func.sum(UsageLedgerModel.prompt_tokens), 0),
            func.coalesce(func.sum(UsageLedgerModel.completion_tokens), 0),
            func.coalesce(func.sum(UsageLedgerModel.cost), 0),
        ).where(UsageLedgerModel.ts >= start)
        if work_id is not None:
            stmt = stmt.where(UsageLedgerModel.work_id == work_id)
        stmt = stmt.group_by(key).order_by(func.sum(UsageLedgerModel.cost).desc())
        rows = (await self._session.execute(stmt)).all()
        return [
            UsageBucket(
                key=str(row[0]),
                calls=int(row[1]),
                prompt_tokens=int(row[2]),
                completion_tokens=int(row[3]),
                cost=float(row[4]),
                currency="CNY",
            )
            for row in rows
        ]

    async def summary(self, work_id: UUID) -> UsageSummary:
        return await self._summary(work_id)
