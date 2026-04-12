from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default="free")  # free | pro
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    jobs: Mapped[list["Job"]] = relationship(back_populates="owner")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_state", "state"),
        Index("ix_jobs_created_at", "created_at"),
        Index("ix_jobs_expires_at", "expires_at"),
        Index("ix_jobs_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "video" | "image"

    state: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timed_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Optional metadata fields (paths/keys will be added later through storage service).
    upload_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stored_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    result: Mapped["Result | None"] = relationship(back_populates="job", uselist=False)
    owner: Mapped["User | None"] = relationship(back_populates="jobs")


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        # Primary key already enforces uniqueness, but we keep this explicit per requirement.
        UniqueConstraint("job_id", name="uq_results_job_id"),
        Index("ix_results_job_id", "job_id"),
    )

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), primary_key=True)

    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # JSON stored as text for simplicity/portability; schema is stabilized at the API layer.
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[Job] = relationship(back_populates="result")

