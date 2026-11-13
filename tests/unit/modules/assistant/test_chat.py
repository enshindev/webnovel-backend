from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.assistant.chat import AssistantChatRunner
from webnovel.modules.assistant.contract import Conversation, Message


class FakeAssistantRepository:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.messages: list[Message] = []

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        return self.conversation

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        usage: dict[str, Any] | None,
    ) -> Message:
        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            tool_calls=tool_calls,
            usage=usage,
            created_at=datetime.now(UTC),
        )
        self.messages.append(message)
        return message

    async def list_messages(self, conversation_id: UUID, limit: int) -> list[Message]:
        return self.messages[-limit:]


class FakeWorkService:
    async def get(self, work_id: UUID) -> Any:
        class Work:
            title = "长夜灯火"
            genre = "悬疑"

        return Work()


class FakeChapterService:
    async def list(self, work_id: UUID) -> list[Any]:
        return []


class FakeModel:
    async def complete(self, request: Any) -> str:
        assert "用户说" in request.messages[-1].content
        return "建议：先写雨夜追捕。"


async def test_chat_runner_persists_user_and_assistant() -> None:
    conversation = Conversation(
        id=uuid4(),
        scope="ideation",
        work_id=None,
        mode="direction",
        title="找方向",
        summary=None,
        created_at=datetime.now(UTC),
    )
    repo = FakeAssistantRepository(conversation)
    runner = AssistantChatRunner(
        repository=repo,
        work_service=FakeWorkService(),
        chapter_service=FakeChapterService(),
        model_client=FakeModel(),
        settings=Settings(),
    )
    reply = await runner.run(conversation.id, "我想写悬疑")
    assert reply.content.startswith("建议")
    assert [message.role for message in repo.messages] == ["user", "assistant"]


class FakeTools:
    async def gather(self, work_id: UUID, query: str, limit: int = 5) -> Any:
        from webnovel.modules.assistant.tools import ToolResult
        from webnovel.modules.memory.contract import MemoryChunk

        return ToolResult(chunks=[MemoryChunk("chapter", "chapter:1:0", "雨夜追捕", 10)])

    def schemas(self) -> list[dict[str, Any]]:
        return []

    async def execute(self, name: str, work_id: UUID, arguments: str) -> Any:
        from webnovel.modules.assistant.tools import ToolExecution

        return ToolExecution(
            text="雨夜追捕",
            citations=[{"source": "chapter", "ref": "chapter:1:0", "quote": "雨夜追捕"}],
        )


async def test_chat_runner_attaches_citations() -> None:
    work_id = uuid4()
    conversation = Conversation(
        id=uuid4(),
        scope="work",
        work_id=work_id,
        mode="story_qa",
        title="查设定",
        summary=None,
        created_at=datetime.now(UTC),
    )
    repo = FakeAssistantRepository(conversation)
    runner = AssistantChatRunner(
        repository=repo,
        work_service=FakeWorkService(),
        chapter_service=FakeChapterService(),
        model_client=FakeModel(),
        settings=Settings(),
        tools=FakeTools(),
    )
    reply = await runner.run(conversation.id, "雨夜发生了什么")
    assert reply.citations[0]["source"] == "chapter"


class FakeToolCallingModel:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_response(self, request: Any) -> Any:
        from webnovel.kernel.ports.llm import ModelResponse, ToolCall

        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                text="",
                tool_calls=[
                    ToolCall(id="call-1", name="search_chapters", arguments='{"query":"雨夜"}')
                ],
            )
        return ModelResponse(text="基于检索：雨夜追捕。", tool_calls=[])


class FakeStreamingModel:
    async def stream(self, request: Any):
        from webnovel.kernel.ports.llm import ModelEvent, ModelUsage

        yield ModelEvent(type="delta", text="建议：")
        yield ModelEvent(type="delta", text="先写雨夜追捕。")
        yield ModelEvent(type="done", usage=ModelUsage(prompt_tokens=10, completion_tokens=8))


async def test_chat_runner_streams_and_persists() -> None:
    conversation = Conversation(
        id=uuid4(),
        scope="ideation",
        work_id=None,
        mode="direction",
        title="找方向",
        summary=None,
        created_at=datetime.now(UTC),
    )
    repo = FakeAssistantRepository(conversation)
    runner = AssistantChatRunner(
        repository=repo,
        work_service=FakeWorkService(),
        chapter_service=FakeChapterService(),
        model_client=FakeStreamingModel(),
        settings=Settings(),
    )
    events = [event async for event in runner.stream(conversation.id, "我想写悬疑")]
    assert [event.type for event in events] == ["delta", "delta", "done"]
    assert repo.messages[-1].role == "assistant"
    assert "雨夜" in repo.messages[-1].content


async def test_chat_runner_executes_model_tool_calls() -> None:
    work_id = uuid4()
    conversation = Conversation(
        id=uuid4(),
        scope="work",
        work_id=work_id,
        mode="story_qa",
        title="查设定",
        summary=None,
        created_at=datetime.now(UTC),
    )
    repo = FakeAssistantRepository(conversation)
    runner = AssistantChatRunner(
        repository=repo,
        work_service=FakeWorkService(),
        chapter_service=FakeChapterService(),
        model_client=FakeToolCallingModel(),
        settings=Settings(),
        tools=FakeTools(),
    )
    reply = await runner.run(conversation.id, "雨夜发生了什么")
    assert reply.content == "基于检索：雨夜追捕。"
    assert reply.citations[0]["ref"] == "chapter:1:0"


class FakeToolStreamingModel:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, request: Any):
        from webnovel.kernel.ports.llm import ModelEvent, ModelUsage, ToolCall

        self.calls += 1
        if self.calls == 1:
            yield ModelEvent(
                type="tool_calls",
                tool_calls=[ToolCall("call-1", "search_chapters", '{"query":"雨夜"}')],
            )
            yield ModelEvent(type="done", usage=ModelUsage())
            return
        yield ModelEvent(type="delta", text="基于工具：")
        yield ModelEvent(type="delta", text="雨夜追捕。")
        yield ModelEvent(type="done", usage=ModelUsage(prompt_tokens=10, completion_tokens=5))


async def test_stream_executes_tool_calls() -> None:
    work_id = uuid4()
    conversation = Conversation(
        id=uuid4(),
        scope="work",
        work_id=work_id,
        mode="story_qa",
        title="查设定",
        summary=None,
        created_at=datetime.now(UTC),
    )
    repo = FakeAssistantRepository(conversation)
    runner = AssistantChatRunner(
        repository=repo,
        work_service=FakeWorkService(),
        chapter_service=FakeChapterService(),
        model_client=FakeToolStreamingModel(),
        settings=Settings(),
        tools=FakeTools(),
    )
    events = [event async for event in runner.stream(conversation.id, "雨夜发生了什么")]
    assert [event.type for event in events] == ["delta", "delta", "done"]
    assert repo.messages[-1].content == "基于工具：雨夜追捕。"
    assert repo.messages[-1].citations[0]["ref"] == "chapter:1:0"
