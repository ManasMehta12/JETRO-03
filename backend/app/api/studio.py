from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AppError, feature_disabled
from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.schemas import PublishRequest, RequestModel
from app.services import (
    media_service,
    studio_analysis_service,
    studio_content_service,
    studio_reset_service,
    studio_service,
)

router = APIRouter(prefix="/studio", tags=["expert studio administration"])
DB = Annotated[Session, Depends(get_db)]
StudioUser = Annotated[CurrentUser, Depends(require_roles("expert", "reviewer", "admin"))]
Admin = Annotated[CurrentUser, Depends(require_roles("admin"))]
Expert = Annotated[CurrentUser, Depends(require_roles("expert", "admin"))]


class EvaluationRequest(RequestModel):
    expected_revision: int = Field(ge=1)


class ResetRequest(EvaluationRequest):
    confirm: str


class CourseContentRequest(RequestModel):
    expected_version: int = Field(ge=0)
    script_text: str = Field(default="", max_length=20000)
    script_filename: str = Field(default="", max_length=255)
    review_notes: str = Field(default="", max_length=10000)


@router.patch("/tasks/{task_id}/course-content")
def save_course_content(task_id: str, req: CourseContentRequest, session: DB, user: Expert):
    with session.begin():
        return studio_content_service.save(session, task_id, req, user)


@router.post("/tasks/{task_id}/reset")
def reset(
    task_id: str,
    req: ResetRequest,
    session: DB,
    user: Expert,
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not (settings.demo_mode and settings.enable_demo_reset):
        raise feature_disabled("ENABLE_DEMO_RESET")
    if req.confirm != "RESET_EXPERT_DATA":
        raise AppError("CONFIRMATION_REQUIRED", "Confirm with RESET_EXPERT_DATA.", 422)
    with session.begin():
        storage_keys = studio_reset_service.reset(session, task_id, req.expected_revision)
    media_service.remove_stored_files(settings, storage_keys)
    return {"success": True, "task_id": task_id}


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
