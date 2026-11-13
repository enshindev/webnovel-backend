from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LibraryCollection:
    id: UUID
    work_id: UUID | None
    name: str
    description: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LibraryDocument:
    id: UUID
    collection_id: UUID
    title: str
    kind: str
    storage_key: str
    content_hash: str
    status: str
    error: str | None
    created_at: datetime


class LibraryService(Protocol):
    async def create_collection(
        self, name: str, description: str | None, work_id: UUID | None
    ) -> LibraryCollection: ...

    async def list_collections(self, work_id: UUID | None = None) -> list[LibraryCollection]: ...

    async def get_collection(self, collection_id: UUID) -> LibraryCollection: ...

    async def delete_collection(self, collection_id: UUID) -> None: ...

    async def add_document(
        self, collection_id: UUID, filename: str, data: bytes
    ) -> LibraryDocument: ...

    async def get_document(self, document_id: UUID) -> LibraryDocument: ...

    async def list_documents(self, collection_id: UUID) -> list[LibraryDocument]: ...

    async def delete_document(self, document_id: UUID) -> None: ...

    async def search(self, query: str, limit: int = 8) -> list[dict[str, object]]: ...

    async def reindex(self, document_id: UUID) -> LibraryDocument: ...
