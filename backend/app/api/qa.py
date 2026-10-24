from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.base import KnowledgeAIProvider, ai_provider
from app.config import Settings, get_settings
from app.core.errors import feature_disabled
from app.core.security import CurrentUser, get_current_user
from app.database import get_db
from app.models.schemas import AskOut, AskRequest
from app.services import qa_service

router = APIRouter(tags=["qa"])


@router.post("/tasks/{task_id}/ask", response_model=AskOut)
def ask(
    task_id: str,
    req: AskRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    provider: Annotated[KnowledgeAIProvider, Depends(ai_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not settings.enable_grounded_qa:
        raise feature_disabled("ENABLE_GROUNDED_QA")
    return qa_service.ask(session, task_id, req, user, provider)
