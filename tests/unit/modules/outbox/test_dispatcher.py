from __future__ import annotations

from typing import Any
from uuid import uuid4

from webnovel.modules.outbox.dispatcher import dispatch_once
from webnovel.modules.outbox.models import OutboxEventModel


class FakeResult:
    def __init__(self, rows: list[OutboxEventModel]) -> None:
        self._rows = rows

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[OutboxEventModel]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[OutboxEventModel]) -> None:
        self.rows = rows
        self.flushed = 0

    async def execute(self, statement: Any) -> FakeResult:
        _ = statement
        return FakeResult(self.rows)

    async def flush(self) -> None:
        self.flushed += 1


async def test_outbox_moves_to_dead_after_max_attempts() -> None:
    row = OutboxEventModel(
        id=1,
        aggregate_type="work",
        aggregate_id=uuid4(),
        event_type="test",
        payload={},
        status="pending",
        attempts=0,
    )
    session = FakeSession([row])

    async def failing_handler(event: OutboxEventModel) -> None:
        _ = event
        raise RuntimeError("downstream down")

    for _ in range(5):
        await dispatch_once(session, handler=failing_handler, max_attempts=5)  # type: ignore[arg-type]
        if row.status != "dead":
            row.available_at = None
    assert row.status == "dead"
    assert row.attempts == 5
    assert "downstream down" in (row.last_error or "")


async def test_outbox_webhook_payload(monkeypatch) -> None:
    from uuid import uuid4

    from webnovel.infra.config import Settings
    from webnovel.modules.outbox import dispatcher

    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
            captured.update(json)
            return FakeResponse()

    monkeypatch.setattr(
        dispatcher, "get_settings", lambda: Settings(outbox_webhook_url="http://hook")
    )
    monkeypatch.setattr(dispatcher.httpx, "AsyncClient", FakeClient)
    row = OutboxEventModel(
        id=1,
        aggregate_type="work",
        aggregate_id=uuid4(),
        event_type="generation.accepted",
        payload={"chapter_id": "x"},
        status="pending",
        attempts=0,
    )
    await dispatcher._handle(row)
    assert captured["event_type"] == "generation.accepted"
    assert captured["payload"] == {"chapter_id": "x"}
