from __future__ import annotations

from fastapi.testclient import TestClient

from webnovel.entrypoints.api import app as app_module
from webnovel.infra.config import Settings


def test_optional_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module, "get_settings", lambda: Settings(api_token="secret", rate_limit_per_minute=0)
    )
    client = TestClient(app_module.create_app())
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/missing").status_code == 401
    assert (
        client.get("/api/v1/missing", headers={"Authorization": "Bearer secret"}).status_code == 404
    )


def test_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "get_settings", lambda: Settings(rate_limit_per_minute=1))
    client = TestClient(app_module.create_app())
    assert client.get("/api/v1/missing").status_code == 404
    assert client.get("/api/v1/missing").status_code == 429
