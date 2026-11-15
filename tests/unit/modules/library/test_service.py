from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.kernel.errors import UnavailableError
from webnovel.modules.library.contract import LibraryCollection, LibraryDocument
from webnovel.modules.library.service import LibraryServiceImpl


class FakeLibraryRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, LibraryDocument] = {}

    async def create_collection(
        self, name: str, description: str | None, work_id: UUID | None
    ) -> LibraryCollection:
        return LibraryCollection(uuid4(), work_id, name, description, datetime.now(UTC))

    async def create_document(self, **values: Any) -> LibraryDocument:
        document = LibraryDocument(
            id=uuid4(),
            collection_id=values["collection_id"],
            title=values["title"],
            kind=values["kind"],
            storage_key=values["storage_key"],
            content_hash=values["content_hash"],
            status=values["status"],
            error=None,
            created_at=datetime.now(UTC),
        )
        self.documents[document.id] = document
        return document

    async def get_document(self, document_id: UUID) -> LibraryDocument | None:
        return self.documents.get(document_id)

    async def list_documents(self, collection_id: UUID) -> list[LibraryDocument]:
        return list(self.documents.values())

    async def set_status(self, document_id: UUID, status: str, error: str | None = None) -> None:
        document = self.documents.get(document_id)
        if document is not None:
            self.documents[document_id] = replace(document, status=status)

    async def delete_document(self, document_id: UUID) -> str | None:
        document = self.documents.pop(document_id, None)
        return document.storage_key if document else None


async def test_upload_and_delete_library_document(tmp_path: Path) -> None:
    repository = FakeLibraryRepository()
    service = LibraryServiceImpl(repository, Settings(library_dir=tmp_path))
    document = await service.add_document(uuid4(), "notes.md", b"# notes")
    assert (tmp_path / document.storage_key).is_file()
    await service.delete_document(document.id)
    assert not (tmp_path / document.storage_key).exists()


class FakeTranscriber:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes]] = []

    async def transcribe(self, filename: str, content_type: str, data: bytes) -> str:
        self.calls.append((filename, content_type, data))
        return "音频里的文字"


async def test_audio_document_uses_asr(tmp_path: Path) -> None:
    repository = FakeLibraryRepository()
    transcriber = FakeTranscriber()
    service = LibraryServiceImpl(
        repository, Settings(library_dir=tmp_path), transcriber=transcriber
    )
    document = await service.add_document(uuid4(), "voice.mp3", b"audio")
    assert document.kind == "mp3"
    assert document.status == "parsed"
    assert transcriber.calls[0][0] == "voice.mp3"
    assert transcriber.calls[0][2] == b"audio"


async def test_audio_document_requires_asr(tmp_path: Path) -> None:
    service = LibraryServiceImpl(FakeLibraryRepository(), Settings(library_dir=tmp_path))
    try:
        await service.add_document(uuid4(), "voice.mp3", b"audio")
    except UnavailableError as exc:
        assert exc.code == "library.asr_unavailable"
    else:
        raise AssertionError("expected UnavailableError")
