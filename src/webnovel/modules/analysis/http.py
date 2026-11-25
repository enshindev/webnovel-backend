from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import AnalysisServiceDep

router = APIRouter(tags=["analysis"])


class ReverseOutlineBody(BaseModel):
    chapter_range: dict[str, int] | None = None


class OutlineDraftPatch(BaseModel):
    content: dict[str, Any]
    status: str | None = None


class OutlineDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    analysis_run_id: UUID | None
    status: str
    content: dict[str, Any]


class ChapterAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    chapter_id: UUID
    version_id: UUID | None
    summary: str
    beats: list[dict[str, Any]]
    pov: str | None
    time_text: str | None
    characters: list[str]
    hook: str | None
    hook_type: str | None
    issues: list[dict[str, Any]]
    status: str
    progress: int
    boundary_confidence: float | None


class SplitChapterBody(BaseModel):
    offset: int


class ChapterAnalysisPatch(BaseModel):
    summary: str | None = None
    beats: list[dict[str, Any]] | None = None
    pov: str | None = None
    time_text: str | None = None
    characters: list[str] | None = None
    hook: str | None = None
    hook_type: str | None = None
    boundary_confidence: float | None = None


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    kind: str
    status: str
    params: dict[str, Any]
    report: dict[str, Any]
    error: str | None
    created_at: datetime


@router.post(
    "/works/{work_id}/analysis/reverse-outline",
    response_model=AnalysisRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_reverse_outline(
    work_id: UUID, body: ReverseOutlineBody, service: AnalysisServiceDep
) -> AnalysisRunOut:
    run = await service.start_reverse_outline(work_id, body.chapter_range)
    return AnalysisRunOut.model_validate(run)


@router.post(
    "/works/{work_id}/analysis/import",
    response_model=AnalysisRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_manuscript(
    work_id: UUID,
    service: AnalysisServiceDep,
    file: Annotated[UploadFile, File()],
) -> AnalysisRunOut:
    run = await service.import_document(
        work_id, file.filename or "manuscript.txt", await file.read()
    )
    return AnalysisRunOut.model_validate(run)


@router.get("/works/{work_id}/analysis/runs", response_model=list[AnalysisRunOut])
async def list_analysis_runs(
    work_id: UUID, service: AnalysisServiceDep, limit: int = 50
) -> list[AnalysisRunOut]:
    return [
        AnalysisRunOut.model_validate(run)
        for run in await service.list_runs(work_id, min(max(limit, 1), 200))
    ]


@router.get("/analysis/runs/{run_id}", response_model=AnalysisRunOut)
async def get_analysis_run(run_id: UUID, service: AnalysisServiceDep) -> AnalysisRunOut:
    return AnalysisRunOut.model_validate(await service.get(run_id))


@router.get(
    "/analysis/runs/{run_id}/chapters",
    response_model=list[ChapterAnalysisOut],
)
async def list_analysis_chapters(
    run_id: UUID, service: AnalysisServiceDep
) -> list[ChapterAnalysisOut]:
    return [
        ChapterAnalysisOut.model_validate(chapter)
        for chapter in await service.list_chapters(run_id)
    ]


@router.patch(
    "/analysis/runs/{run_id}/chapters/{chapter_id}",
    response_model=ChapterAnalysisOut,
)
async def update_analysis_chapter(
    run_id: UUID,
    chapter_id: UUID,
    body: ChapterAnalysisPatch,
    service: AnalysisServiceDep,
) -> ChapterAnalysisOut:
    values = body.model_dump(exclude_none=True)
    return ChapterAnalysisOut.model_validate(
        await service.update_chapter(run_id, chapter_id, values)
    )


@router.post(
    "/analysis/runs/{run_id}/chapters/{chapter_id}/retry",
    response_model=ChapterAnalysisOut,
)
async def retry_analysis_chapter(
    run_id: UUID, chapter_id: UUID, service: AnalysisServiceDep
) -> ChapterAnalysisOut:
    return ChapterAnalysisOut.model_validate(await service.retry_chapter(run_id, chapter_id))


@router.post(
    "/analysis/runs/{run_id}/chapters/{chapter_id}/split",
    response_model=list[dict[str, str]],
)
async def split_analysis_chapter(
    run_id: UUID, chapter_id: UUID, body: SplitChapterBody, service: AnalysisServiceDep
) -> list[dict[str, str]]:
    result = await service.split_chapter(run_id, chapter_id, body.offset)
    return [
        {"id": str(result.first.id), "title": result.first.title},
        {"id": str(result.second.id), "title": result.second.title},
    ]


@router.get("/analysis/runs/{run_id}/outline", response_model=OutlineDraftOut)
async def get_outline(run_id: UUID, service: AnalysisServiceDep) -> OutlineDraftOut:
    return OutlineDraftOut.model_validate(await service.get_outline(run_id))


@router.post("/analysis/runs/{run_id}/apply", response_model=OutlineDraftOut)
async def apply_analysis(run_id: UUID, service: AnalysisServiceDep) -> OutlineDraftOut:
    return OutlineDraftOut.model_validate(await service.apply(run_id))


@router.patch("/analysis/runs/{run_id}/outline", response_model=OutlineDraftOut)
async def update_outline(
    run_id: UUID, body: OutlineDraftPatch, service: AnalysisServiceDep
) -> OutlineDraftOut:
    return OutlineDraftOut.model_validate(
        await service.update_outline(run_id, body.content, body.status)
    )
