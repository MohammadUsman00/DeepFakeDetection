from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


def _sqlite_url(db_path: Path) -> str:
    # SQLAlchemy expects forward slashes in file URLs even on Windows.
    return f"sqlite:///{db_path.as_posix()}"


def _database_url_from_env() -> str | None:
    """
    If DATABASE_URL is set (e.g. postgresql://... in Docker), use PostgreSQL.
    Otherwise use local SQLite under the configured data directory.
    """
    raw = os.getenv("DATABASE_URL", "").strip()
    return raw or None


def get_engine() -> Engine:
    url = _database_url_from_env()
    if url:
        # pool_pre_ping avoids stale connections after idle periods (e.g. behind Docker)
        return create_engine(url, pool_pre_ping=True)

    db_path = (settings.storage.data_dir / "db" / "app.sqlite3").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False allows usage across FastAPI threads / Celery.
    return create_engine(_sqlite_url(db_path), connect_args={"check_same_thread": False})


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def db_session() -> Session:
    return SessionLocal()
