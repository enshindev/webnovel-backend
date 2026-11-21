from __future__ import annotations

import hashlib
import json
from typing import Any, cast
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.kernel.errors import WebnovelError
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.prompts.schema import PromptSpec
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.memory.contract import ExtractionStatus, MemoryIndexer
from webnovel.modules.memory.repository import MemoryRepository
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)
_EXTRACTION_STEPS = 3


def parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        if not starts:
            raise
        return json.loads(cleaned[min(starts) :])


class ExtractionRunner:
    def __init__(
        self,
        *,
        repository: MemoryRepository,
        chapter_service: ChapterService,
        model_client: ModelClient,
        settings: Settings,
        indexer: MemoryIndexer | None = None,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._indexer = indexer
        self._usage = usage

    async def run(self, run_id: UUID) -> None:
        run = await self._repository.get_run(run_id)
        if run is None:
            return
        await self._repository.set_run_status(run.id, ExtractionStatus.RUNNING)
        try:
            chapter = await self._chapter_service.get(run.chapter_id)
            version = await self._chapter_service.get_version(run.chapter_id, run.version_id)
            text = version.content
        except WebnovelError as exc:
            await self._repository.set_run_status(run.id, ExtractionStatus.FAILED, str(exc))
            return

        if self._indexer is not None:
            try:
                await self._indexer.index_chapter(run.work_id, run.chapter_id, run.version_id, text)
            except Exception:
                logger.exception("extraction.chapter_index_failed", run_id=str(run.id))

        errors: list[str] = []
        await self._run_summary(run.id, run.work_id, run.chapter_id, run.version_id, text, errors)
        await self._run_entities(run.id, run.work_id, run.chapter_id, text, errors)
        await self._run_events(
            run.id, run.work_id, run.chapter_id, run.version_id, chapter.number, text, errors
        )

        if len(errors) == _EXTRACTION_STEPS:
            status = ExtractionStatus.FAILED
        elif errors:
            status = ExtractionStatus.PARTIAL
        else:
            status = ExtractionStatus.SUCCEEDED
        await self._repository.set_run_status(run.id, status, "; ".join(errors) or None)
        logger.info(
            "extraction.finished",
            run_id=str(run.id),
            status=status.value,
            errors=len(errors),
        )

    async def _run_summary(
        self,
        run_id: UUID,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        text: str,
        errors: list[str],
    ) -> None:
        step_id = await self._repository.create_step(run_id, "summary")
        try:
            prompt = self._prompt("memory/summary")
            includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
            rendered = render_prompt(prompt, {"chapter_text": text}, includes)
            raw_result = await self._model_client.complete(self._request(rendered, max_tokens=800))
            result = parse_json(raw_result)
            summary = str(cast(dict[str, Any], result).get("summary", "")).strip()
            if not summary:
                raise ValueError("summary is empty")
            saved = await self._repository.save_summary(
                work_id=work_id,
                chapter_id=chapter_id,
                version_id=version_id,
                content=summary,
                content_hash=hashlib.sha256(summary.encode("utf-8")).hexdigest(),
                model=self._settings.llm_model,
                prompt_version=prompt.version,
            )
            if self._indexer is not None:
                try:
                    await self._indexer.index_summary(saved)
                except Exception:
                    logger.exception("extraction.summary_index_failed", run_id=str(run_id))
            await self._record_usage(work_id, "summary", rendered, raw_result)
            await self._repository.finish_step(
                step_id,
                "succeeded",
                model=self._settings.llm_model,
                prompt_version=prompt.version,
            )
        except Exception as exc:
            logger.exception("extraction.summary_failed", run_id=str(run_id))
            await self._repository.finish_step(step_id, "failed", error=str(exc))
            errors.append(f"summary: {exc}")

    async def _run_entities(
        self,
        run_id: UUID,
        work_id: UUID,
        chapter_id: UUID,
        text: str,
        errors: list[str],
    ) -> None:
        step_id = await self._repository.create_step(run_id, "entities")
        try:
            prompt = self._prompt("memory/entity")
            includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
            rendered = render_prompt(prompt, {"chapter_text": text}, includes)
            raw_result = await self._model_client.complete(
                self._request(rendered, max_tokens=1_200)
            )
            result = parse_json(raw_result)
            raw_entities = (
                result
                if isinstance(result, list)
                else cast(dict[str, Any], result).get("entities", [])
            )
            if not isinstance(raw_entities, list):
                raise ValueError("entities must be a list")
            for item in raw_entities:
                proposal = self._entity_payload(item)
                existing = await self._repository.find_entity(
                    work_id,
                    str(proposal["type"]),
                    str(proposal["name"]),
                    [str(alias) for alias in cast(list[Any], proposal["aliases"])],
                )
                kind = "entity_create"
                target_id: UUID | None = None
                base_version: int | None = None
                before: dict[str, Any] | None = None
                if existing is not None:
                    kind = "entity_update"
                    target_id = existing.id
                    base_version = existing.version
                    before = {
                        "type": existing.type,
                        "name": existing.name,
                        "aliases": list(existing.aliases),
                        "attributes": dict(existing.attributes),
                    }
                    proposal = {
                        **proposal,
                        "name": existing.name,
                        "aliases": list(dict.fromkeys([*existing.aliases, *proposal["aliases"]])),
                        "attributes": {**existing.attributes, **proposal["attributes"]},
                    }
                await self._repository.add_proposal(
                    work_id=work_id,
                    run_id=run_id,
                    step_id=step_id,
                    kind=kind,
                    after=proposal,
                    confidence=self._confidence(item),
                    source_span={"quote": str(cast(dict[str, Any], item).get("quote", ""))},
                    target_entity_id=target_id,
                    base_entity_version=base_version,
                    before=before,
                )
            await self._record_usage(work_id, "extraction", rendered, raw_result)
            await self._repository.finish_step(
                step_id,
                "succeeded",
                model=self._settings.llm_model,
                prompt_version=prompt.version,
            )
        except Exception as exc:
            logger.exception("extraction.entity_failed", run_id=str(run_id))
            await self._repository.finish_step(step_id, "failed", error=str(exc))
            errors.append(f"entities: {exc}")

    async def _run_events(
        self,
        run_id: UUID,
        work_id: UUID,
        chapter_id: UUID,
        version_id: UUID,
        chapter_number: int,
        text: str,
        errors: list[str],
    ) -> None:
        step_id = await self._repository.create_step(run_id, "event")
        try:
            prompt = self._prompt("memory/event")
            includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
            rendered = render_prompt(prompt, {"chapter_text": text}, includes)
            raw_result = await self._model_client.complete(
                self._request(rendered, max_tokens=1_800)
            )
            result = parse_json(raw_result)
            raw_events = (
                result
                if isinstance(result, list)
                else cast(dict[str, Any], result).get("events", [])
            )
            if not isinstance(raw_events, list):
                raise ValueError("events must be a list")
            entities = await self._repository.list_entities(work_id, limit=500)
            entity_map: dict[str, UUID] = {}
            for entity in entities:
                entity_map[entity.name.casefold()] = entity.id
                for alias in entity.aliases:
                    entity_map[alias.casefold()] = entity.id
            events = [
                await self._event_payload(work_id, cast(dict[str, Any], item), entity_map)
                for item in raw_events
            ]
            await self._repository.replace_story_events(
                work_id, chapter_id, version_id, chapter_number, events, run_id=run_id
            )
            await self._record_usage(work_id, "event", rendered, raw_result)
            await self._repository.finish_step(
                step_id,
                "succeeded",
                model=self._settings.llm_model,
                prompt_version=prompt.version,
            )
        except Exception as exc:
            logger.exception("extraction.event_failed", run_id=str(run_id))
            await self._repository.finish_step(step_id, "failed", error=str(exc))
            errors.append(f"event: {exc}")

    async def _event_payload(
        self,
        work_id: UUID,
        item: dict[str, Any],
        entity_map: dict[str, UUID] | None = None,
    ) -> dict[str, Any]:
        summary = str(item.get("summary", "")).strip()
        if not summary:
            raise ValueError("event requires summary")
        participants = item.get("participants", [])
        changes = item.get("knowledge_changes", [])
        entity_changes = item.get("entity_changes", [])
        if not isinstance(participants, list) or not isinstance(changes, list):
            raise ValueError("invalid participants/knowledge_changes")
        if not isinstance(entity_changes, list):
            raise ValueError("invalid entity_changes")

        knowledge_changes: list[dict[str, Any]] = []
        for change in changes:
            change = cast(dict[str, Any], change)
            character = str(change.get("character", "")).strip()
            fact = str(change.get("fact", "")).strip()
            state = str(change.get("state", "knows")).strip()
            if not character or not fact:
                continue
            if state not in {"knows", "suspects", "does_not_know"}:
                state = "knows"
            entity = await self._repository.find_entity(work_id, "character", character, [])
            knowledge_changes.append(
                {
                    "character_id": str(entity.id) if entity is not None else None,
                    "character_name": character,
                    "fact_key": fact.casefold(),
                    "fact_value": {"text": fact},
                    "state": state,
                }
            )
        normalized_entity_changes: list[dict[str, Any]] = []
        for change in entity_changes:
            change = cast(dict[str, Any], change)
            entity_name = str(change.get("entity", "")).strip()
            field = str(change.get("field", "")).strip()
            if not entity_name or not field:
                continue
            normalized_entity_changes.append(
                {
                    "entity_id": str((entity_map or {}).get(entity_name.casefold(), "")),
                    "entity_name": entity_name,
                    "field": field,
                    "before": {"value": change.get("before")},
                    "after": {"value": change.get("after")},
                }
            )
        return {
            "index": int(item.get("index", 0)),
            "summary": summary,
            "time_text": str(item.get("time_text")).strip() if item.get("time_text") else None,
            "location": str(item.get("location")).strip() if item.get("location") else None,
            "participants": participants,
            "knowledge_changes": knowledge_changes,
            "entity_changes": normalized_entity_changes,
            "source_span": {"quote": str(item.get("quote", ""))},
            "confidence": self._confidence(item),
        }

    async def _record_usage(
        self, work_id: UUID, task_type: str, prompt_text: str, completion_text: str
    ) -> None:
        if self._usage is None:
            return
        try:
            await self._usage.record_llm(
                work_id=work_id,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type=task_type,
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens(completion_text),
                estimated=True,
            )
        except Exception:
            logger.exception("extraction.usage_failed", work_id=str(work_id))

    def _prompt(self, key: str) -> PromptSpec:
        return PromptRegistry(self._settings.prompts_dir).resolve(key)

    def _request(self, rendered: str, *, max_tokens: int) -> ModelRequest:
        return ModelRequest(
            model=self._settings.llm_model,
            messages=[ChatMessage(role="user", content=rendered)],
            max_tokens=max_tokens,
        )

    @staticmethod
    def _entity_payload(item: Any) -> dict[str, Any]:
        data = cast(dict[str, Any], item)
        entity_type = str(data.get("type", "")).strip()
        name = str(data.get("name", "")).strip()
        if not entity_type or not name:
            raise ValueError("entity requires type and name")
        aliases = data.get("aliases", [])
        attributes = data.get("attributes", {})
        if not isinstance(aliases, list) or not isinstance(attributes, dict):
            raise ValueError("invalid aliases/attributes")
        return {
            "type": entity_type,
            "name": name,
            "aliases": [str(alias) for alias in aliases],
            "attributes": cast(dict[str, Any], attributes),
        }

    @staticmethod
    def _confidence(item: Any) -> float | None:
        raw = cast(dict[str, Any], item).get("confidence")
        if raw is None:
            return None
        return float(raw)
