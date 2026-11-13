from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.export.contract import ExportJob, ExportStatus
from webnovel.modules.export.models import ExportJobModel


class ExportRepository(Protocol):
    async def create(self, work_id: UUID, fmt: str) -> ExportJob: ...

    async def get(self, job_id: UUID) -> ExportJob | None: ...

    async def finish(
        self, job_id: UUID, status: ExportStatus, file_path: str | None = None
    ) -> None: ...

    async def expire(self) -> list[str]: ...


def _to_domain(model: ExportJobModel) -> ExportJob:
    return ExportJob(
        id=model.id,
        work_id=model.work_id,
        format=model.format,
        status=ExportStatus(model.status),
        file_path=model.file_path,
        created_at=model.created_at,
        download_token=model.download_token,
        expires_at=model.expires_at,
    )


class SqlAlchemyExportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, work_id: UUID, fmt: str) -> ExportJob:
        model = ExportJobModel(
            work_id=work_id,
            format=fmt,
            status=ExportStatus.QUEUED.value,
            download_token=secrets.token_urlsafe(32),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get(self, job_id: UUID) -> ExportJob | None:
        model = await self._session.get(ExportJobModel, job_id)
        return _to_domain(model) if model is not None else None

    async def finish(
        self, job_id: UUID, status: ExportStatus, file_path: str | None = None
    ) -> None:
        model = await self._session.get(ExportJobModel, job_id)
        if model is None:
            return
        model.status = status.value
        model.file_path = file_path
        model.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def expire(self) -> list[str]:
        from sqlalchemy import select

        now = datetime.now(UTC)
        stmt = select(ExportJobModel).where(
            ExportJobModel.status != ExportStatus.EXPIRED.value,
            ExportJobModel.expires_at.is_not(None),
            ExportJobModel.expires_at < now,
        )
        paths: list[str] = []
        for model in (await self._session.execute(stmt)).scalars().all():
            if model.file_path:
                paths.append(model.file_path)
            model.status = ExportStatus.EXPIRED.value
        await self._session.flush()
        return paths
