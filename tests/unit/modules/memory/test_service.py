from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.kernel.errors import ValidationError
from webnovel.modules.memory.contract import (
    ExtractionRun,
    ExtractionStatus,
    ProposalStatus,
)
from webnovel.modules.memory.service import MemoryServiceImpl


class FakeMemoryRepository:
    def __init__(self) -> None:
        self.created: tuple[UUID, UUID, UUID, str] | None = None

    async def create_run(
        self, work_id: UUID, chapter_id: UUID, version_id: UUID, trigger: str
    ) -> ExtractionRun:
        self.created = (work_id, chapter_id, version_id, trigger)
        return ExtractionRun(
            id=uuid4(),
            work_id=work_id,
            chapter_id=chapter_id,
            version_id=version_id,
            status=ExtractionStatus.PENDING,
            created_at=datetime.now(UTC),
        )

    async def list_proposals(
        self, work_id: UUID, status: ProposalStatus | None = None
    ) -> list[Any]:
        return []

    async def resolve_proposal(
        self,
        proposal_id: UUID,
        action: str,
        *,
        base_entity_version: int,
        modified_payload: dict[str, Any] | None = None,
    ) -> Any:
        return None

    async def list_entities(self, work_id: UUID) -> list[Any]:
        return []

    async def get_summary(self, chapter_id: UUID) -> Any:
        return None


async def test_start_extraction_enqueues_run() -> None:
    repo = FakeMemoryRepository()
    enqueued: list[UUID] = []

    async def enqueue(run_id: UUID) -> None:
        enqueued.append(run_id)

    service = MemoryServiceImpl(repo, enqueue)
    run = await service.start_extraction(uuid4(), uuid4(), uuid4())
    assert repo.created is not None
    assert enqueued == [run.id]


async def test_resolve_rejects_unknown_action() -> None:
    service = MemoryServiceImpl(FakeMemoryRepository())
    try:
        await service.resolve_proposal(uuid4(), "approve", base_entity_version=0)
    except ValidationError as exc:
        assert exc.code == "proposal.invalid_action"
    else:
        raise AssertionError("expected ValidationError")
