from __future__ import annotations

import time
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.infra.streams import StreamBuffer
from webnovel.kernel.ports.llm import ModelClient, ModelRequest, ModelUsage
from webnovel.llm.context.builder import ContextBuilder
from webnovel.llm.context.ports import ContextSegment
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.generation.contract import DraftStatus, Generation, GenerationStatus
from webnovel.modules.generation.repository import GenerationRepository
from webnovel.modules.memory.contract import MemoryRetrievalService
from webnovel.modules.style.contract import StyleProfileReader
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "你是中文网文作者。只输出章节正文，不解释、不总结。承接上文语气与人物状态，不自动推进大剧情。"
)


class GenerationRunner:
    def __init__(
        self,
        *,
        repository: GenerationRepository,
        chapter_service: ChapterService,
        model_client: ModelClient,
        settings: Settings,
        buffer: StreamBuffer | None = None,
        retrieval: MemoryRetrievalService | None = None,
        style_reader: StyleProfileReader | None = None,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._buffer = buffer
        self._retrieval = retrieval
        self._style_reader = style_reader
        self._usage = usage

    async def run(self, generation_id: UUID) -> None:
        generation = await self._repository.claim(generation_id)
        if generation is None:
            logger.info("generation.skip", generation_id=str(generation_id))
            return
        draft_id = generation.draft_id
        if draft_id is None:
            await self._repository.finish(
                generation.id, GenerationStatus.FAILED, DraftStatus.PARTIAL
            )
            await self._record_usage(
                generation,
                locals().get("prompt_text", ""),
                "".join(locals().get("generated", [])),
                locals().get("final_usage", ModelUsage()),
            )
            return

        try:
            chapter = await self._chapter_service.get(generation.chapter_id)
            recent_text = ""
            if chapter.current_version_id is not None:
                version = await self._chapter_service.get_version(
                    chapter.id, chapter.current_version_id
                )
                recent_text = version.content[-1_200:]

            registry = PromptRegistry(self._settings.prompts_dir)
            prompt = registry.resolve("generation/continuation")
            rendered_prompt = render_prompt(
                prompt,
                {
                    "chapter_outline": f"第{chapter.number}章 {chapter.title}",
                    "recent_text": recent_text,
                    "instruction": generation.instruction
                    or "续写本章，承接上文，不自动推进大剧情。",
                },
                registry.load_includes(prompt),
            )
            await self._repository.record_prompt(
                generation.id, prompt.id, prompt.version, prompt.model_dump(mode="json")
            )
            logger.info(
                "generation.prompt",
                generation_id=str(generation.id),
                prompt_id=prompt.id,
                prompt_version=prompt.version,
            )
            segments = await self._retrieve_segments(
                generation.work_id,
                f"{chapter.title}\n{generation.instruction or ''}",
            )
            style_segment = await self._style_segment(generation.work_id)
            if style_segment is not None:
                segments.append(style_segment)
            context = ContextBuilder().build(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=rendered_prompt,
                segments=segments,
                model_window=self._settings.context_max_tokens,
                max_output=self._max_tokens(generation.target_words),
            )
            await self._repository.record_context(
                generation.id,
                {
                    "messages": [
                        {"role": message.role, "content": message.content}
                        for message in context.messages
                    ],
                    "manifest": {
                        "total_tokens": context.manifest.total_tokens,
                        "model_window": context.manifest.model_window,
                        "segments": list(context.manifest.segments),
                        "cache_prefix_hash": context.manifest.cache_prefix_hash,
                        "estimated": context.manifest.estimated,
                    },
                },
            )
            request = ModelRequest(
                model=self._settings.llm_model,
                messages=context.messages,
                max_tokens=self._max_tokens(generation.target_words),
            )
            first_delta = True
            cancelled = False
            chunk_count = 0
            pending: list[str] = []
            generated: list[str] = []
            final_usage = ModelUsage()
            prompt_text = "".join(message.content for message in context.messages)
            last_checkpoint = time.monotonic()
            async for event in self._model_client.stream(request):
                if event.type == "error":
                    raise RuntimeError(f"model error: {event.error_class}: {event.error_code_raw}")
                if event.type != "delta" or not event.text:
                    continue
                if first_delta:
                    await self._repository.mark_streaming(generation.id)
                    first_delta = False
                pending.append(event.text)
                chunk_count += 1
                if self._buffer is not None:
                    await self._buffer.append(str(generation.id), event.text)
                if len(pending) >= 64 or time.monotonic() - last_checkpoint >= 2.0:
                    await self._repository.append_draft(draft_id, "".join(pending))
                    pending.clear()
                    last_checkpoint = time.monotonic()
                if chunk_count % 32 == 0:
                    current = await self._repository.get(generation.id)
                    if current is not None and current.status in {
                        GenerationStatus.CANCELLING,
                        GenerationStatus.CANCELLED,
                    }:
                        cancelled = True
                        break

            if pending:
                await self._repository.append_draft(draft_id, "".join(pending))
            if cancelled:
                await self._repository.finish(
                    generation.id, GenerationStatus.CANCELLED, DraftStatus.PARTIAL
                )
                await self._record_usage(generation, prompt_text, "".join(generated), final_usage)
                logger.info("generation.cancelled", generation_id=str(generation.id))
                return
            await self._repository.finish(
                generation.id, GenerationStatus.SUCCEEDED, DraftStatus.READY
            )
            await self._record_usage(generation, prompt_text, "".join(generated), final_usage)
            logger.info("generation.succeeded", generation_id=str(generation.id))
        except Exception:
            logger.exception("generation.failed", generation_id=str(generation.id))
            if "pending" in locals() and pending:
                await self._repository.append_draft(draft_id, "".join(pending))
            await self._repository.finish(
                generation.id, GenerationStatus.FAILED, DraftStatus.PARTIAL
            )
            await self._record_usage(
                generation,
                locals().get("prompt_text", ""),
                "".join(locals().get("generated", [])),
                locals().get("final_usage", ModelUsage()),
            )

    async def _record_usage(
        self,
        generation: Generation,
        prompt_text: str,
        completion_text: str,
        usage: ModelUsage,
    ) -> None:
        if self._usage is None:
            return
        final = usage
        if final.prompt_tokens == 0 and final.completion_tokens == 0:
            final = ModelUsage(
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens(completion_text),
                estimated=True,
            )
        try:
            await self._usage.record_llm(
                work_id=generation.work_id,
                generation_id=generation.id,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type=generation.task_type.value,
                prompt_tokens=final.prompt_tokens,
                completion_tokens=final.completion_tokens,
                cached_tokens=final.cached_tokens,
                estimated=final.estimated,
            )
        except Exception:
            logger.exception("generation.usage_failed", generation_id=str(generation.id))

    async def _style_segment(self, work_id: UUID) -> ContextSegment | None:
        if self._style_reader is None:
            return None
        try:
            profile = await self._style_reader.get_active(work_id)
        except Exception:
            logger.exception("generation.style_read_failed", work_id=str(work_id))
            return None
        if profile is None:
            return None
        text = profile.summary
        if profile.do_list:
            text += "\nDO: " + "; ".join(profile.do_list)
        if profile.dont_list:
            text += "\nDON'T: " + "; ".join(profile.dont_list)
        return ContextSegment(
            name="style",
            source="style_profile",
            ref=str(profile.id),
            text=text,
            tokens=max(1, len(text)),
        )

    async def _retrieve_segments(self, work_id: UUID, query: str) -> list[ContextSegment]:
        if self._retrieval is None:
            return []
        try:
            chunks = await self._retrieval.retrieve(work_id, query, limit=6)
            return [
                ContextSegment(
                    name="memory",
                    source=chunk.source,
                    ref=chunk.ref,
                    text=chunk.text,
                    tokens=chunk.tokens,
                )
                for chunk in chunks
            ]
        except Exception:
            logger.exception("generation.retrieval_failed", work_id=str(work_id))
            return []

    @staticmethod
    def _user_prompt(task_type: str, chapter_title: str, instruction: str | None) -> str:
        instruction = (instruction or "续写本章，承接上文，不自动推进大剧情。").strip()
        return f"章节：{chapter_title}\n任务：{task_type}\n作者指令：{instruction}"

    @staticmethod
    def _max_tokens(target_words: int | None) -> int:
        if target_words is None:
            return 2_000
        return min(8_192, max(512, target_words * 2))
