"""Saved course sources and expert notes, resolved on the server for analysis."""

import hashlib
import json

from sqlalchemy import select

from app.core.errors import AppError
from app.database import utcnow
from app.models.entities import MediaAsset, Task
from app.models.studio import StudioCourseContent
from app.services import studio_service


def content(session, task_id):
    saved = session.get(StudioCourseContent, task_id)
    video = session.scalar(
        select(MediaAsset)
        .where(MediaAsset.task_id == task_id)
        .order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
    )
    return {
        "version": saved.version if saved else 0,
        "script_text": saved.script_text if saved else "",
        "script_filename": saved.script_filename if saved else "",
        "review_notes": saved.review_notes if saved else "",
        "video": {
            "id": video.id,
            "filename": video.original_filename,
            "duration_ms": video.duration_ms,
            "sha256": video.sha256,
        }
        if video
        else None,
        "available": bool(video or (saved and saved.script_text.strip())),
    }


def save(session, task_id, req, user):
    if session.get(Task, task_id) is None:
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    saved = session.get(StudioCourseContent, task_id)
    version = saved.version if saved else 0
    if req.expected_version != version:
        raise AppError(
            "REVISION_CONFLICT",
            "Course sources changed. Refresh before saving.",
            409,
            {"expected": req.expected_version, "actual": version},
        )
    if saved is None:
        saved = StudioCourseContent(task_id=task_id, updated_by=user.id)
        session.add(saved)
    updates = req.model_dump(exclude_unset=True, exclude={"expected_version"})
    for field, value in updates.items():
        setattr(saved, field, value)
    saved.version = version + 1
    saved.updated_at, saved.updated_by = utcnow(), user.id
    session.flush()
    studio_service.audit(
        session,
        task_id,
        user,
        "course_sources_updated",
        source_version=saved.version,
        fields=list(updates),
    )
    return content(session, task_id)


def snapshot(session, task_id, include_review_notes):
    data = content(session, task_id)
    manifest = {
        "version": data["version"],
        "video": data["video"],
        "script_filename": data["script_filename"],
        "include_review_notes": include_review_notes,
    }
    source = ""
    if data["script_text"].strip():
        source += (
            f"[Uploaded course script: {data['script_filename'] or 'saved script'}]\n"
            f"{data['script_text']}\n\n"
        )
    if include_review_notes and data["review_notes"].strip():
        source += f"[Expert review notes]\n{data['review_notes']}\n\n"
    if data["video"]:
        video = data["video"]
        source += (
            f"[Uploaded course video: {video['filename']}; media_id={video['id']}; "
            f"sha256={video['sha256']}]\n"
        )
    manifest["input_hash"] = hashlib.sha256(
        json.dumps({"manifest": manifest, "source": source}, sort_keys=True).encode()
    ).hexdigest()
    return source, manifest


def check_snapshot(session, task_id, manifest):
    _, current = snapshot(session, task_id, manifest["include_review_notes"])
    if current["input_hash"] != manifest["input_hash"]:
        raise AppError(
            "ANALYSIS_STALE",
            "Course video, script or review notes changed. Run extraction again.",
            409,
        )
