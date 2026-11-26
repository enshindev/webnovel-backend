from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.analysis.repository import AnalysisRepository
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)


class AnalysisRunner:
    def __init__(
        self,
        *,
        repository: AnalysisRepository,
        chapter_service: ChapterService,
        model_client: ModelClient | None,
        settings: Settings,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._usage = usage

    async def run(self, run_id: UUID) -> None:
        run = await self._repository.get_run(run_id)
        if run is None or run.status != "queued":
            return
        await self._repository.set_status(run.id, "extracting")
        await self._repository.clear_chapters(run.id)
        chapters = await self._chapter_service.list(run.work_id)
        chapter_range = run.params.get("chapter_range") or {}
        start = int(chapter_range.get("start", 0) or 0)
        end = int(chapter_range.get("end", 10**9) or 10**9)
        selected = [chapter for chapter in chapters if start <= chapter.number <= end]
        results: list[dict[str, Any]] = []
        try:
            for chapter in selected:
                if chapter.current_version_id is None:
                    results.append(
                        {
                            "chapter": chapter.number,
                            "title": chapter.title,
                            "word_count": 0,
                            "summary": "",
                            "issues": [{"type": "empty_chapter", "severity": "P1"}],
                        }
                    )
                    continue
                version = await self._chapter_service.get_version(
                    chapter.id, chapter.current_version_id
                )
                extracted = await self._extract(version.content)
                extracted["boundary_confidence"] = min(
                    1.0, len(extracted.get("beats", [])) / max(1, len(selected))
                )
                extracted["status"] = "needs_review" if extracted.get("issues") else "ready"
                extracted["progress"] = 100
                await self._repository.add_chapter(
                    run.id,
                    {
                        "chapter_id": chapter.id,
                        "version_id": version.id,
                        **extracted,
                    },
                )
                results.append(
                    {
                        "chapter": chapter.number,
                        "title": chapter.title,
                        "word_count": len(version.content),
                        **extracted,
                    }
                )
            report = {
                "chapter_range": chapter_range,
                "chapter_count": len(selected),
                "total_words": sum(item["word_count"] for item in results),
                "chapters": results,
                "warnings": [item["chapter"] for item in results if item.get("issues")],
            }
            await self._repository.set_status(run.id, "ready", report=report)
            logger.info("analysis.ready", run_id=str(run.id), chapters=len(selected))
        except Exception as exc:
            logger.exception("analysis.failed", run_id=str(run.id))
            await self._repository.set_status(run.id, "failed", error=str(exc))

    async def _extract(self, content: str) -> dict[str, Any]:
        if self._model_client is None or self._settings is None:
            return {
                "summary": content.strip()[:200],
                "beats": [],
                "pov": None,
                "time_text": None,
                "characters": [],
                "hook": None,
                "hook_type": None,
                "issues": [],
            }
        prompt = PromptRegistry(self._settings.prompts_dir).resolve("analysis/chapter")
        includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
        rendered = render_prompt(prompt, {"chapter_text": content[:12_000]}, includes)
        raw = await self._model_client.complete(
            ModelRequest(
                model=self._settings.llm_model,
                messages=[ChatMessage(role="user", content=rendered)],
                max_tokens=1_200,
            )
        )
        if self._usage is not None:
            await self._usage.record_llm(
                work_id=None,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type="analysis",
                prompt_tokens=estimate_tokens(rendered),
                completion_tokens=estimate_tokens(raw),
                estimated=True,
            )
        try:
            value = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            value = {}
        data = cast(dict[str, Any], value) if isinstance(value, dict) else {}
        return {
            "summary": str(data.get("summary", ""))[:200],
            "beats": data.get("beats", []),
            "pov": data.get("pov"),
            "time_text": data.get("time_text"),
            "characters": data.get("characters", []),
            "hook": data.get("hook"),
            "hook_type": data.get("hook_type"),
            "issues": data.get("issues", []),
        }
