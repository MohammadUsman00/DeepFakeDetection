"""Smoke tests for API routes (no Celery / no heavy ML)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


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
