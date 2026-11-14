from __future__ import annotations

from collections import defaultdict
from typing import Any

from webnovel.modules.memory.contract import Contradiction, StoryEvent


def detect_contradictions(events: list[StoryEvent]) -> list[Contradiction]:
    """确定性检查，优先低误报；只处理同一章内互相冲突的状态。"""
    knowledge: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    entity_states: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
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
        for item in changes.get("entity_changes", []) or []:
            if not isinstance(item, dict):
                continue
            entity = str(item.get("entity", "")).strip()
            field = str(item.get("field", "")).strip()
            after = item.get("after")
            if entity and field in {"location", "holder"} and after:
                entity_states[(event.chapter_number, entity, field)].append(
                    {"after": str(after), "event_id": str(event.id), "summary": event.summary}
                )

    contradictions: list[Contradiction] = []
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
