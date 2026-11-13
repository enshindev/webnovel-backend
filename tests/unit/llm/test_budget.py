from __future__ import annotations

from webnovel.llm.context.budget import allocate, usable_tokens


def test_usable_tokens_reserves_output_and_safety() -> None:
    assert usable_tokens(window=16_000, max_output=2_000) == 13_200


def test_allocate_sums_to_usable() -> None:
    budgets = allocate(13_200)
    assert sum(budgets.values()) <= 13_200
    assert budgets["recent_text"] > budgets["entities"]
