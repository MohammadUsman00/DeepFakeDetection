"""Smoke tests for API routes (no Celery / no heavy ML)."""

from __future__ import annotations

from dataclasses import replace
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import analyze as analyze_routes
from app.api.routes import artifacts as artifacts_routes
from app.api import deps as api_deps
from app.config import settings as app_settings
from app.db.repository import JobRepository
from app.db.session import db_session
from app.services.auth_tokens import create_access_token
from app.services.storage_service import StorageService


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok" or "status" in body


def test_health_live(client: TestClient) -> None:
    r = client.get("/api/health/live")
    assert r.status_code == 200
    assert r.json().get("status") == "alive"


def test_health_ready(client: TestClient) -> None:
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body.get("checks", {}).get("database") == "ok"


def test_metrics_endpoint(client: TestClient) -> None:
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert len(r.text) > 0


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

    me_cookie = client.get("/api/auth/me")
    assert me_cookie.status_code == 200
    assert me_cookie.json()["email"] == email


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


def test_artifact_requires_authorization_header_when_auth_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    secure_settings = replace(app_settings, saas=replace(app_settings.saas, require_auth=True))
    monkeypatch.setattr(artifacts_routes, "settings", secure_settings)
    monkeypatch.setattr(api_deps, "settings", secure_settings)

    user_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    token = create_access_token(user_id=user_id, email="owner@example.com", tier="free")

    db = db_session()
    try:
        repo = JobRepository(db)
        repo.create_job(
            job_id=job_id,
            media_type="image",
            original_filename="sample.png",
            original_content_type="image/png",
            user_id=user_id,
        )
        StorageService().save_artifact_bytes(job_id=job_id, name="heatmap_frame_0.png", data=b"PNG")
    finally:
        db.close()

    missing_auth = client.get(f"/api/artifacts/{job_id}/heatmap_frame_0.png")
    assert missing_auth.status_code == 401

    bad_query_token = client.get(
        f"/api/artifacts/{job_id}/heatmap_frame_0.png?access_token={token}"
    )
    assert bad_query_token.status_code == 401

    ok = client.get(
        f"/api/artifacts/{job_id}/heatmap_frame_0.png",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert ok.headers.get("cache-control") == "no-store"
