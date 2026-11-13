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
