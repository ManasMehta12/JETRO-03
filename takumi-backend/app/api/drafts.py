from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.schemas import DraftOut, DraftPatch, DraftPatchOut
from app.services import knowledge_service

router = APIRouter(tags=["drafts"])


@router.get("/tasks/{task_id}/draft", response_model=DraftOut)
def get_draft(
    task_id: str,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    return knowledge_service.read_draft(session, task_id)


@router.patch("/tasks/{task_id}/draft", response_model=DraftPatchOut)
def patch_draft(
    task_id: str,
    req: DraftPatch,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    with session.begin():
        result = knowledge_service.patch_draft(session, task_id, req, user)
    return result
