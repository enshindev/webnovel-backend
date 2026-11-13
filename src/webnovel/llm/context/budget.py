from __future__ import annotations

from collections.abc import Mapping

# 架构文档的六段预算；业务模块可覆盖，但平台提供默认值。
DEFAULT_RATIOS: Mapping[str, int] = {
    "system": 5,
    "task": 10,
    "entities": 20,
    "foreshadow_summary": 20,
    "recent_text": 40,
    "instruction": 5,
    "memory": 20,
    "style": 10,
}


def usable_tokens(window: int, max_output: int, *, safety_ratio: float = 0.05) -> int:
    reserve = max(0, int(window * safety_ratio))
    return max(0, window - max_output - reserve)


def allocate(usable: int, ratios: Mapping[str, int] = DEFAULT_RATIOS) -> dict[str, int]:
    total = sum(ratios.values())
    if total <= 0:
        return {}
    return {name: usable * value // total for name, value in ratios.items()}
