from __future__ import annotations

from sqlalchemy import inspect, text

from .models import Base
from .session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    insp = inspect(engine)
    dialect = engine.dialect.name

    # Bootstrap columns on existing `jobs` rows (SQLite + PostgreSQL dev DBs).
    if "jobs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("jobs")}
        alter_stmts: list[str] = []
        if "original_filename" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN original_filename VARCHAR(128)")
        if "original_content_type" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN original_content_type VARCHAR(64)")
        if "original_size_bytes" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN original_size_bytes INTEGER")
        if "stored_size_bytes" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN stored_size_bytes INTEGER")
        if "processing_started_at" not in cols:
            if dialect == "sqlite":
                alter_stmts.append("ALTER TABLE jobs ADD COLUMN processing_started_at DATETIME")
            else:
                alter_stmts.append(
                    "ALTER TABLE jobs ADD COLUMN processing_started_at TIMESTAMP WITH TIME ZONE"
                )
        if "processing_completed_at" not in cols:
            if dialect == "sqlite":
                alter_stmts.append("ALTER TABLE jobs ADD COLUMN processing_completed_at DATETIME")
            else:
                alter_stmts.append(
                    "ALTER TABLE jobs ADD COLUMN processing_completed_at TIMESTAMP WITH TIME ZONE"
                )
        if "retry_count" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
        if "timed_out" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN timed_out INTEGER NOT NULL DEFAULT 0")
        if "user_id" not in cols:
            alter_stmts.append("ALTER TABLE jobs ADD COLUMN user_id VARCHAR(36)")

        if alter_stmts:
            with engine.begin() as conn:
                for stmt in alter_stmts:
                    conn.execute(text(stmt))
