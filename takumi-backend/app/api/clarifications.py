from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.schemas import ClarificationRespond, ClarificationRespondOut
from app.services import clarification_service

router = APIRouter(tags=["clarifications"])


@router.post("/clarifications/{clarification_id}/respond", response_model=ClarificationRespondOut)
def respond(
    clarification_id: str,
    req: ClarificationRespond,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    with session.begin():
        result = clarification_service.respond(session, clarification_id, req, user)
    return result
