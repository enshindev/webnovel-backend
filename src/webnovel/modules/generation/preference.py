from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.generation.models import (
    CandidateSetModel,
    DraftModel,
    GenerationModel,
    PreferenceEventModel,
)
from webnovel.modules.generation.service import _normalized_edit_distance

logger = logging.getLogger(__name__)


class SqlAlchemyPreferenceRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def edited_after_accept(self, chapter_id: UUID, content: str) -> None:
        draft = (
            await self._session.scalars(
                select(DraftModel)
                .join(GenerationModel, GenerationModel.id == DraftModel.generation_id)
                .where(
                    DraftModel.chapter_id == chapter_id,
                    DraftModel.status == "accepted",
                    GenerationModel.accepted_at.is_not(None),
                )
                .order_by(GenerationModel.accepted_at.desc())
                .limit(1)
            )
        ).first()
        if draft is None or draft.content == content:
            return
        distance = _normalized_edit_distance(draft.content[:4_000], content[:4_000])
        existing = await self._session.scalar(
            select(PreferenceEventModel.id)
            .where(
                PreferenceEventModel.candidate_id == str(draft.id),
                PreferenceEventModel.event_type == "edited_after_accept",
                PreferenceEventModel.edit_distance == distance,
            )
            .limit(1)
        )
        if existing is not None:
            return
        candidate_set = (
            await self._session.scalars(
                select(CandidateSetModel).where(
                    CandidateSetModel.generation_id == draft.generation_id
                )
            )
        ).first()
        if candidate_set is None:
            return
        self._session.add(
            PreferenceEventModel(
                candidate_set_id=candidate_set.id,
                candidate_id=str(draft.id),
                event_type="edited_after_accept",
                edit_distance=distance,
                event_metadata={"chapter_id": str(chapter_id)},
            )
        )
        await self._session.flush()

    async def saved_idea(self, idea_id: UUID, scope: str) -> None:
        self._session.add(
            PreferenceEventModel(
                candidate_set_id=None,
                candidate_id=str(idea_id),
                event_type="saved_idea",
                event_metadata={"scope": scope},
            )
        )
        await self._session.flush()
