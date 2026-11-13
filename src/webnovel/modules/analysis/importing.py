from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

_CHAPTER = re.compile(
    r"^\s*(第[一二三四五六七八九十百千万0-9]+章|Chapter\s+\d+)\s*[：: ]?(.*)$", re.MULTILINE
)


@dataclass(frozen=True, slots=True)
class ImportedChapter:
    number: int
    title: str
    content: str


def split_chapters(text: str) -> list[ImportedChapter]:
    matches = list(_CHAPTER.finditer(text))
    if not matches:
        body = text.strip()
        return [ImportedChapter(1, "正文", body)] if body else []
    chapters: list[ImportedChapter] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(2).strip() or match.group(1).strip()
        chapters.append(ImportedChapter(index + 1, title[:200], text[start:end].strip()))
    return chapters


def parse_manuscript(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"txt", "md", ""}:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("gb18030", errors="ignore")
    if suffix == "docx":
        from docx import Document

        document = Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix == "pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    return ""
