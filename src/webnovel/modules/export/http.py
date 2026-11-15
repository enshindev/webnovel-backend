from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import ExportServiceDep

router = APIRouter(tags=["export"])


class ExportCreate(BaseModel):
    format: Literal["txt", "docx", "mp3", "cover"] = "txt"


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    format: str
    status: str
    file_path: str | None
    created_at: datetime
    download_token: str | None
    expires_at: datetime | None


@router.post(
    "/works/{work_id}/exports",
    response_model=ExportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    work_id: UUID, body: ExportCreate, service: ExportServiceDep
) -> ExportJobOut:
    job = await service.create(work_id, body.format)
    return ExportJobOut.model_validate(job)


@router.get("/exports/{job_id}", response_model=ExportJobOut)
async def get_export(job_id: UUID, service: ExportServiceDep) -> ExportJobOut:
    return ExportJobOut.model_validate(await service.get(job_id))


@router.get("/exports/{job_id}/download")
async def download_export(
    job_id: UUID, service: ExportServiceDep, token: str | None = None
) -> FileResponse:
    job = await service.get(job_id)
    if job.download_token is not None and token != job.download_token:
        raise HTTPException(status_code=403, detail="invalid download token")
    if job.expires_at is not None and job.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="export expired")
    if job.status != "succeeded" or job.file_path is None:
        raise HTTPException(status_code=409, detail="export is not ready")
    path = Path(job.file_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="export file is missing")
    suffix = path.suffix
    media = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".mp3": "audio/mpeg",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }.get(suffix, "text/plain")
    return FileResponse(path, filename=f"work-{job.work_id}{suffix}", media_type=media)
