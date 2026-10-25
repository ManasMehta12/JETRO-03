from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SCHEMA_VERSION, get_db
from app.models.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    status, database = "ok", "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        status, database = "degraded", "unavailable"
    return HealthOut(
        status=status,
        database=database,
        app_env=settings.app_env,
        demo_mode=settings.demo_mode,
        ai_provider=settings.ai_provider,
        schema_version=SCHEMA_VERSION,
        features={
            name: getattr(settings, name)
            for name in type(settings).model_fields
            if name.startswith("enable_")
        },
    )
