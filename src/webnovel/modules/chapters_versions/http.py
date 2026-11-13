from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import ChapterExtractionQueueDep, ChapterServiceDep

router = APIRouter(tags=["chapters"])
logger = structlog.get_logger(__name__)


class ChapterCreate(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    content: str = ""


class ChapterAssignVolume(BaseModel):
    volume_id: UUID | None = None


class ChapterSave(BaseModel):
    base_version: int = Field(ge=0)
    content: str
    title: str | None = Field(default=None, max_length=200)


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    number: int
    title: str
    current_version_id: UUID | None
    lock_version: int
    word_count: int
    created_at: datetime
    updated_at: datetime
    volume_id: UUID | None = None


class ChapterList(BaseModel):
    items: list[ChapterOut]


class ChapterVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    parent_version_id: UUID | None
    content: str
    content_hash: str
    source: str
    created_at: datetime


class ChapterVersionList(BaseModel):
    items: list[ChapterVersionOut]


@router.post(
    "/works/{work_id}/chapters",
    response_model=ChapterOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    work_id: UUID, body: ChapterCreate, service: ChapterServiceDep
) -> ChapterOut:
    chapter = await service.create(
        work_id=work_id, number=body.number, title=body.title, content=body.content
    )
    return ChapterOut.model_validate(chapter)


@router.get("/works/{work_id}/chapters", response_model=ChapterList)
async def list_chapters(work_id: UUID, service: ChapterServiceDep) -> ChapterList:
    chapters = await service.list(work_id)
    return ChapterList(items=[ChapterOut.model_validate(chapter) for chapter in chapters])


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
async def get_chapter(chapter_id: UUID, service: ChapterServiceDep) -> ChapterOut:
    return ChapterOut.model_validate(await service.get(chapter_id))


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
async def save_chapter(
    chapter_id: UUID,
    body: ChapterSave,
    service: ChapterServiceDep,
    extraction_queue: ChapterExtractionQueueDep,
) -> ChapterOut:
    chapter = await service.save(
        chapter_id=chapter_id,
        base_version=body.base_version,
        content=body.content,
        title=body.title,
    )
    if chapter.current_version_id is not None:
        try:
            await extraction_queue.enqueue_chapter_extraction(chapter.id)
        except Exception:
            logger.exception("chapter.extraction_enqueue_failed", chapter_id=str(chapter.id))
    return ChapterOut.model_validate(chapter)


@router.put("/chapters/{chapter_id}/volume", response_model=ChapterOut)
async def assign_chapter_volume(
    chapter_id: UUID, body: ChapterAssignVolume, service: ChapterServiceDep
) -> ChapterOut:
    return ChapterOut.model_validate(await service.assign_volume(chapter_id, body.volume_id))


@router.get("/chapters/{chapter_id}/versions", response_model=ChapterVersionList)
async def list_chapter_versions(chapter_id: UUID, service: ChapterServiceDep) -> ChapterVersionList:
    versions = await service.versions(chapter_id)
    return ChapterVersionList(
        items=[ChapterVersionOut.model_validate(version) for version in versions]
    )
