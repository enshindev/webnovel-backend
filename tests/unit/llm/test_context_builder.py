from __future__ import annotations

from webnovel.llm.context.builder import ContextBuilder
from webnovel.llm.context.ports import ContextSegment


def test_context_builder_truncates_segment_to_budget() -> None:
    long_text = "记" * 10_000
    context = ContextBuilder().build(
        system_prompt="system",
        user_prompt="continue",
        segments=[
            ContextSegment(name="memory", source="summary", ref="s1", text=long_text, tokens=10_000)
        ],
        model_window=1_000,
        max_output=100,
    )
    content = context.messages[-1].content
    assert len(content) < 1_000
    assert context.manifest.total_tokens <= 10_000
