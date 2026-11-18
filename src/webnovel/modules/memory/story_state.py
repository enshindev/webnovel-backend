from __future__ import annotations

from collections import defaultdict
from itertools import pairwise
from typing import Any

from webnovel.modules.memory.contract import Contradiction, StoryEvent


def detect_contradictions(events: list[StoryEvent]) -> list[Contradiction]:
    """确定性检查：同章状态冲突，以及跨章前值不连续、知识倒退。"""
    knowledge: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    entity_states: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    knowledge_history: dict[tuple[str, str], list[tuple[int, str, str]]] = defaultdict(list)
    entity_history: dict[tuple[str, str], str] = {}
    contradictions: list[Contradiction] = []
    by_chapter: dict[int, list[StoryEvent]] = defaultdict(list)
    for event in events:
        by_chapter[event.chapter_number].append(event)
        changes = event.changes or {}
        for item in changes.get("knowledge_changes", []) or []:
            if not isinstance(item, dict):
                continue
            character = str(item.get("character_name", "")).strip()
            fact_key = str(item.get("fact_key", "")).strip()
            state = str(item.get("state", "")).strip()
            if character and fact_key:
                knowledge[(event.chapter_number, character, fact_key)].append(
                    {"state": state, "event_id": str(event.id), "summary": event.summary}
                )
                knowledge_history[(character, fact_key)].append(
                    (event.chapter_number, state, str(event.id))
                )
        for item in changes.get("entity_changes", []) or []:
            if not isinstance(item, dict):
                continue
            entity = str(item.get("entity_name") or item.get("entity") or "").strip()
            field = str(item.get("field", "")).strip()
            after = item.get("after")
            if isinstance(after, dict):
                after = after.get("value")
            before = item.get("before")
            if isinstance(before, dict):
                before = before.get("value")
            if entity and field in {"location", "holder"} and after:
                entity_states[(event.chapter_number, entity, field)].append(
                    {"after": str(after), "event_id": str(event.id), "summary": event.summary}
                )
                previous = entity_history.get((entity, field))
                if before is not None and previous is not None and str(before) != previous:
                    contradictions.append(
                        Contradiction(
                            kind="entity.state_sequence",
                            severity="P2",
                            message=(
                                f"第 {event.chapter_number} 章：{entity} 的 {field} "
                                f"前值「{before}」与上一状态「{previous}」不一致"
                            ),
                            chapter_number=event.chapter_number,
                            evidence=[
                                {
                                    "before": str(before),
                                    "previous": previous,
                                    "event_id": str(event.id),
                                    "summary": event.summary,
                                }
                            ],
                        )
                    )
                entity_history[(entity, field)] = str(after)

    for (chapter, character, fact_key), states in knowledge.items():
        values = {item["state"] for item in states}
        if "knows" in values and "does_not_know" in values:
            contradictions.append(
                Contradiction(
                    kind="knowledge.conflict",
                    severity="P1",
                    message=f"第 {chapter} 章：{character} 对「{fact_key}」同时出现知道和不知道",
                    chapter_number=chapter,
                    evidence=states,
                )
            )
    for (character, fact_key), history in knowledge_history.items():
        history.sort(key=lambda item: item[0])
        for previous_item, next_item in pairwise(history):
            if (
                next_item[0] != previous_item[0]
                and previous_item[1] in {"knows", "suspects"}
                and next_item[1] == "does_not_know"
            ):
                contradictions.append(
                    Contradiction(
                        kind="knowledge.regression",
                        severity="P2",
                        message=(
                            f"第 {next_item[0]} 章：{character} 对「{fact_key}」"
                            "从知道/怀疑退回不知道，且没有 corrected 标记"
                        ),
                        chapter_number=next_item[0],
                        evidence=[
                            {"chapter": previous_item[0], "state": previous_item[1]},
                            {"chapter": next_item[0], "state": next_item[1]},
                        ],
                    )
                )
    for (chapter, entity, field), states in entity_states.items():
        values = {item["after"] for item in states}
        if len(values) > 1:
            contradictions.append(
                Contradiction(
                    kind="entity.state_conflict",
                    severity="P2",
                    message=(
                        f"第 {chapter} 章：{entity} 的 {field} 同时出现 "
                        + "、".join(sorted(values))
                    ),
                    chapter_number=chapter,
                    evidence=states,
                )
            )
    contradictions.sort(key=lambda item: (item.chapter_number, item.kind, item.message))
    return contradictions
