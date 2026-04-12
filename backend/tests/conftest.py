"""Ensure SaaS auth is off for API smoke tests unless a test overrides it."""

from __future__ import annotations

import os

os.environ.setdefault("SAAS_REQUIRE_AUTH", "false")


def pytest_configure() -> None:
    # TestClient may not run FastAPI lifespan on the Socket.IO ASGI wrapper; run migrations explicitly.
    from app.db.init_db import init_db

    init_db()
