import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.database import utcnow

DEMO_USERS = {
    "expert": ("expert_001", "expert", "Demo Expert"),
    "reviewer": ("reviewer_001", "reviewer", "Demo Reviewer"),
    "apprentice": ("apprentice_001", "apprentice", "Demo Apprentice"),
}
bearer = HTTPBearer(auto_error=False)
PLAYBACK_TOKEN_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: str
    display_name: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(data: dict, key: str) -> str:
    payload = _encode(json.dumps(data, separators=(",", ":")).encode())
    signature = _encode(hmac.new(key.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def _verify(token: str, key: str) -> dict:
    payload, signature = token.split(".")
    expected = hmac.new(key.encode(), payload.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _decode(signature)):
        raise ValueError("Invalid signature")
    data = json.loads(_decode(payload))
    if not isinstance(data["exp"], (int, float)) or data["exp"] <= utcnow().timestamp():
        raise ValueError("Expired token")
    return data


def issue_token(user_key, settings, key):
    user = CurrentUser(*DEMO_USERS[user_key])
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.demo_token_ttl_minutes)
    return _sign(
        {
            "sub": user.id,
            "role": user.role,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        },
        key,
    ), expires_at


def issue_playback_token(media_id: str, user: CurrentUser, key: str) -> tuple[str, datetime]:
    expires_at = utcnow() + PLAYBACK_TOKEN_TTL
    return _sign(
        {
            "sub": user.id,
            "role": user.role,
            "scope": "playback",
            "media_id": media_id,
            "exp": int(expires_at.timestamp()),
        },
        key,
    ), expires_at


def verify_playback_token(token: str, media_id: str, key: str) -> CurrentUser:
    try:
        data = _verify(token, key)
        if data["scope"] != "playback" or data["media_id"] != media_id:
            raise ValueError("Invalid playback scope")
        for identity in DEMO_USERS.values():
            if (data["sub"], data["role"]) == identity[:2]:
                return CurrentUser(*identity)
        raise ValueError("Unknown identity")
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError) as exc:
        raise AppError("UNAUTHENTICATED", "Valid playback token required.", 401) from exc


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    try:
        if credentials is None:
            raise ValueError("Missing token")
        data = _verify(credentials.credentials, request.app.state.signing_key)
        if "scope" in data:
            raise ValueError("Scoped token")
        for identity in DEMO_USERS.values():
            if (data["sub"], data["role"]) == identity[:2]:
                return CurrentUser(*identity)
        raise ValueError("Unknown identity")
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError) as exc:
        raise AppError("UNAUTHENTICATED", "Valid bearer token required.", 401) from exc


def require_roles(*roles):
    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]):
        if user.role not in roles:
            raise AppError("FORBIDDEN", "This role cannot perform this action.", 403)
        return user

    return dependency
