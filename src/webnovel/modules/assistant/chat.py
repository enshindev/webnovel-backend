from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from webnovel.infra.config import Settings
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.assistant.contract import AssistantEvent, Message
from webnovel.modules.assistant.knowledge import KnowledgeRetriever, KnowledgeSearchService
from webnovel.modules.assistant.repository import AssistantRepository
from webnovel.modules.assistant.tools import AssistantTools, ToolResult
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.usage.contract import UsageService
from webnovel.modules.works.contract import WorkService


class AssistantChatRunner:
    def __init__(
        self,
        *,
        repository: AssistantRepository,
        work_service: WorkService,
        chapter_service: ChapterService,
        model_client: ModelClient,
        settings: Settings,
        usage: UsageService | None = None,
        tools: AssistantTools | None = None,
        knowledge: KnowledgeRetriever | None = None,
        knowledge_store: KnowledgeSearchService | None = None,
    ) -> None:
        self._repository = repository
        self._work_service = work_service
        self._chapter_service = chapter_service
        self._model_client = model_client
        self._settings = settings
        self._usage = usage
        self._tools = tools
        self._knowledge = knowledge
        self._knowledge_store = knowledge_store

    async def run(self, conversation_id: UUID, content: str) -> Message:
        conversation, rendered, citations = await self._prepare(conversation_id, content)
        reply, citations, usage = await self._complete_with_tools(conversation, rendered, citations)
        message = await self._repository.add_message(
            conversation_id, "assistant", reply, citations, [], None
        )
        await self._record_usage(conversation, rendered, reply, usage)
        return message

    async def _complete_with_tools(
        self, conversation: Any, rendered: str, citations: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], Any]:
        complete_response = getattr(self._model_client, "complete_response", None)
        if complete_response is None:
            reply = await self._model_client.complete(
                ModelRequest(
                    model=self._settings.llm_model,
                    messages=[ChatMessage(role="user", content=rendered)],
                    max_tokens=1_500,
                )
            )
            return reply, citations, None

        tools = self._tools.schemas() if self._tools is not None else None
        messages: list[ChatMessage] = [ChatMessage(role="user", content=rendered)]
        usage = None
        for _ in range(2):
            response = await complete_response(
                ModelRequest(
                    model=self._settings.llm_model,
                    messages=messages,
                    max_tokens=1_500,
                    tools=tools,
                )
            )
            usage = response.usage
            if not response.tool_calls:
                return response.text, _dedupe_citations(citations), usage
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )
            tool_messages = await self._execute_tool_calls(
                conversation, list(response.tool_calls), citations
            )
            messages.extend(tool_messages)
        return "", _dedupe_citations(citations), usage

    async def _execute_tool_calls(
        self, conversation: Any, tool_calls: list[Any], citations: list[dict[str, Any]]
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        if self._tools is None or conversation.work_id is None:
            return messages
        for call in tool_calls:
            try:
                execution = await asyncio.wait_for(
                    self._tools.execute(call.name, conversation.work_id, call.arguments),
                    timeout=8,
                )
                citations.extend(execution.citations)
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=execution.text,
                        tool_call_id=call.id,
                    )
                )
            except Exception as exc:
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=f"工具执行失败：{exc}",
                        tool_call_id=call.id,
                    )
                )
        return messages

    async def stream(self, conversation_id: UUID, content: str) -> AsyncIterator[AssistantEvent]:
        conversation, rendered, citations = await self._prepare(conversation_id, content)
        tools = self._tools.schemas() if self._tools is not None else None
        messages: list[ChatMessage] = [ChatMessage(role="user", content=rendered)]
        usage = None
        reply = ""
        try:
            for round_no in range(2):
                parts: list[str] = []
                tool_calls: list[Any] = []
                async for event in self._model_client.stream(
                    ModelRequest(
                        model=self._settings.llm_model,
                        messages=messages,
                        max_tokens=1_500,
                        tools=tools if round_no == 0 else None,
                    )
                ):
                    if event.type == "delta" and event.text:
                        parts.append(event.text)
                        yield AssistantEvent(type="delta", text=event.text)
                    elif event.type == "usage":
                        usage = event.usage
                    elif event.type == "tool_calls":
                        tool_calls = list(event.tool_calls or [])
                    elif event.type == "done":
                        usage = event.usage or usage
                    elif event.type == "error":
                        raise RuntimeError(
                            f"model error: {event.error_class}: {event.error_code_raw}"
                        )

                if not tool_calls:
                    reply = "".join(parts)
                    break
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content="".join(parts),
                        tool_calls=tool_calls,
                    )
                )
                messages.extend(await self._execute_tool_calls(conversation, tool_calls, citations))

            message = await self._repository.add_message(
                conversation_id, "assistant", reply, _dedupe_citations(citations), [], None
            )
            await self._record_usage(conversation, rendered, reply, usage)
            yield AssistantEvent(
                type="done",
                message=message,
                citations=_dedupe_citations(citations),
            )
        except Exception as exc:
            yield AssistantEvent(type="error", text=str(exc))

    async def _prepare(
        self, conversation_id: UUID, content: str
    ) -> tuple[Any, str, list[dict[str, Any]]]:
        conversation = await self._repository.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"conversation not found: {conversation_id}")
        if not content.strip():
            raise ValueError("message must not be empty")

        await self._repository.add_message(conversation_id, "user", content, [], [], None)
        result = (
            await self._tools.gather(conversation.work_id, content)
            if self._tools is not None and conversation.work_id is not None
            else ToolResult()
        )
        citations = [
            {"source": chunk.source, "ref": chunk.ref, "quote": chunk.text[:200]}
            for chunk in result.chunks
        ]
        citations.extend(
            {
                "source": "entity",
                "ref": f"entity:{entity.id}",
                "quote": f"{entity.type}: {entity.name}",
            }
            for entity in result.entities
        )
        if conversation.scope == "ideation":
            if self._knowledge_store is not None:
                knowledge_chunks = await self._knowledge_store.search(content)
            elif self._knowledge is not None:
                knowledge_chunks = await self._knowledge.asearch(content)
            else:
                knowledge_chunks = []
        else:
            knowledge_chunks = []
        citations.extend(
            {
                "source": "knowledge",
                "ref": chunk.ref,
                "quote": chunk.text[:200],
            }
            for chunk in knowledge_chunks
        )
        context = await self._context(
            conversation_id,
            conversation.scope,
            conversation.work_id,
            result.chunks,
            result.entities,
            knowledge_chunks,
        )
        prompt_key = "assistant/work" if conversation.scope == "work" else "assistant/ideation"
        prompt = PromptRegistry(self._settings.prompts_dir).resolve(prompt_key)
        includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
        rendered = render_prompt(
            prompt,
            {
                "conversation_title": conversation.title or "未命名会话",
                "mode": conversation.mode,
                "workspace_context": context,
                "message": content,
            },
            includes,
        )
        return conversation, rendered, citations

    async def _record_usage(
        self, conversation: Any, prompt_text: str, completion_text: str, usage: Any = None
    ) -> None:
        if self._usage is None:
            return
        with contextlib.suppress(Exception):
            await self._usage.record_llm(
                work_id=conversation.work_id,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type="assistant",
                prompt_tokens=usage.prompt_tokens if usage else estimate_tokens(prompt_text),
                completion_tokens=usage.completion_tokens
                if usage
                else estimate_tokens(completion_text),
                cached_tokens=usage.cached_tokens if usage else 0,
                estimated=not usage,
            )

    @staticmethod
    def _dedupe(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _dedupe_citations(citations)

    async def _context(
        self,
        conversation_id: UUID,
        scope: str,
        work_id: UUID | None,
        chunks: list[Any],
        entities: list[Any],
        knowledge_chunks: list[Any],
    ) -> str:
        parts: list[str] = []
        if scope == "work" and work_id is not None:
            try:
                work = await self._work_service.get(work_id)
                parts.append(f"作品：{work.title}（{work.genre or '未设题材'}）")
                chapters = await self._chapter_service.list(work_id)
                parts.append("章节：" + "、".join(chapter.title for chapter in chapters[:50]))
            except Exception:
                parts.append("作品上下文暂不可用。")
        else:
            parts.append("当前是开书前的 ideation 会话，不要假定已有正文。")
        if chunks:
            memory = "\n".join(
                f"[{chunk.source}:{chunk.ref}] {chunk.text[:800]}" for chunk in chunks
            )
            parts.append(f"记忆检索：\n{memory}")
        if entities:
            entity_lines = "\n".join(
                f"[entity:{entity.id}] {entity.type}: {entity.name} {entity.attributes}"
                for entity in entities
            )
            parts.append(f"设定实体：\n{entity_lines}")
        if knowledge_chunks:
            knowledge = "\n".join(
                f"[knowledge:{chunk.ref}] {chunk.text[:800]}" for chunk in knowledge_chunks
            )
            parts.append(f"创作知识：\n{knowledge}")
        messages = await self._repository.list_messages(conversation_id, limit=12)
        if messages:
            history = "\n".join(f"{message.role}: {message.content}" for message in messages)
            parts.append(f"最近对话：\n{history}")
        return "\n\n".join(parts)


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[object, object]] = set()
    result: list[dict[str, Any]] = []
    for citation in citations:
        key = (citation.get("source"), citation.get("ref"))
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result
