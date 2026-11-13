from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import BudgetGuardDep, GenerationServiceDep, RedisDep
from webnovel.modules.generation.contract import TERMINAL, GenerationCreate, TaskType

router = APIRouter(tags=["generation"])


class GenerationCreateBody(BaseModel):
    chapter_id: UUID
    task_type: TaskType
    instruction: str | None = Field(default=None, max_length=4000)
    target_words: int | None = Field(default=None, ge=100, le=20_000)


class GenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    chapter_id: UUID
    task_type: str
    status: str
    draft_id: UUID | None
    prompt_name: str | None
    prompt_version: int | None
    prompt_snapshot: dict[str, Any] | None = None
    created_at: datetime


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    generation_id: UUID
    chapter_id: UUID
    content: str
    status: str


class AcceptDraftBody(BaseModel):
    base_version: int = Field(ge=0)


class ChapterVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    parent_version_id: UUID | None
    content: str
    content_hash: str
    source: str
    created_at: datetime


class AcceptedDraftOut(BaseModel):
    draft: DraftOut
    chapter_version: ChapterVersionOut


@router.post(
    "/works/{work_id}/generations",
    response_model=GenerationOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation(
    work_id: UUID,
    body: GenerationCreateBody,
    service: GenerationServiceDep,
    guard: BudgetGuardDep,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> GenerationOut:
    await guard.check()
    generation = await service.create(
        command=GenerationCreate(
            work_id=work_id,
            chapter_id=body.chapter_id,
            task_type=body.task_type,
            instruction=body.instruction,
            target_words=body.target_words,
        ),
        idempotency_key=idempotency_key,
    )
    return GenerationOut.model_validate(generation)


@router.get("/generations/{generation_id}", response_model=GenerationOut)
async def get_generation(generation_id: UUID, service: GenerationServiceDep) -> GenerationOut:
    return GenerationOut.model_validate(await service.get(generation_id))


@router.get("/generations/{generation_id}/prompt")
async def get_generation_prompt(
    generation_id: UUID, service: GenerationServiceDep
) -> dict[str, Any]:
    generation = await service.get(generation_id)
    return {
        "generation_id": str(generation.id),
        "prompt_name": generation.prompt_name,
        "prompt_version": generation.prompt_version,
        "snapshot": generation.prompt_snapshot,
        "context_snapshot": generation.context_snapshot,
    }


@router.post(
    "/generations/{generation_id}/retry",
    response_model=GenerationOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_generation(generation_id: UUID, service: GenerationServiceDep) -> GenerationOut:
    return GenerationOut.model_validate(await service.retry(generation_id))


@router.post("/generations/{generation_id}/cancel", response_model=GenerationOut)
async def cancel_generation(generation_id: UUID, service: GenerationServiceDep) -> GenerationOut:
    return GenerationOut.model_validate(await service.cancel(generation_id))


@router.get("/drafts/{draft_id}", response_model=DraftOut)
async def get_draft(draft_id: UUID, service: GenerationServiceDep) -> DraftOut:
    draft = await service.get_draft(draft_id)
    return DraftOut.model_validate(draft)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(draft_id: UUID, service: GenerationServiceDep) -> None:
    await service.discard_draft(draft_id)


@router.post("/drafts/{draft_id}/accept", response_model=AcceptedDraftOut)
async def accept_draft(
    draft_id: UUID, body: AcceptDraftBody, service: GenerationServiceDep
) -> AcceptedDraftOut:
    accepted = await service.accept_draft(draft_id=draft_id, base_version=body.base_version)
    return AcceptedDraftOut(
        draft=DraftOut.model_validate(accepted.draft),
        chapter_version=ChapterVersionOut.model_validate(accepted.chapter_version),
    )


@router.get("/generations/{generation_id}/stream")
async def stream_generation(
    generation_id: UUID,
    redis: RedisDep,
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    from webnovel.infra.streams import RedisStreamBuffer

    buffer = RedisStreamBuffer(redis)

    async def events() -> AsyncIterator[str]:
        from webnovel.infra.db.session import session_factory
        from webnovel.modules.generation.repository import SqlAlchemyGenerationRepository

        seq = max(last_event_id or 0, 0)
        while True:
            chunks = await buffer.read_after(str(generation_id), seq)
            for chunk_seq, text in chunks:
                seq = chunk_seq
                payload = json.dumps(
                    {"type": "delta", "seq": chunk_seq, "text": text},
                    ensure_ascii=False,
                )
                yield f"id: {chunk_seq}\nevent: delta\ndata: {payload}\n\n"

            async with session_factory() as session:
                repository = SqlAlchemyGenerationRepository(session)
                generation = await repository.get(generation_id)
            if generation is None:
                yield 'event: error\ndata: {"type":"error","error_class":"internal"}\n\n'
                return
            if generation.status in TERMINAL:
                payload = json.dumps(
                    {"type": "done", "status": generation.status.value},
                    ensure_ascii=False,
                )
                yield f"event: done\ndata: {payload}\n\n"
                return
            await asyncio.sleep(0.2)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
