from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..utils.errors import AppError, ErrorCode
from .models import Job, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    email: str
    tier: str
    created_at: datetime


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, *, user_id: str, email: str, password_hash: str, tier: str = "free") -> UserRecord:
        now = _utcnow()
        normalized = email.strip().lower()
        u = User(id=user_id, email=normalized, password_hash=password_hash, tier=tier, created_at=now)
        try:
            self.db.add(u)
            self.db.commit()
            self.db.refresh(u)
        except IntegrityError as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.EMAIL_IN_USE, message="Email already registered") from e
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to create user", details={"reason": str(e)}) from e
        return self._to_record(u)

    def get_by_email(self, email: str) -> UserRecord | None:
        q = email.strip().lower()
        u = self.db.scalar(select(User).where(User.email == q))
        return None if u is None else self._to_record(u)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        u = self.db.get(User, user_id)
        return None if u is None else self._to_record(u)

    def get_password_hash(self, user_id: str) -> str | None:
        u = self.db.get(User, user_id)
        return None if u is None else u.password_hash

    def count_jobs_since(self, user_id: str, since: datetime) -> int:
        n = self.db.scalar(
            select(func.count()).select_from(Job).where(Job.user_id == user_id, Job.created_at >= since)
        )
        return int(n or 0)

    @staticmethod
    def _to_record(u: User) -> UserRecord:
        return UserRecord(id=u.id, email=u.email, tier=u.tier, created_at=u.created_at)
