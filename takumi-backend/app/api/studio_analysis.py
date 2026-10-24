from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import CurrentUser, require_roles
from app.database import get_db
from app.models.entities import Task
from app.models.schemas import RequestModel
from app.services import studio_analysis_service as service

router = APIRouter(prefix="/studio/tasks/{task_id}/analysis", tags=["Studio AI diagnosis"])
DB = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StudioUser = Annotated[CurrentUser, Depends(require_roles("expert", "reviewer", "admin"))]


class AnalysisRequest(RequestModel):
    expected_revision: int = Field(ge=1)
    mode: Literal["live", "rehearsal"] = "live"
    source_notes: str | None = Field(default=None, min_length=1, max_length=20000, pattern=r"\S")


class ApproveRequest(RequestModel):
    expected_revision: int = Field(ge=1)
    proposal_ids: list[str] = Field(min_length=1, max_length=12)
    defer_unanswered: bool = False
    approval_note: str = Field(min_length=1, max_length=2000, pattern=r"\S")


@router.get("/config")
def config(task_id: str, user: StudioUser, settings: SettingsDep, session: DB):
    if session.get(Task, task_id) is None:
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    return service.configuration(settings, session, task_id)


@router.get("/latest")
def latest(task_id: str, user: StudioUser, session: DB):
    return service.output(service.get_run(session, task_id))


@router.get("/{run_id}")
def status(task_id: str, run_id: str, user: StudioUser, session: DB):
    return service.output(service.get_run(session, task_id, run_id))


@router.post("")
def analyze(
    task_id: str, req: AnalysisRequest, user: StudioUser, settings: SettingsDep, request: Request
):
    return service.analyze(request.app.state.sessionmaker, settings, task_id, req, user)


@router.post("/{run_id}/publish")
def publish(
    task_id: str,
    run_id: str,
    req: ApproveRequest,
    user: StudioUser,
    session: DB,
    settings: SettingsDep,
):
    with session.begin():
        return service.approve_publish(session, task_id, run_id, req, user, settings)
