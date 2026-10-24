from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import feature_disabled
from app.core.security import (
    CurrentUser,
    bearer,
    get_current_user,
    require_roles,
    verify_playback_token,
)
from app.database import get_db
from app.models.schemas import MediaOut
from app.services import media_service, task_service

router = APIRouter(tags=["media"])


@router.post("/tasks/{task_id}/media", status_code=201, response_model=MediaOut)
def upload_media(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
    file: Annotated[UploadFile, File()],
):
    if not settings.enable_media_upload:
        raise feature_disabled("ENABLE_MEDIA_UPLOAD", 4)
    with session.begin():
        task_service.get_task(session, task_id, user)
    received = media_service.receive_upload(settings, file)
    media = None
    try:
        with session.begin():
            media = media_service.save_media(session, settings, task_id, user, received)
    except BaseException:
        media_service.discard(settings, received, media.storage_key if media is not None else None)
        raise
    return media_service.media_out(media, settings, request.app.state.signing_key, user)


@router.get("/media/{media_id}", response_model=MediaOut)
def get_media(
    media_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not settings.enable_media_streaming:
        raise feature_disabled("ENABLE_MEDIA_STREAMING", 4)
    with session.begin():
        media = media_service.get_visible_media(session, media_id, user)
    return media_service.media_out(media, settings, request.app.state.signing_key, user)


@router.post("/tasks/{task_id}/process")
def process_media(
    task_id: str,
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    raise feature_disabled("ENABLE_MEDIA_PROCESSING", 5)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    raise feature_disabled("ENABLE_MEDIA_PROCESSING", 5)


@router.get("/media/{media_id}/stream")
def stream_media(
    media_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    token: str | None = Query(None),
):
    if not settings.enable_media_streaming:
        raise feature_disabled("ENABLE_MEDIA_STREAMING", 4)
    user = (
        verify_playback_token(token, media_id, request.app.state.signing_key)
        if token is not None
        else get_current_user(request, credentials)
    )
    with session.begin():
        media = media_service.get_visible_media(session, media_id, user)
        path = media_service.media_path(settings, media)
    return FileResponse(path, media_type=media.mime_type)
