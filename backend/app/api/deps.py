from __future__ import annotations

from fastapi import Header

from ..config import settings
from ..services.auth_tokens import decode_access_token
from ..utils.errors import AppError, ErrorCode


async def resolve_bearer_user_id(authorization: str | None = Header(None)) -> str | None:
    """
    When SAAS_REQUIRE_AUTH is false: returns None (anonymous API usage).
    When true: requires `Authorization: Bearer <jwt>` and returns user id.
    """

    if not settings.saas.require_auth:
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing bearer token")
    try:
        data = decode_access_token(token)
        uid = data.get("sub")
        if not uid or not isinstance(uid, str):
            raise ValueError("no sub")
        return uid
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid or expired token") from e


async def require_user_id(authorization: str | None = Header(None)) -> str:
    """Strict: always requires a valid user (for register-only flows)."""

    uid = await resolve_bearer_user_id(authorization)
    if uid is None:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Authentication required")
    return uid


async def require_token_user_id(authorization: str | None = Header(None)) -> str:
    """Validate Bearer JWT regardless of SAAS_REQUIRE_AUTH (for /auth/me)."""

    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing bearer token")
    try:
        data = decode_access_token(token)
        uid = data.get("sub")
        if not uid or not isinstance(uid, str):
            raise ValueError("no sub")
        return uid
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid or expired token") from e
