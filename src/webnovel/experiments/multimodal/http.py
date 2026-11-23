from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from webnovel.entrypoints.api.deps import MultimodalServiceDep
from webnovel.kernel.errors import ValidationError
from webnovel.experiments.multimodal.contract import MultimodalStatus

router = APIRouter(prefix="/experiments/multimodal", tags=["multimodal"])

_MAX_AUDIO_BYTES = 20 * 1024 * 1024


class TranscribeOut(BaseModel):
    text: str


class SpeechBody(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)
    voice: str | None = Field(default=None, max_length=64)
    work_id: UUID | None = None


class CoverBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)
    size: str = Field(default="1024x1024", pattern=r"^\d{3,4}x\d{3,4}$")
    work_id: UUID | None = None


@router.get("/status", response_model=MultimodalStatus)
async def status(service: MultimodalServiceDep) -> MultimodalStatus:
    return cast(MultimodalStatus, service.status())


@router.post("/transcribe", response_model=TranscribeOut)
async def transcribe(
    service: MultimodalServiceDep,
    file: Annotated[UploadFile, File()],
    work_id: Annotated[UUID | None, Form()] = None,
) -> TranscribeOut:
    data = await file.read()
    if not data:
        raise ValidationError("audio file is empty", code="multimodal.empty_audio")
    if len(data) > _MAX_AUDIO_BYTES:
        raise ValidationError("audio file is too large", code="multimodal.audio_too_large")
    text = await service.transcribe(
        file.filename or "audio.bin",
        file.content_type or "application/octet-stream",
        data,
        work_id=work_id,
    )
    return TranscribeOut(text=text)


@router.post("/speech")
async def speech(body: SpeechBody, service: MultimodalServiceDep) -> Response:
    audio = await service.synthesize(body.text, body.voice, work_id=body.work_id)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/cover")
async def cover(body: CoverBody, service: MultimodalServiceDep) -> Response:
    image = await service.cover(body.prompt, body.size, work_id=body.work_id)
    media_type = "image/jpeg" if image.startswith(b"\xff\xd8\xff") else "image/png"
    return Response(content=image, media_type=media_type)
