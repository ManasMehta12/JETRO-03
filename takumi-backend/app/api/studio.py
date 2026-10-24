from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.schemas import PublishRequest, RequestModel
from app.services import studio_analysis_service, studio_service

router = APIRouter(prefix="/studio", tags=["expert studio administration"])
DB = Annotated[Session, Depends(get_db)]
StudioUser = Annotated[CurrentUser, Depends(require_roles("expert", "reviewer", "admin"))]
Admin = Annotated[CurrentUser, Depends(require_roles("admin"))]
Expert = Annotated[CurrentUser, Depends(require_roles("expert", "admin"))]


class EvaluationRequest(RequestModel):
    expected_revision: int = Field(ge=1)


class AuthorizationRequest(RequestModel):
    evaluation_id: str = Field(min_length=1)
    expert_id: str = Field(default="expert_001", min_length=1)
    note: str = Field(min_length=1, max_length=2000, pattern=r"\S")


@router.get("/workspace")
def workspace(session: DB, user: StudioUser, settings: Annotated[Settings, Depends(get_settings)]):
    return studio_analysis_service.workspace(session, settings, user)


@router.get("/tasks/{task_id}")
def overview(task_id: str, session: DB, user: StudioUser):
    return studio_service.overview(session, task_id)


@router.post("/tasks/{task_id}/evaluate")
def evaluate(task_id: str, req: EvaluationRequest, session: DB, user: StudioUser):
    with session.begin():
        result = studio_service.evaluate(session, task_id, req.expected_revision, user)
    return result


@router.post("/tasks/{task_id}/authorize")
def authorize(task_id: str, req: AuthorizationRequest, session: DB, user: Admin):
    with session.begin():
        result = studio_service.authorize(session, task_id, req, user)
    return result


@router.post("/tasks/{task_id}/publish")
def publish(
    task_id: str,
    req: PublishRequest,
    session: DB,
    user: Expert,
    settings: Annotated[Settings, Depends(get_settings)],
):
    with session.begin():
        result = studio_service.publish(session, task_id, req, user, settings)
    return result
