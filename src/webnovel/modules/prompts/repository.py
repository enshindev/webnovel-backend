from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.prompts.models import PromptLabelModel, PromptVersionModel


class PromptCatalogRepository(Protocol):
    async def upsert_version(self, values: dict[str, object]) -> None: ...

    async def upsert_label(self, prompt_id: str, label: str, version: int) -> None: ...

    async def versions(self, prompt_id: str) -> Sequence[PromptVersionModel]: ...


class SqlAlchemyPromptCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_version(self, values: dict[str, object]) -> None:
        prompt_id = str(values["prompt_id"])
        version_value = values["version"]
        if not isinstance(version_value, int):
            raise ValueError("version must be an int")
        version = version_value
        row = (
            await self._session.execute(
                select(PromptVersionModel).where(
                    PromptVersionModel.prompt_id == prompt_id,
                    PromptVersionModel.version == version,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = PromptVersionModel(**values)
            self._session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        await self._session.flush()

    async def upsert_label(self, prompt_id: str, label: str, version: int) -> None:
        row = await self._session.get(PromptLabelModel, (prompt_id, label))
        if row is None:
            self._session.add(PromptLabelModel(prompt_id=prompt_id, label=label, version=version))
        else:
            row.version = version
        await self._session.flush()

    async def versions(self, prompt_id: str) -> Sequence[PromptVersionModel]:
        return (
            (
                await self._session.execute(
                    select(PromptVersionModel)
                    .where(PromptVersionModel.prompt_id == prompt_id)
                    .order_by(PromptVersionModel.version.asc())
                )
            )
            .scalars()
            .all()
        )
