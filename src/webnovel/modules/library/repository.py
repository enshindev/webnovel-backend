from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.library.contract import LibraryCollection, LibraryDocument
from webnovel.modules.library.models import (
    LibraryChunkModel,
    LibraryCollectionModel,
    LibraryDocumentModel,
)


class LibraryRepository(Protocol):
    async def create_collection(
        self, name: str, description: str | None, work_id: UUID | None
    ) -> LibraryCollection: ...

    async def create_document(self, **values: Any) -> LibraryDocument: ...

    async def list_collections(self, work_id: UUID | None) -> list[LibraryCollection]: ...

    async def get_collection(self, collection_id: UUID) -> LibraryCollection | None: ...

    async def delete_collection(self, collection_id: UUID) -> bool: ...

    async def get_document(self, document_id: UUID) -> LibraryDocument | None: ...

    async def find_document_by_hash(
        self, collection_id: UUID, content_hash: str
    ) -> LibraryDocument | None: ...

    async def list_documents(self, collection_id: UUID) -> list[LibraryDocument]: ...

    async def delete_document(self, document_id: UUID) -> str | None: ...

    async def set_status(
        self, document_id: UUID, status: str, error: str | None = None
    ) -> None: ...

    async def replace_chunks(
        self, document_id: UUID, chunks: list[tuple[str, list[float], str]]
    ) -> None: ...

    async def search(
        self,
        embedding: list[float],
        limit: int,
        *,
        collection_id: UUID | None = None,
        work_id: UUID | None = None,
    ) -> list[dict[str, Any]]: ...


def _collection(model: LibraryCollectionModel) -> LibraryCollection:
    return LibraryCollection(
        model.id, model.work_id, model.name, model.description, model.created_at
    )


def _document(model: LibraryDocumentModel) -> LibraryDocument:
    return LibraryDocument(
        model.id,
        model.collection_id,
        model.title,
        model.kind,
        model.storage_key,
        model.content_hash,
        model.status,
        model.error,
        model.created_at,
    )


class SqlAlchemyLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_collection(
        self, name: str, description: str | None, work_id: UUID | None
    ) -> LibraryCollection:
        model = LibraryCollectionModel(name=name, description=description, work_id=work_id)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _collection(model)

    async def list_collections(self, work_id: UUID | None) -> list[LibraryCollection]:
        stmt = select(LibraryCollectionModel)
        if work_id is not None:
            stmt = stmt.where(LibraryCollectionModel.work_id == work_id)
        rows = (
            (await self._session.execute(stmt.order_by(LibraryCollectionModel.created_at.desc())))
            .scalars()
            .all()
        )
        return [_collection(row) for row in rows]

    async def get_collection(self, collection_id: UUID) -> LibraryCollection | None:
        model = await self._session.get(LibraryCollectionModel, collection_id)
        return _collection(model) if model is not None else None

    async def delete_collection(self, collection_id: UUID) -> bool:
        model = await self._session.get(LibraryCollectionModel, collection_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def create_document(self, **values: Any) -> LibraryDocument:
        model = LibraryDocumentModel(**values)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _document(model)

    async def find_document_by_hash(
        self, collection_id: UUID, content_hash: str
    ) -> LibraryDocument | None:
        model = (
            await self._session.scalars(
                select(LibraryDocumentModel)
                .where(
                    LibraryDocumentModel.collection_id == collection_id,
                    LibraryDocumentModel.content_hash == content_hash,
                )
                .limit(1)
            )
        ).first()
        return _document(model) if model is not None else None

    async def get_document(self, document_id: UUID) -> LibraryDocument | None:
        model = await self._session.get(LibraryDocumentModel, document_id)
        return _document(model) if model is not None else None

    async def list_documents(self, collection_id: UUID) -> list[LibraryDocument]:
        rows = (
            (
                await self._session.execute(
                    select(LibraryDocumentModel)
                    .where(LibraryDocumentModel.collection_id == collection_id)
                    .order_by(LibraryDocumentModel.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [_document(row) for row in rows]

    async def delete_document(self, document_id: UUID) -> str | None:
        model = await self._session.get(LibraryDocumentModel, document_id)
        if model is None:
            return None
        key = model.storage_key
        await self._session.delete(model)
        await self._session.flush()
        return key

    async def set_status(self, document_id: UUID, status: str, error: str | None = None) -> None:
        model = await self._session.get(LibraryDocumentModel, document_id)
        if model is not None:
            model.status = status
            model.error = error
            await self._session.flush()

    async def replace_chunks(
        self, document_id: UUID, chunks: list[tuple[str, list[float], str]]
    ) -> None:
        from sqlalchemy import delete

        await self._session.execute(
            delete(LibraryChunkModel).where(LibraryChunkModel.document_id == document_id)
        )
        for index, (text, embedding, content_hash) in enumerate(chunks):
            self._session.add(
                LibraryChunkModel(
                    document_id=document_id,
                    chunk_index=index,
                    text=text,
                    embedding=embedding,
                    content_hash=content_hash,
                )
            )
        await self._session.flush()

    async def list_all_chunks(
        self, *, collection_id: UUID | None = None, work_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(LibraryChunkModel, LibraryDocumentModel.title).join(
            LibraryDocumentModel, LibraryDocumentModel.id == LibraryChunkModel.document_id
        )
        if collection_id is not None:
            stmt = stmt.where(LibraryDocumentModel.collection_id == collection_id)
        if work_id is not None:
            stmt = stmt.join(LibraryCollectionModel).where(
                LibraryCollectionModel.work_id == work_id
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "document_id": row[0].document_id,
                "title": row[1],
                "chunk_index": row[0].chunk_index,
                "text": row[0].text,
            }
            for row in rows
        ]

    async def search(
        self,
        embedding: list[float],
        limit: int,
        *,
        collection_id: UUID | None = None,
        work_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select

        distance = LibraryChunkModel.embedding.cosine_distance(embedding)
        stmt = (
            select(LibraryChunkModel, LibraryDocumentModel.title, distance.label("distance"))
            .join(LibraryDocumentModel, LibraryDocumentModel.id == LibraryChunkModel.document_id)
            .order_by(distance)
            .limit(limit)
        )
        if collection_id is not None:
            stmt = stmt.where(LibraryDocumentModel.collection_id == collection_id)
        if work_id is not None:
            stmt = stmt.join(LibraryCollectionModel).where(
                LibraryCollectionModel.work_id == work_id
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "document_id": row[0].document_id,
                "title": row[1],
                "chunk_index": row[0].chunk_index,
                "text": row[0].text,
                "score": max(0, int((1 - float(row[2])) * 100)),
            }
            for row in rows
        ]
