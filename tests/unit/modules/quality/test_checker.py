from __future__ import annotations

from webnovel.modules.quality.checker import check_chapter
from webnovel.modules.quality.rules import PlatformRules


def test_good_chapter_passes() -> None:
    result = check_chapter("正文。" * 800, chapter_numbers=[1])
    assert result.status == "passed"
    assert result.score == 100


def test_empty_chapter_fails() -> None:
    result = check_chapter("", chapter_numbers=[1])
    assert result.status == "failed"
    assert result.issues[0].code == "format.empty"


def test_thin_chapter_warns() -> None:
    result = check_chapter("短" * 500, chapter_numbers=[1])
    assert result.status == "warning"
    assert any(issue.code == "word_count.thin" for issue in result.issues)


def test_missing_chapters_are_reported() -> None:
    result = check_chapter("正文。" * 800, chapter_numbers=[1, 3])
    assert any(issue.code == "chapter.missing" for issue in result.issues)


def test_ai_signal_density_warns() -> None:
    text = "然而，他缓缓抬头。" * 200
    result = check_chapter(text, chapter_numbers=[1], rules=PlatformRules(min_words=100))
    assert any(issue.code == "ai_flavor.signal_density" for issue in result.issues)
