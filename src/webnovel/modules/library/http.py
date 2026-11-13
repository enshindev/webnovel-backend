from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import LibraryServiceDep

router = APIRouter(prefix="/experiments/library", tags=["library"])


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    work_id: UUID | None = None


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID | None
    name: str
    description: str | None
    created_at: datetime


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=30)


class SearchOut(BaseModel):
    chunks: list[dict[str, object]]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    title: str
    kind: str
    storage_key: str
    content_hash: str
    status: str
    error: str | None
    created_at: datetime


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(body: CollectionCreate, service: LibraryServiceDep) -> CollectionOut:
    return CollectionOut.model_validate(
        await service.create_collection(body.name, body.description, body.work_id)
    )


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(
    service: LibraryServiceDep, work_id: UUID | None = None
) -> list[CollectionOut]:
    return [CollectionOut.model_validate(item) for item in await service.list_collections(work_id)]


@router.get("/collections/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: UUID, service: LibraryServiceDep) -> CollectionOut:
    return CollectionOut.model_validate(await service.get_collection(collection_id))


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: UUID, service: LibraryServiceDep) -> None:
    await service.delete_collection(collection_id)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    service: LibraryServiceDep,
    collection_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    data = await file.read()
    return DocumentOut.model_validate(
        await service.add_document(collection_id, file.filename or "upload", data)
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: UUID, service: LibraryServiceDep) -> DocumentOut:
    return DocumentOut.model_validate(await service.get_document(document_id))


@router.get("/collections/{collection_id}/documents", response_model=list[DocumentOut])
async def list_documents(collection_id: UUID, service: LibraryServiceDep) -> list[DocumentOut]:
    return [
        DocumentOut.model_validate(item) for item in await service.list_documents(collection_id)
    ]


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
async def reindex_document(document_id: UUID, service: LibraryServiceDep) -> DocumentOut:
    return DocumentOut.model_validate(await service.reindex(document_id))


@router.post("/search", response_model=SearchOut)
async def search_library(body: SearchBody, service: LibraryServiceDep) -> SearchOut:
    return SearchOut(chunks=await service.search(body.query, body.limit))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, service: LibraryServiceDep) -> None:
    await service.delete_document(document_id)
