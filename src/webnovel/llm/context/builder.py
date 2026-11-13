from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from webnovel.kernel.ports.llm import ChatMessage
from webnovel.llm.context.budget import allocate, usable_tokens
from webnovel.llm.context.ports import ContextSegment


@dataclass(frozen=True, slots=True)
class ContextManifest:
    total_tokens: int
    model_window: int
    segments: Sequence[dict[str, Any]] = field(default_factory=tuple)
    cache_prefix_hash: str | None = None
    estimated: bool = True


@dataclass(frozen=True, slots=True)
class BuiltContext:
    messages: Sequence[ChatMessage]
    manifest: ContextManifest


class ContextBuilder:
    """机制：对业务模块已选好的 segments 做预算、渲染、manifest。

    业务选择（人物、设定、伏笔、最近原文）在 modules/<x>/ai/context.py。
    """

    def build(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        segments: Sequence[ContextSegment] = (),
        model_window: int = 16_000,
        max_output: int = 2_000,
    ) -> BuiltContext:
        usable = usable_tokens(model_window, max_output)
        budgets = allocate(usable)
        counts = Counter(segment.name for segment in segments)
        rendered: list[str] = []
        manifest_segments: list[dict[str, Any]] = []
        for segment in segments:
            budget = budgets.get(segment.name, usable) // counts[segment.name]
            text = segment.text
            tokens = segment.tokens or max(1, len(text))
            if budget is not None and tokens > budget > 0:
                keep = max(0, int(len(text) * budget / tokens))
                text = text[:keep]
                tokens = budget
            rendered.append(f"[{segment.name}:{segment.ref}]\n{text}")
            manifest_segments.append(
                {
                    "name": segment.name,
                    "ref": segment.ref,
                    "tokens": tokens,
                    "budget": budget,
                }
            )
        content = "\n\n".join([*rendered, user_prompt])
        return BuiltContext(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=content),
            ],
            manifest=ContextManifest(
                total_tokens=sum(segment.tokens for segment in segments),
                model_window=model_window,
                segments=tuple(manifest_segments),
            ),
        )
