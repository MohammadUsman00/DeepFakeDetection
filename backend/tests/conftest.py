"""Ensure SaaS auth is off for API smoke tests unless a test overrides it."""

from __future__ import annotations

import os
from pathlib import Path

# Isolated SQLite DB for pytest (avoids requiring local Postgres when root `.env` sets DATABASE_URL).
_test_db = (Path(__file__).resolve().parent / "deepshield_test.sqlite3").as_posix()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"

os.environ.setdefault("SAAS_REQUIRE_AUTH", "false")


def pytest_configure() -> None:
    # TestClient may not run FastAPI lifespan on the Socket.IO ASGI wrapper; run migrations explicitly.
    from app.db.init_db import init_db

    init_db()
