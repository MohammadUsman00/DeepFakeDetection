from __future__ import annotations

from starlette.responses import Response

from ..config import settings


def set_auth_cookie(response: Response, token: str) -> None:
    """HttpOnly session cookie (JWT). Prefer SameSite=Lax for dev; set Secure + SameSite=None for cross-site HTTPS."""
    cfg = settings.saas
    max_age = int(cfg.jwt_exp_hours) * 3600
    response.set_cookie(
        key=cfg.auth_cookie_name,
        value=token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=cfg.auth_cookie_secure,
        samesite=cfg.auth_cookie_samesite,
    )


def clear_auth_cookie(response: Response) -> None:
    cfg = settings.saas
    response.delete_cookie(
        key=cfg.auth_cookie_name,
        path="/",
        secure=cfg.auth_cookie_secure,
        samesite=cfg.auth_cookie_samesite,
    )
