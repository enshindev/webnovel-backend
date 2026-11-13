from __future__ import annotations

from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.style.contract import StyleCheck, StyleProfile
from webnovel.modules.style.models import StyleCheckModel, StyleProfileModel, StyleSampleModel


class StyleRepository(Protocol):
    async def create_profile(
        self,
        work_id: UUID,
        features: dict[str, Any],
        summary: str,
        samples: list[dict[str, Any]],
        qualitative: dict[str, Any] | None = None,
    ) -> StyleProfile: ...

    async def get_profile(self, profile_id: UUID) -> StyleProfile | None: ...

    async def get_active(self, work_id: UUID) -> StyleProfile | None: ...

    async def update_profile(self, profile_id: UUID, **values: Any) -> StyleProfile | None: ...

    async def add_sample(self, profile_id: UUID, character_name: str, text: str) -> None: ...

    async def get_character_text(self, profile_id: UUID, character_name: str) -> str | None: ...

    async def add_check(
        self,
        work_id: UUID,
        profile_id: UUID,
        score: float,
        dimensions: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> StyleCheck: ...


def _profile(model: StyleProfileModel) -> StyleProfile:
    return StyleProfile(
        id=model.id,
        work_id=model.work_id,
        version=model.version,
        status=model.status,
        features=cast(dict[str, Any], model.features),
        qualitative=cast(dict[str, Any], model.qualitative),
        summary=model.summary,
        do_list=model.do_list,
        dont_list=model.dont_list,
        created_at=model.created_at,
    )


class SqlAlchemyStyleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_profile(
        self,
        work_id: UUID,
        features: dict[str, Any],
        summary: str,
        samples: list[dict[str, Any]],
        qualitative: dict[str, Any] | None = None,
    ) -> StyleProfile:
        latest = (
            await self._session.execute(
                select(StyleProfileModel)
                .where(StyleProfileModel.work_id == work_id)
                .order_by(StyleProfileModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        model = StyleProfileModel(
            work_id=work_id,
            version=(latest.version + 1) if latest else 1,
            status="active",
            features=features,
            qualitative=qualitative or {},
            summary=summary,
            do_list=[],
            dont_list=[],
        )
        self._session.add(model)
        await self._session.flush()
        for sample in samples:
            self._session.add(
                StyleSampleModel(
                    profile_id=model.id,
                    chapter_id=sample.get("chapter_id"),
                    version_id=sample.get("version_id"),
                    start=0,
                    end=len(str(sample.get("text", ""))),
                    text=str(sample.get("text", "")),
                )
            )
        await self._session.flush()
        await self._session.refresh(model)
        return _profile(model)

    async def get_profile(self, profile_id: UUID) -> StyleProfile | None:
        model = await self._session.get(StyleProfileModel, profile_id)
        return _profile(model) if model is not None else None

    async def get_active(self, work_id: UUID) -> StyleProfile | None:
        row = (
            await self._session.execute(
                select(StyleProfileModel)
                .where(
                    StyleProfileModel.work_id == work_id,
                    StyleProfileModel.status == "active",
                )
                .order_by(StyleProfileModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _profile(row) if row is not None else None

    async def update_profile(self, profile_id: UUID, **values: Any) -> StyleProfile | None:
        model = await self._session.get(StyleProfileModel, profile_id)
        if model is None:
            return None
        for key, value in values.items():
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return _profile(model)

    async def add_sample(self, profile_id: UUID, character_name: str, text: str) -> None:
        self._session.add(
            StyleSampleModel(
                profile_id=profile_id,
                character_name=character_name,
                kind=f"character:{character_name}",
                start=0,
                end=len(text),
                text=text,
            )
        )
        await self._session.flush()

    async def get_character_text(self, profile_id: UUID, character_name: str) -> str | None:
        row = (
            await self._session.execute(
                select(StyleSampleModel)
                .where(
                    StyleSampleModel.profile_id == profile_id,
                    StyleSampleModel.character_name == character_name,
                )
                .order_by(StyleSampleModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return row.text if row is not None else None

    async def add_check(
        self,
        work_id: UUID,
        profile_id: UUID,
        score: float,
        dimensions: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> StyleCheck:
        model = StyleCheckModel(
            work_id=work_id,
            profile_id=profile_id,
            score=score,
            dimensions=dimensions,
            issues=issues,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return StyleCheck(
            id=model.id,
            work_id=model.work_id,
            profile_id=model.profile_id,
            score=model.score,
            dimensions=cast(dict[str, Any], model.dimensions),
            issues=cast(list[dict[str, Any]], model.issues),
            created_at=model.created_at,
        )
