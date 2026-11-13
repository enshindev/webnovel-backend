from __future__ import annotations

from webnovel.modules.analysis.importing import split_chapters


def test_split_chapters() -> None:
    chapters = split_chapters("第一章 雨夜\n正文一\n第二章 灯灭\n正文二")
    assert [chapter.number for chapter in chapters] == [1, 2]
    assert chapters[0].title == "雨夜"
    assert "正文二" in chapters[1].content
