from fastapi import APIRouter, Depends

from app.core.errors import feature_disabled
from app.core.security import get_current_user

router = APIRouter(tags=["media"], dependencies=[Depends(get_current_user)])


@router.post("/tasks/{task_id}/media")
def upload_media(task_id: str):
    raise feature_disabled("ENABLE_MEDIA_UPLOAD", 4)


@router.post("/tasks/{task_id}/process")
def process_media(task_id: str):
    raise feature_disabled("ENABLE_MEDIA_PROCESSING", 5)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    raise feature_disabled("ENABLE_MEDIA_PROCESSING", 5)


@router.get("/media/{media_id}/stream")
def stream_media(media_id: str):
    raise feature_disabled("ENABLE_MEDIA_STREAMING", 4)
