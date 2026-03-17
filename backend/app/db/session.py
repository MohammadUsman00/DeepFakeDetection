from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


def _sqlite_url(db_path: Path) -> str:
    # SQLAlchemy expects forward slashes in file URLs even on Windows.
    return f"sqlite:///{db_path.as_posix()}"


def get_engine() -> Engine:
    db_path = (settings.storage.data_dir / "db" / "app.sqlite3").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False allows usage across FastAPI threads/background tasks.
    return create_engine(_sqlite_url(db_path), connect_args={"check_same_thread": False})


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def db_session() -> Session:
    return SessionLocal()

