from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import VolumeServiceDep

router = APIRouter(tags=["volumes"])


class VolumeCreate(BaseModel):
    number: int = Field(ge=1)
    title: str = ""


class VolumeUpdate(BaseModel):
    number: int | None = Field(default=None, ge=1)
    title: str | None = None


class VolumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    number: int
    title: str
    created_at: datetime


@router.post("/works/{work_id}/volumes", response_model=VolumeOut, status_code=201)
async def create_volume(work_id: UUID, body: VolumeCreate, service: VolumeServiceDep) -> VolumeOut:
    return VolumeOut.model_validate(await service.create(work_id, body.number, body.title))


@router.get("/works/{work_id}/volumes", response_model=list[VolumeOut])
async def list_volumes(work_id: UUID, service: VolumeServiceDep) -> list[VolumeOut]:
    return [VolumeOut.model_validate(item) for item in await service.list(work_id)]


@router.patch("/volumes/{volume_id}", response_model=VolumeOut)
async def update_volume(
    volume_id: UUID, body: VolumeUpdate, service: VolumeServiceDep
) -> VolumeOut:
    return VolumeOut.model_validate(await service.update(volume_id, body.number, body.title))


@router.delete("/volumes/{volume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volume(volume_id: UUID, service: VolumeServiceDep) -> None:
    await service.delete(volume_id)
