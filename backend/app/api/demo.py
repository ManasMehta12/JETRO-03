from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AppError, feature_disabled
from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.schemas import DemoResetOut, DemoResetRequest
from app.services import media_service
from app.services.seed_service import reset_demo

router = APIRouter(tags=["demo"])


@router.post("/demo/reset", response_model=DemoResetOut)
def reset(
    req: DemoResetRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_roles("reviewer"))],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not (settings.demo_mode and settings.enable_demo_reset):
        raise feature_disabled("ENABLE_DEMO_RESET")
    if req.scope == "attempts":
        raise AppError(
            "RESET_SCOPE_UNAVAILABLE",
            "Learner attempts are owned by the scenario engine; "
            "reset them through its reset interface.",
            400,
        )
    if req.confirm != "RESET_DEMO_DATA":
        raise AppError("CONFIRMATION_REQUIRED", "Confirm with RESET_DEMO_DATA.", 422)
    with session.begin():
        storage_keys = reset_demo(session, req.state)
    media_service.remove_stored_files(settings, storage_keys)
    return DemoResetOut(success=True, scope=req.scope, state=req.state)
