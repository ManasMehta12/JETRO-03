from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import feature_disabled
from app.core.security import CurrentUser, get_current_user, require_roles
from app.database import get_db
from app.models.schemas import PublishOut, PublishRequest, ReleaseOut, TrainingPack
from app.services import publication_service

router = APIRouter(tags=["releases"])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/tasks/{task_id}/publish", response_model=PublishOut, status_code=201)
def publish(
    task_id: str,
    req: PublishRequest,
    response: Response,
    session: DB,
    user: Annotated[CurrentUser, Depends(require_roles("reviewer"))],
):
    with session.begin():
        release, created = publication_service.publish(session, task_id, req, user)
    response.status_code = 201 if created else 200
    return PublishOut(
        release_id=release.id,
        task_id=release.task_id,
        version=release.version,
        status=publication_service.release_status(session, release),
        approved_by=release.approved_by,
        content_hash=release.content_hash,
    )


@router.get("/tasks/{task_id}/release", response_model=ReleaseOut)
def active_release(task_id: str, session: DB, user: User):
    return publication_service.release_out(
        session, publication_service.active_release(session, task_id)
    )


@router.get("/releases/{release_id}", response_model=ReleaseOut)
def get_release(release_id: str, session: DB, user: User):
    return publication_service.release_out(
        session, publication_service.get_release(session, release_id)
    )


@router.get("/releases/{release_id}/training-pack", response_model=TrainingPack)
def training_pack(
    release_id: str,
    session: DB,
    user: User,
    settings: Annotated[Settings, Depends(get_settings)],
):
    if not settings.enable_training_pack_export:
        raise feature_disabled("ENABLE_TRAINING_PACK_EXPORT")
    return publication_service.training_pack(publication_service.get_release(session, release_id))
