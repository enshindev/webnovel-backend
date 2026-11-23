from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.kernel.errors import NotFoundError, UnavailableError, ValidationError
from webnovel.kernel.ports.embeddings import EmbeddingClient
from webnovel.kernel.ports.rerank import Reranker
from webnovel.llm.retrieval.bm25 import BM25Index
from webnovel.modules.library.contract import LibraryCollection, LibraryDocument, LibraryService
from webnovel.modules.library.repository import LibraryRepository
from webnovel.modules.multimodal.contract import TranscriptionProvider
from webnovel.modules.usage.contract import UsageService, record_media_usage

_OCR_ENGINE: Any | None = None
_AUDIO_SUFFIXES = {"mp3", "wav", "m4a", "ogg", "webm", "flac"}


class LibraryServiceImpl(LibraryService):
    def __init__(
        self,
        repository: LibraryRepository,
        settings: Settings,
        embedding_client: EmbeddingClient | None = None,
        usage: UsageService | None = None,
        reranker: Reranker | None = None,
        transcriber: TranscriptionProvider | None = None,
        experiments_enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._embedding_client = embedding_client
        self._usage = usage
        self._reranker = reranker
        self._transcriber = transcriber
        self._experiments_enabled = experiments_enabled

    async def create_collection(
        self, name: str, description: str | None, work_id: UUID | None
    ) -> LibraryCollection:
        if not name.strip():
            raise ValidationError("collection name required", code="library.name_required")
        return await self._repository.create_collection(name.strip(), description, work_id)

    async def list_collections(self, work_id: UUID | None = None) -> list[LibraryCollection]:
        return await self._repository.list_collections(work_id)

    async def get_collection(self, collection_id: UUID) -> LibraryCollection:
        collection = await self._repository.get_collection(collection_id)
        if collection is None:
            raise NotFoundError(
                f"collection not found: {collection_id}", code="library.collection_not_found"
            )
        return collection

    async def delete_collection(self, collection_id: UUID) -> None:
        if not await self._repository.delete_collection(collection_id):
            raise NotFoundError(
                f"collection not found: {collection_id}", code="library.collection_not_found"
            )

    async def add_document(
        self, collection_id: UUID, filename: str, data: bytes
    ) -> LibraryDocument:
        if not data:
            raise ValidationError("empty file", code="library.empty_file")
        suffix = Path(filename).suffix.lower().lstrip(".") or "bin"
        if suffix not in {"txt", "md", "docx", "pdf", "png", "jpg", "jpeg"} | _AUDIO_SUFFIXES:
            raise ValidationError("unsupported file type", code="library.unsupported_type")
        digest = hashlib.sha256(data).hexdigest()
        storage_key = f"{uuid4().hex}.{suffix}"
        root = self._settings.library_dir
        root.mkdir(parents=True, exist_ok=True)
        (root / storage_key).write_bytes(data)
        try:
            document = await self._repository.create_document(
                collection_id=collection_id,
                title=Path(filename).name,
                kind=suffix,
                storage_key=storage_key,
                content_hash=digest,
                status="uploaded",
            )
            text = await self._extract_text(filename, suffix, data)
            if text.strip() and self._embedding_client is not None:
                chunks = _chunk(text)
                vectors = await self._embedding_client.embed(chunks)
                await self._repository.replace_chunks(
                    document.id,
                    [
                        (chunk, vector, hashlib.sha256(chunk.encode()).hexdigest())
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ],
                )
                await self._repository.set_status(document.id, "ready")
            elif text.strip():
                await self._repository.set_status(document.id, "parsed")
            return await self._repository.get_document(document.id) or document
        except Exception:
            (root / storage_key).unlink(missing_ok=True)
            raise

    async def get_document(self, document_id: UUID) -> LibraryDocument:
        document = await self._repository.get_document(document_id)
        if document is None:
            raise NotFoundError(f"document not found: {document_id}", code="library.not_found")
        return document

    async def list_documents(self, collection_id: UUID) -> list[LibraryDocument]:
        return await self._repository.list_documents(collection_id)

    async def reindex(self, document_id: UUID) -> LibraryDocument:
        document = await self.get_document(document_id)
        path = self._settings.library_dir / document.storage_key
        if not path.is_file():
            raise NotFoundError("library file missing", code="library.file_missing")
        await self._index_document(document, path.read_bytes())
        return await self.get_document(document_id)

    async def _index_document(self, document: LibraryDocument, data: bytes) -> None:
        text = await self._extract_text(document.title, document.kind, data)
        if not text.strip():
            await self._repository.set_status(document.id, "uploaded")
            return
        if self._embedding_client is None:
            await self._repository.set_status(document.id, "parsed")
            return
        chunks = _chunk(text)
        vectors = await self._embedding_client.embed(chunks)
        await self._repository.replace_chunks(
            document.id,
            [
                (chunk, vector, hashlib.sha256(chunk.encode()).hexdigest())
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        await self._repository.set_status(document.id, "ready")

    async def _extract_text(self, filename: str, suffix: str, data: bytes) -> str:
        if suffix in _AUDIO_SUFFIXES:
            if not self._experiments_enabled:
                raise ValidationError(
                    "audio import requires ENABLE_EXPERIMENTS=true",
                    code="library.audio_experiment_disabled",
                )
            if self._transcriber is None:
                raise UnavailableError(
                    "audio import requires ASR configuration", code="library.asr_unavailable"
                )
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            text = await self._transcriber.transcribe(filename, content_type, data)
            await record_media_usage(
                self._usage,
                work_id=None,
                task="asr",
                model=str(getattr(self._transcriber, "model", "multimodal") or "multimodal"),
                prompt_units=len(data),
                output_units=len(text),
            )
            return text
        return _parse_text(data, suffix)

    async def search(
        self,
        query: str,
        limit: int = 8,
        *,
        work_id: UUID | None = None,
        collection_id: UUID | None = None,
    ) -> list[dict[str, object]]:
        if self._embedding_client is None:
            raise ValidationError(
                "library search requires embedding", code="library.search_unavailable"
            )
        vector = (await self._embedding_client.embed([query]))[0]
        vector_hits = await self._repository.search(
            vector, limit, work_id=work_id, collection_id=collection_id
        )
        list_all = getattr(self._repository, "list_all_chunks", None)
        if list_all is None:
            return vector_hits
        all_chunks = await list_all(work_id=work_id, collection_id=collection_id)
        if not all_chunks:
            return vector_hits
        bm25 = BM25Index([str(chunk["text"]) for chunk in all_chunks])
        lexical = [
            {**all_chunks[index], "score": int(score * 100)}
            for index, score in bm25.search(query, limit)
        ]
        rankings = [
            [f"{hit['document_id']}:{hit['chunk_index']}" for hit in vector_hits],
            [f"{hit['document_id']}:{hit['chunk_index']}" for hit in lexical],
        ]
        from webnovel.llm.retrieval.fusion import reciprocal_rank_fusion

        merged = reciprocal_rank_fusion(rankings)
        by_key = {
            f"{hit['document_id']}:{hit['chunk_index']}": hit for hit in [*vector_hits, *lexical]
        }
        candidates = [by_key[key] for key, _ in merged if key in by_key][:20]
        if self._reranker is None or len(candidates) < 2:
            return candidates[:limit]
        try:
            reranked = await self._reranker.rerank(
                query, [str(hit["text"]) for hit in candidates], top_n=limit
            )
            return [
                candidates[item.index] for item in reranked if 0 <= item.index < len(candidates)
            ]
        except Exception:
            return candidates[:limit]

    async def delete_document(self, document_id: UUID) -> None:
        key = await self._repository.delete_document(document_id)
        if key is None:
            raise NotFoundError(f"document not found: {document_id}", code="library.not_found")
        (self._settings.library_dir / key).unlink(missing_ok=True)


def _parse_text(data: bytes, suffix: str) -> str:
    if suffix in {"txt", "md"}:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("gb18030", errors="ignore")
    if suffix == "docx":
        from io import BytesIO

        from docx import Document

        document = Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix == "pdf":
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {"png", "jpg", "jpeg"}:
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(data))
        try:
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR

            global _OCR_ENGINE
            if _OCR_ENGINE is None:
                _OCR_ENGINE = RapidOCR()
            result, _ = _OCR_ENGINE(np.array(image))
            if result:
                return "\n".join(str(line[1]) for line in result)
        except Exception:
            pass
        try:
            import pytesseract

            return str(pytesseract.image_to_string(image, lang=os.getenv("OCR_LANG", "eng")))
        except Exception:
            return ""
    return ""


def _chunk(text: str, size: int = 800) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > size:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [text.strip()[:size]]
