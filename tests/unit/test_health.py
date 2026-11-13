from __future__ import annotations

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_world_draft_frontend_is_served() -> None:
    from fastapi.testclient import TestClient

    from webnovel.entrypoints.api.app import create_app

    response = TestClient(create_app()).get("/app/")
    assert response.status_code == 200
    assert "World Draft" in response.text
    assert TestClient(create_app()).get("/app/analysis.html").status_code == 200
    assert TestClient(create_app()).get("/app/library.html").status_code == 200


def test_prompt_catalog_exposes_locked_version() -> None:
    from fastapi.testclient import TestClient

    from webnovel.entrypoints.api.app import create_app

    client = TestClient(create_app())
    listing = client.get("/api/v1/prompt-catalog/list/generation/continuation")
    assert listing.status_code == 200
    assert listing.json()["versions"]
    version = client.get("/api/v1/prompt-catalog/version/generation/continuation/1")
    assert version.status_code == 200
    assert version.json()["id"] == "generation/continuation"


def test_metrics_endpoint() -> None:
    from fastapi.testclient import TestClient

    from webnovel.entrypoints.api.app import create_app

    client = TestClient(create_app())
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "webnovel_http_requests_total" in response.text
