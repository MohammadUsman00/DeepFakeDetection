from __future__ import annotations

from fastapi import Header, Request

from ..config import settings
from ..services.auth_tokens import decode_access_token
from ..utils.errors import AppError, ErrorCode


def _jwt_from_request(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        t = authorization.split(" ", 1)[1].strip()
        if t:
            return t
    return request.cookies.get(settings.saas.auth_cookie_name)


def _decode_user_id(token: str) -> str:
    data = decode_access_token(token)
    uid = data.get("sub")
    if not uid or not isinstance(uid, str):
        raise ValueError("no sub")
    return uid


async def resolve_bearer_user_id(
    request: Request,
    authorization: str | None = Header(None),
) -> str | None:
    """
    When SAAS_REQUIRE_AUTH is false: returns None (anonymous API usage).
    When true: requires `Authorization: Bearer <jwt>` or HttpOnly session cookie and returns user id.
    """

    if not settings.saas.require_auth:
        return None
    token = _jwt_from_request(request, authorization)
    if not token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing or invalid credentials")
    try:
        return _decode_user_id(token)
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid or expired token") from e


async def require_user_id(request: Request, authorization: str | None = Header(None)) -> str:
    """Strict: always requires a valid user (for register-only flows)."""

    uid = await resolve_bearer_user_id(request, authorization)
    if uid is None:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Authentication required")
    return uid


async def require_token_user_id(request: Request, authorization: str | None = Header(None)) -> str:
    """Validate JWT from Bearer header or HttpOnly cookie (for /auth/me)."""

    token = _jwt_from_request(request, authorization)
    if not token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Missing or invalid credentials")
    try:
        return _decode_user_id(token)
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid or expired token") from e
