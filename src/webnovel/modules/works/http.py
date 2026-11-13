from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import WorkServiceDep

router = APIRouter(prefix="/works", tags=["works"])


class WorkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=64)


class WorkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    genre: str | None
    status: str


class WorkUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)


class WorkList(BaseModel):
    items: list[WorkOut]


@router.post("", response_model=WorkOut, status_code=status.HTTP_201_CREATED)
async def create_work(body: WorkCreate, service: WorkServiceDep) -> WorkOut:
    work = await service.create(title=body.title, genre=body.genre)
    return WorkOut.model_validate(work)


@router.get("", response_model=WorkList)
async def list_works(service: WorkServiceDep, limit: int = 50) -> WorkList:
    works = await service.list(limit=min(max(limit, 1), 200))
    return WorkList(items=[WorkOut.model_validate(work) for work in works])


@router.get("/{work_id}", response_model=WorkOut)
async def get_work(work_id: UUID, service: WorkServiceDep) -> WorkOut:
    return WorkOut.model_validate(await service.get(work_id))


@router.patch("/{work_id}", response_model=WorkOut)
async def update_work(work_id: UUID, body: WorkUpdate, service: WorkServiceDep) -> WorkOut:
    return WorkOut.model_validate(
        await service.update(work_id, body.title, body.genre, body.status)
    )


@router.delete("/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work(work_id: UUID, service: WorkServiceDep) -> None:
    await service.delete(work_id)
