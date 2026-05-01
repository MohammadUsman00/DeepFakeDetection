from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from starlette.responses import Response

from ...config import settings
from ...db.session import db_session
from ...db.user_repository import UserRepository
from ...services.auth_cookie import clear_auth_cookie, set_auth_cookie
from ...services.auth_tokens import create_access_token
from ...services.passwords import hash_password, verify_password
from ...utils.errors import AppError, ErrorCode
from ..deps import require_token_user_id

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _login_response_payload(u, token: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token_type": "bearer",
        "expires_in_hours": settings.saas.jwt_exp_hours,
        "user": {"id": u.id, "email": u.email, "tier": u.tier},
    }
    if settings.saas.return_token_in_body:
        payload["access_token"] = token
    return payload


@router.post("/auth/register")
def register(body: RegisterRequest, response: Response) -> dict[str, Any]:
    db = db_session()
    try:
        users = UserRepository(db)
        user_id = str(uuid.uuid4())
        users.create_user(user_id=user_id, email=body.email, password_hash=hash_password(body.password), tier="free")
        u = users.get_by_id(user_id)
        if u is None:
            raise AppError(code=ErrorCode.INTERNAL_ERROR, message="User creation failed")
        token = create_access_token(user_id=u.id, email=u.email, tier=u.tier)
        set_auth_cookie(response, token)
        return _login_response_payload(u, token)
    finally:
        db.close()


@router.post("/auth/login")
def login(body: LoginRequest, response: Response) -> dict[str, Any]:
    db = db_session()
    try:
        users = UserRepository(db)
        u = users.get_by_email(body.email)
        if u is None:
            raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid email or password")
        ph = users.get_password_hash(u.id)
        if ph is None or not verify_password(body.password, ph):
            raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid email or password")
        token = create_access_token(user_id=u.id, email=u.email, tier=u.tier)
        set_auth_cookie(response, token)
        return _login_response_payload(u, token)
    finally:
        db.close()


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, str]:
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/auth/me")
def me(user_id: str = Depends(require_token_user_id)) -> dict[str, Any]:
    db = db_session()
    try:
        users = UserRepository(db)
        u = users.get_by_id(user_id)
        if u is None:
            raise AppError(code=ErrorCode.UNAUTHORIZED, message="User not found")
        return {"id": u.id, "email": u.email, "tier": u.tier, "limits": {"free_daily_uploads": settings.saas.free_tier_daily_uploads}}
    finally:
        db.close()
