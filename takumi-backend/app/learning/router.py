from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import CurrentUser, issue_playback_token, require_roles
from app.database import get_db
from app.learning import service
from app.learning.schemas import Answer, Completion, Heartbeat, Playground

router = APIRouter(prefix="/learning", tags=["learning"])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[CurrentUser, Depends(require_roles("apprentice"))]


def get_course_settings(session: DB, settings: Annotated[Settings, Depends(get_settings)]):
    with session.begin():
        return service.video_settings(session, settings)


Config = Annotated[Settings, Depends(get_course_settings)]


@router.get("/course")
def get_course(request: Request, session: DB, user: User, settings: Config):
    result = service.course(session, settings)
    if settings.enable_media_streaming:
        video = service.course_video(session)
        if video is not None:
            token, _ = issue_playback_token(video.id, user, request.app.state.signing_key)
            result["video_url"] = f"/api/v1/media/{video.id}/stream?token={token}"
    return result


@router.get("/progress")
def get_progress(session: DB, user: User, settings: Config):
    with session.begin():
        return service.progress(service.enrollment(session, user, settings), settings)


@router.post("/playback")
def playback(session: DB, user: User, settings: Config):
    with session.begin():
        return service.start_playback(service.enrollment(session, user, settings), settings)


@router.post("/playback/{playback_id}")
def heartbeat(playback_id: str, req: Heartbeat, session: DB, user: User, settings: Config):
    with session.begin():
        row = service.enrollment(session, user, settings)
        return service.heartbeat(row, playback_id, req.position_seconds, settings)


@router.post("/playground")
def playground(req: Playground, session: DB, user: User, settings: Config):
    with session.begin():
        return service.submit_playground(service.enrollment(session, user, settings), req, settings)


@router.post("/interview")
def interview(session: DB, user: User, settings: Config):
    with session.begin():
        return service.start_interview(
            session, service.enrollment(session, user, settings), settings
        )


@router.post("/interview/answers")
def answer(req: Answer, session: DB, user: User, settings: Config):
    with session.begin():
        return service.answer(service.enrollment(session, user, settings), req, settings)


@router.post("/complete")
def complete(req: Completion, session: DB, user: User, settings: Config):
    with session.begin():
        row = service.enrollment(session, user, settings)
        return service.complete(session, row, req.stage, settings)


@router.post("/reset")
def reset_progress(session: DB, user: User, settings: Config):
    with session.begin():
        row = service.enrollment(session, user, settings)
        return service.reset_progress(session, row, settings)
