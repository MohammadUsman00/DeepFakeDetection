"""Smoke tests for API routes (no Celery / no heavy ML)."""

from __future__ import annotations

import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import analyze as analyze_routes


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok" or "status" in body


def test_results_unknown_job_404(client: TestClient) -> None:
    r = client.get("/api/results/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_register_and_login_flow(client: TestClient) -> None:
    email = f"test-user-{uuid.uuid4().hex[:8]}@example.com"
    password = "very-strong-pass-123"

    reg = client.post("/api/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 200
    reg_body = reg.json()
    assert reg_body["token_type"] == "bearer"
    assert reg_body["access_token"]
    assert reg_body["user"]["email"] == email

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {reg_body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_analyze_image_queues_job_without_celery(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_delay(job_id: str) -> None:
        captured["job_id"] = job_id

    monkeypatch.setattr(analyze_routes.process_analysis_task, "delay", fake_delay)

    # 1x1 PNG header + minimal body is enough for magic-byte validation.
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
    )
    response = client.post(
        "/api/analyze-image",
        files={"file": ("sample.png", png_bytes, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "QUEUED"
    assert body["job_id"]
    assert captured["job_id"] == body["job_id"]


def test_analyze_image_rejects_invalid_extension(client: TestClient) -> None:
    response = client.post(
        "/api/analyze-image",
        files={"file": ("bad.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 415
    body = response.json()
    assert body["error"]["error_code"] == "INVALID_EXTENSION"
