from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.core.errors import feature_disabled
from app.core.security import DEMO_USERS, issue_token
from app.models.schemas import DemoLoginOut, DemoLoginRequest

router = APIRouter(tags=["auth"])


@router.post("/auth/demo-login", response_model=DemoLoginOut)
def demo_login(
    req: DemoLoginRequest, request: Request, settings: Annotated[Settings, Depends(get_settings)]
):
    if not settings.enable_demo_auth:
        raise feature_disabled("ENABLE_DEMO_AUTH")
    token, expires = issue_token(req.demo_user, settings, request.app.state.signing_key)
    identity = DEMO_USERS[req.demo_user]
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires,
        "user": dict(zip(("id", "role", "display_name"), identity, strict=True)),
    }
