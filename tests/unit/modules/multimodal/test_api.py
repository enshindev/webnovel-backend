from __future__ import annotations

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app


def test_status_reports_unconfigured_providers() -> None:
    response = TestClient(create_app()).get("/api/v1/experiments/multimodal/status")
    assert response.status_code == 200
    assert response.json() == {"asr": False, "tts": False, "cover": False}


def test_speech_returns_503_when_unconfigured() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/experiments/multimodal/speech", json={"text": "你好"}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "multimodal.tts_unavailable"
