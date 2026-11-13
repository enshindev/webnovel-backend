from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from webnovel.modules.chapters_versions.contract import Chapter
from webnovel.modules.export.render import render_docx, render_txt


def test_render_txt_contains_chapter_and_disclosure() -> None:
    now = datetime.now(UTC)
    chapter = Chapter(
        id=uuid4(),
        work_id=uuid4(),
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=2,
        created_at=now,
        updated_at=now,
    )
    text = render_txt(
        work_title="长夜灯火",
        chapters=[chapter],
        contents=["正文"],
        disclosure="AI 使用说明",
    )
    assert "《长夜灯火》" in text
    assert "第1章 雨夜" in text
    assert "正文" in text
    assert "AI 使用说明" in text


def test_render_docx(tmp_path) -> None:
    pytest.importorskip("docx")
    from docx import Document

    now = datetime.now(UTC)
    chapter = Chapter(
        id=uuid4(),
        work_id=uuid4(),
        number=1,
        title="雨夜",
        current_version_id=uuid4(),
        lock_version=1,
        word_count=2,
        created_at=now,
        updated_at=now,
    )
    path = tmp_path / "out.docx"
    render_docx(
        path=str(path),
        work_title="长夜灯火",
        chapters=[chapter],
        contents=["正文"],
        disclosure="AI 使用说明",
    )
    document = Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "第1章 雨夜" in text
    assert "AI 使用说明" in text
