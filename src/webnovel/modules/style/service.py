from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.style.analyzer import compare_features, extract_features
from webnovel.modules.style.contract import StyleCheck, StyleProfile, StyleRewrite, StyleService
from webnovel.modules.style.repository import StyleRepository
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)


class StyleServiceImpl(StyleService):
    def __init__(
        self,
        repository: StyleRepository,
        chapter_service: ChapterService,
        model_client: ModelClient | None = None,
        settings: Settings | None = None,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._usage = usage

    async def create_profile(self, work_id: UUID, chapter_ids: list[UUID]) -> StyleProfile:
        if not 1 <= len(chapter_ids) <= 5:
            raise ValidationError("1-5 chapter samples required", code="style.sample_count")
        texts: list[str] = []
        samples: list[dict[str, object]] = []
        for chapter_id in chapter_ids:
            chapter = await self._chapter_service.get(chapter_id)
            if chapter.work_id != work_id:
                raise ValidationError(
                    "sample chapter belongs to another work", code="style.work_mismatch"
                )
            if chapter.current_version_id is None:
                raise ValidationError("sample chapter is empty", code="style.sample_empty")
            version = await self._chapter_service.get_version(
                chapter.id, chapter.current_version_id
            )
            texts.append(version.content)
            samples.append(
                {
                    "chapter_id": chapter.id,
                    "version_id": version.id,
                    "text": version.content,
                }
            )
        sample_text = "\n\n".join(texts)
        features = extract_features(sample_text)
        summary = _summary(features)
        qualitative: dict[str, Any] = {}
        if self._model_client is not None and self._settings is not None:
            try:
                prompt = PromptRegistry(self._settings.prompts_dir).resolve("style/profile")
                includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
                rendered = render_prompt(prompt, {"sample_text": sample_text}, includes)
                raw = await self._model_client.complete(
                    ModelRequest(
                        model=self._settings.llm_model,
                        messages=[ChatMessage(role="user", content=rendered)],
                        max_tokens=1_200,
                    )
                )
                parsed = _parse_json(raw)
                if isinstance(parsed, dict):
                    qualitative = cast(dict[str, Any], parsed)
                    summary = str(parsed.get("summary") or summary)
                if self._usage is not None:
                    await self._usage.record_llm(
                        work_id=work_id,
                        generation_id=None,
                        provider=self._settings.llm_provider,
                        model=self._settings.llm_model,
                        task_type="style",
                        prompt_tokens=estimate_tokens(rendered),
                        completion_tokens=estimate_tokens(raw),
                        estimated=True,
                    )
            except Exception:
                logger.exception("style.qualitative_failed", work_id=str(work_id))
        return await self._repository.create_profile(
            work_id, features, summary, samples, qualitative=qualitative
        )

    async def get_profile(self, work_id: UUID, profile_id: UUID) -> StyleProfile:
        profile = await self._repository.get_profile(profile_id)
        if profile is None or profile.work_id != work_id:
            raise NotFoundError(f"style profile not found: {profile_id}", code="style.not_found")
        return profile

    async def update_profile(
        self,
        work_id: UUID,
        profile_id: UUID,
        *,
        summary: str | None = None,
        status: str | None = None,
        do_list: list[str] | None = None,
        dont_list: list[str] | None = None,
    ) -> StyleProfile:
        await self.get_profile(work_id, profile_id)
        values: dict[str, object] = {}
        if summary is not None:
            values["summary"] = summary
        if status is not None:
            values["status"] = status
        if do_list is not None:
            values["do_list"] = do_list
        if dont_list is not None:
            values["dont_list"] = dont_list
        updated = await self._repository.update_profile(profile_id, **values)
        if updated is None:
            raise NotFoundError(f"style profile not found: {profile_id}", code="style.not_found")
        return updated

    async def get_active(self, work_id: UUID) -> StyleProfile | None:
        return await self._repository.get_active(work_id)

    async def add_character_sample(
        self, work_id: UUID, profile_id: UUID, character_name: str, text: str
    ) -> None:
        await self.get_profile(work_id, profile_id)
        if not character_name.strip() or not text.strip():
            raise ValidationError(
                "character name and sample required", code="style.character_sample"
            )
        await self._repository.add_sample(profile_id, character_name.strip(), text)

    async def check_character(
        self, work_id: UUID, profile_id: UUID, character_name: str, content: str
    ) -> StyleCheck:
        await self.get_profile(work_id, profile_id)
        sample = await self._repository.get_character_text(profile_id, character_name)
        if sample is None:
            raise NotFoundError(
                f"character sample not found: {character_name}",
                code="style.character_sample_not_found",
            )
        score, dimensions, issues = compare_features(extract_features(sample), content)
        return await self._repository.add_check(work_id, profile_id, score, dimensions, issues)

    async def rewrite(self, work_id: UUID, profile_id: UUID, content: str) -> StyleRewrite:
        profile = await self.get_profile(work_id, profile_id)
        if self._model_client is None or self._settings is None:
            raise ValidationError(
                "style rewrite requires a configured model", code="style.model_required"
            )
        prompt = PromptRegistry(self._settings.prompts_dir).resolve("style/rewrite")
        includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
        rendered = render_prompt(
            prompt,
            {
                "profile_summary": profile.summary,
                "do_list": "; ".join(profile.do_list) or "无",
                "dont_list": "; ".join(profile.dont_list) or "无",
                "content": content,
            },
            includes,
        )
        rewritten = await self._model_client.complete(
            ModelRequest(
                model=self._settings.llm_model,
                messages=[ChatMessage(role="user", content=rendered)],
                max_tokens=2_000,
            )
        )
        check = await self.check(work_id, profile_id, rewritten)
        if self._usage is not None:
            await self._usage.record_llm(
                work_id=work_id,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type="style",
                prompt_tokens=estimate_tokens(rendered),
                completion_tokens=estimate_tokens(rewritten),
                estimated=True,
            )
        return StyleRewrite(content=rewritten, check=check)

    async def check(self, work_id: UUID, profile_id: UUID, content: str) -> StyleCheck:
        profile = await self.get_profile(work_id, profile_id)
        score, dimensions, issues = compare_features(profile.features, content)
        return await self._repository.add_check(work_id, profile_id, score, dimensions, issues)


def _summary(features: dict[str, object]) -> str:
    return (
        f"平均句长 {features['avg_sentence_length']} 字，"
        f"对话段落比 {features['dialogue_ratio']}，"
        f"段落数 {features['paragraph_count']}，"
        f"词汇丰富度 {features['vocabulary_richness']}。"
    )


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        index = cleaned.find("{")
        if index < 0:
            return None
        try:
            return json.loads(cleaned[index:])
        except json.JSONDecodeError:
            return None
