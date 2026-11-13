from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from webnovel.modules.quality.contract import QualityIssue
from webnovel.modules.quality.rules import PlatformRules

AI_SIGNALS = (
    "然而",
    "不禁",
    "仿佛",
    "似乎",
    "与此同时",
    "深吸一口气",
    "嘴角",
    "眼底",
    "缓缓",
    "微微",
)

_SENTENCE_SPLIT = re.compile(r"[。！？!?]+")


@dataclass(frozen=True, slots=True)
class MachineResult:
    status: str
    score: int
    issues: list[QualityIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def check_chapter(
    content: str,
    *,
    chapter_numbers: list[int],
    rules: PlatformRules | None = None,
) -> MachineResult:
    rules = rules or PlatformRules()
    text = content.strip()
    issues: list[QualityIssue] = []
    word_count = len(text)

    if not text:
        issues.append(
            QualityIssue(
                code="format.empty",
                severity="P0",
                message="章节正文为空",
            )
        )
    elif word_count < rules.thin_words:
        issues.append(
            QualityIssue(
                code="word_count.thin",
                severity="P1",
                message=f"章节偏薄：{word_count} 字，建议至少 {rules.thin_words} 字",
                location={"word_count": word_count},
            )
        )
    elif word_count < rules.min_words:
        issues.append(
            QualityIssue(
                code="word_count.below_min",
                severity="P2",
                message=f"低于平台参考下限：{word_count} < {rules.min_words}",
                location={"word_count": word_count},
            )
        )
    elif word_count > rules.max_words:
        issues.append(
            QualityIssue(
                code="word_count.above_max",
                severity="P2",
                message=f"高于平台参考上限：{word_count} > {rules.max_words}",
                location={"word_count": word_count},
            )
        )

    max_number = max(chapter_numbers, default=0)
    present = set(chapter_numbers)
    missing = [number for number in range(1, max_number + 1) if number not in present]
    if missing:
        issues.append(
            QualityIssue(
                code="chapter.missing",
                severity="P1",
                message=f"缺少章节：{missing[:20]}",
                location={"missing": missing},
            )
        )

    paragraphs = [line for line in text.splitlines() if line.strip()]
    if "\n\n\n" in text:
        issues.append(
            QualityIssue(
                code="format.blank_lines",
                severity="P2",
                message="存在连续空行",
            )
        )
    if any(line.rstrip() != line for line in text.splitlines()):
        issues.append(
            QualityIssue(
                code="format.trailing_spaces",
                severity="P2",
                message="存在行尾空格",
            )
        )
    if re.search(r"^#{1,6}\s", text, re.MULTILINE):
        issues.append(
            QualityIssue(
                code="format.markdown_heading",
                severity="P2",
                message="正文包含 Markdown 标题",
            )
        )

    signal_count = sum(text.count(signal) for signal in AI_SIGNALS)
    density = signal_count / max(1, word_count) * 1_000
    if density > 6:
        issues.append(
            QualityIssue(
                code="ai_flavor.signal_density",
                severity="P1",
                message=f"AI 味信号偏密：{density:.1f}/千字",
                location={"signals": signal_count},
            )
        )

    sentences = [part for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    avg_sentence = word_count / max(1, len(sentences))
    dialogue_ratio = text.count("“") / max(1, len(paragraphs))

    score = 100 - sum({"P0": 35, "P1": 12, "P2": 4}.get(issue.severity, 2) for issue in issues)
    score = max(0, min(100, score))
    if any(issue.severity == "P0" for issue in issues):
        status = "failed"
    elif any(issue.severity == "P1" for issue in issues):
        status = "warning"
    else:
        status = "passed"

    return MachineResult(
        status=status,
        score=score,
        issues=issues,
        metrics={
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sentence, 2),
            "dialogue_paragraph_ratio": round(dialogue_ratio, 3),
            "ai_signal_count": signal_count,
            "ai_signal_density": round(density, 2),
        },
    )
