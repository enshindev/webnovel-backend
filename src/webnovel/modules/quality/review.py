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
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.quality.contract import QualityIssue
from webnovel.modules.quality.repository import QualityRepository
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)


class QualityReviewRunner:
    def __init__(
        self,
        *,
        repository: QualityRepository,
        chapter_service: ChapterService,
        model_client: ModelClient,
        settings: Settings,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._usage = usage

    async def run(self, report_id: UUID) -> None:
        report = await self._repository.get(report_id)
        if report is None or report.status != "queued":
            return
        try:
            version = await self._chapter_service.get_version(report.chapter_id, report.version_id)
            prompt = PromptRegistry(self._settings.prompts_dir).resolve("quality/review")
            includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
            rendered = render_prompt(prompt, {"chapter_text": version.content}, includes)
            raw_result = await self._model_client.complete(
                ModelRequest(
                    model=self._settings.llm_model,
                    messages=[ChatMessage(role="user", content=rendered)],
                    max_tokens=1_500,
                )
            )
            result = _parse_json(raw_result)
            score, issues = _parse_review(result)
            await self._repository.save_review(
                report.id,
                status="warning" if issues else "passed",
                score=score,
                metrics={"issue_count": len(issues), "model": self._settings.llm_model},
                issues=issues,
            )
            await self._record_usage(report.work_id, rendered, raw_result)
            logger.info("quality.review_succeeded", report_id=str(report.id))
        except Exception as exc:
            logger.exception("quality.review_failed", report_id=str(report.id))
            await self._repository.save_review(
                report.id,
                status="failed",
                score=0,
                metrics={"error": str(exc)},
                issues=[
                    QualityIssue(
                        code="review.failed",
                        severity="P0",
                        message=f"审稿失败：{exc}",
                    )
                ],
            )

    async def _record_usage(self, work_id: UUID, prompt_text: str, completion_text: str) -> None:
        if self._usage is None:
            return
        try:
            await self._usage.record_llm(
                work_id=work_id,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type="quality",
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens(completion_text),
                estimated=True,
            )
        except Exception:
            logger.exception("quality.usage_failed", work_id=str(work_id))


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        index = cleaned.find("{")
        if index < 0:
            raise
        return json.loads(cleaned[index:])


def _parse_review(payload: Any) -> tuple[int, list[QualityIssue]]:
    data = cast(dict[str, Any], payload)
    score = max(0, min(100, int(data.get("score", 0))))
    issues: list[QualityIssue] = []
    for raw in cast(list[Any], data.get("issues", [])):
        item = cast(dict[str, Any], raw)
        severity = str(item.get("severity", "P2"))
        if severity not in {"P0", "P1", "P2"}:
            severity = "P2"
        issues.append(
            QualityIssue(
                code=str(item.get("type", "review.issue")),
                severity=severity,
                message=str(item.get("detail", "")),
                location=cast(dict[str, Any] | None, item.get("location")),
                suggestion=str(item.get("suggestion", "")) or None,
            )
        )
    return score, issues
