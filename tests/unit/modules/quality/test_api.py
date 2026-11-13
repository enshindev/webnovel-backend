from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_quality_service
from webnovel.modules.quality.contract import QualityIssue, QualityReport


class FakeQualityService:
    async def check_chapter(self, work_id: UUID, chapter_id: UUID) -> QualityReport:
        return self._report(work_id, chapter_id)

    async def get_report(self, report_id: UUID) -> QualityReport:
        return self._report(uuid4(), uuid4())

    async def list_reports(self, work_id: UUID) -> list[QualityReport]:
        return []

    @staticmethod
    def _report(work_id: UUID, chapter_id: UUID) -> QualityReport:
        return QualityReport(
            id=uuid4(),
            work_id=work_id,
            chapter_id=chapter_id,
            version_id=uuid4(),
            status="warning",
            score=88,
            issues=[
                QualityIssue(
                    code="word_count.thin",
                    severity="P1",
                    message="偏薄",
                    location={"word_count": 1000},
                )
            ],
            metrics={"word_count": 1000},
            created_at=datetime.now(UTC),
        )


def test_run_quality_check() -> None:
    fake = FakeQualityService()
    app = create_app()
    app.dependency_overrides[get_quality_service] = lambda: fake
    client = TestClient(app)
    work_id = uuid4()
    chapter_id = uuid4()
    response = client.post(
        f"/api/v1/works/{work_id}/quality-checks", json={"chapter_id": str(chapter_id)}
    )
    assert response.status_code == 201
    assert response.json()["score"] == 88
    assert response.json()["issues"][0]["code"] == "word_count.thin"
