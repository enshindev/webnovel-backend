from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import StyleServiceDep

router = APIRouter(tags=["style"])


class StyleProfileCreate(BaseModel):
    chapter_ids: list[UUID] = Field(min_length=1, max_length=5)


class StyleProfilePatch(BaseModel):
    summary: str | None = None
    status: str | None = None
    do_list: list[str] | None = None
    dont_list: list[str] | None = None


class StyleProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    version: int
    status: str
    features: dict[str, Any]
    qualitative: dict[str, Any]
    summary: str
    do_list: list[str]
    dont_list: list[str]
    created_at: datetime


class StyleCheckCreate(BaseModel):
    content: str = Field(min_length=1)


class CharacterSampleCreate(BaseModel):
    character_name: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1)


class CharacterCheckCreate(BaseModel):
    character_name: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)


class StyleRewriteCreate(BaseModel):
    content: str = Field(min_length=1)


class StyleCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    profile_id: UUID
    score: float
    dimensions: dict[str, Any]
    issues: list[dict[str, Any]]
    created_at: datetime


class StyleRewriteOut(BaseModel):
    content: str
    check: StyleCheckOut


@router.post(
    "/works/{work_id}/style-profiles",
    response_model=StyleProfileOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_style_profile(
    work_id: UUID, body: StyleProfileCreate, service: StyleServiceDep
) -> StyleProfileOut:
    return StyleProfileOut.model_validate(await service.create_profile(work_id, body.chapter_ids))


@router.get("/works/{work_id}/style-profiles/{profile_id}", response_model=StyleProfileOut)
async def get_style_profile(
    work_id: UUID, profile_id: UUID, service: StyleServiceDep
) -> StyleProfileOut:
    return StyleProfileOut.model_validate(await service.get_profile(work_id, profile_id))


@router.patch("/works/{work_id}/style-profiles/{profile_id}", response_model=StyleProfileOut)
async def update_style_profile(
    work_id: UUID,
    profile_id: UUID,
    body: StyleProfilePatch,
    service: StyleServiceDep,
) -> StyleProfileOut:
    return StyleProfileOut.model_validate(
        await service.update_profile(
            work_id,
            profile_id,
            summary=body.summary,
            status=body.status,
            do_list=body.do_list,
            dont_list=body.dont_list,
        )
    )


@router.post(
    "/works/{work_id}/style-profiles/{profile_id}/character-samples",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_character_sample(
    work_id: UUID,
    profile_id: UUID,
    body: CharacterSampleCreate,
    service: StyleServiceDep,
) -> None:
    await service.add_character_sample(work_id, profile_id, body.character_name, body.text)


@router.post(
    "/works/{work_id}/style-profiles/{profile_id}/character-check",
    response_model=StyleCheckOut,
)
async def check_character(
    work_id: UUID,
    profile_id: UUID,
    body: CharacterCheckCreate,
    service: StyleServiceDep,
) -> StyleCheckOut:
    return StyleCheckOut.model_validate(
        await service.check_character(work_id, profile_id, body.character_name, body.content)
    )


@router.post(
    "/works/{work_id}/style-profiles/{profile_id}/rewrite",
    response_model=StyleRewriteOut,
)
async def rewrite_style(
    work_id: UUID,
    profile_id: UUID,
    body: StyleRewriteCreate,
    service: StyleServiceDep,
) -> StyleRewriteOut:
    result = await service.rewrite(work_id, profile_id, body.content)
    return StyleRewriteOut(
        content=result.content,
        check=StyleCheckOut.model_validate(result.check),
    )


@router.post(
    "/works/{work_id}/style-profiles/{profile_id}/check",
    response_model=StyleCheckOut,
)
async def check_style(
    work_id: UUID,
    profile_id: UUID,
    body: StyleCheckCreate,
    service: StyleServiceDep,
) -> StyleCheckOut:
    return StyleCheckOut.model_validate(await service.check(work_id, profile_id, body.content))
