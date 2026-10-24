from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.database import get_db
from app.models.schemas import EvidenceItemOut
from app.services import evidence_service

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{evidence_id}", response_model=EvidenceItemOut)
def get_evidence(
    evidence_id: str,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    return evidence_service.get_evidence(session, evidence_id, user)
