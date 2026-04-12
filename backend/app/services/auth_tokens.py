from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings


def create_access_token(*, user_id: str, email: str, tier: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=int(settings.saas.jwt_exp_hours))
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.saas.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.saas.jwt_secret, algorithms=["HS256"])
