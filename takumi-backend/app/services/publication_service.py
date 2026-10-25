import hashlib
import json
import logging
from copy import deepcopy

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.database import new_id, utcnow
from app.models.entities import Draft, Evidence, Release, Task
from app.models.schemas import ReleaseOut, TrainingPack
from app.services.evidence_service import evidence_out

logger = logging.getLogger(__name__)
CONTENT_FIELDS = ("action", "cue", "interpretation", "decision", "exception")


def get_release(session, release_id):
    release = session.get(Release, release_id)
    if release is None:
        raise AppError("RELEASE_NOT_FOUND", "Release not found.", 404)
    return release


def active_release(session, task_id):
    task = session.get(Task, task_id)
    release = (
        session.get(Release, task.active_release_id) if task and task.active_release_id else None
    )
    if release is None or release.task_id != task_id:
        raise AppError("NO_ACTIVE_RELEASE", "No active release exists for this task.", 404)
    return release


def release_status(session, release):
    task = session.get(Task, release.task_id)
    return "active" if task.active_release_id == release.id else "superseded"


def release_out(session, release):
    return ReleaseOut(
        id=release.id,
        task_id=release.task_id,
        version=release.version,
        status=release_status(session, release),
        approved_by=release.approved_by,
        approved_at=release.approved_at,
        approval_note=release.approval_note,
        content_hash=release.content_hash,
        knowledge_units=release.knowledge_snapshot,
        evidence_items=release.evidence_snapshot,
    )


def training_pack(release):
    evidence_ids = {item["id"] for item in release.evidence_snapshot}
    for unit in release.knowledge_snapshot:
        referenced = set(unit["evidence_ids"])
        referenced.update(eid for ids in unit["field_evidence"].values() for eid in ids)
        if not referenced <= evidence_ids:
            logger.error("training pack evidence invariant failed release_id=%s", release.id)
            raise AppError("INTERNAL_ERROR", "Internal server error.", 500)
    return TrainingPack(
        schema_version="1.0",
        task_id=release.task_id,
        release_id=release.id,
        version=release.version,
        **release.task_snapshot,
        approved_by=release.approved_by,
        approved_at=release.approved_at,
        content_hash=release.content_hash,
        knowledge_units=release.knowledge_snapshot,
        evidence_items=release.evidence_snapshot,
    )


def publish(session, task_id, req, user, release_id=None):
    task = session.get(Task, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    draft = session.scalar(select(Draft).where(Draft.task_id == task_id))
    if draft is None:
        raise AppError("DRAFT_NOT_FOUND", "Draft not found.", 404)
    existing_query = select(Release).where(
        Release.task_id == task_id, Release.source_draft_revision == req.expected_revision
    )
    existing = session.scalar(existing_query)
    if draft.revision != req.expected_revision:
        raise AppError(
            "REVISION_CONFLICT",
            "Draft revision does not match.",
            409,
            {"expected": req.expected_revision, "actual": draft.revision},
        )
    if existing is not None:
        return existing, False

    issues = []
    referenced = set()
    for unit in draft.knowledge_units:
        if not unit.get("action") or not unit["action"].strip():
            issues.append({"knowledge_unit_id": unit["id"], "problem": "MISSING_ACTION"})
        for field in CONTENT_FIELDS:
            ids = unit.get("field_evidence", {}).get(field, [])
            if unit.get(field) is not None and not ids:
                issues.append(
                    {"knowledge_unit_id": unit["id"], "problem": f"UNSUPPORTED_FIELD:{field}"}
                )
        unit_ids = set(unit.get("evidence_ids", []))
        unit_ids.update(eid for ids in unit.get("field_evidence", {}).values() for eid in ids)
        for evidence_id in sorted(unit_ids):
            evidence = session.get(Evidence, evidence_id)
            if evidence is None or evidence.task_id != task_id:
                issues.append(
                    {"knowledge_unit_id": unit["id"], "problem": f"INVALID_EVIDENCE:{evidence_id}"}
                )
        referenced.update(unit_ids)
    if not draft.knowledge_units:
        issues.append({"knowledge_unit_id": None, "problem": "EMPTY_DRAFT"})
    if issues:
        raise AppError("PUBLICATION_BLOCKED", "Draft cannot be published.", 409, {"issues": issues})

    units = deepcopy(draft.knowledge_units)
    for unit in units:
        unit["review_status"] = "approved"
    evidence_items = [
        evidence_out(session.get(Evidence, eid)).model_dump(mode="json")
        for eid in sorted(referenced)
    ]
    content = json.dumps(
        {"knowledge_units": units, "evidence_items": evidence_items},
        sort_keys=True,
        separators=(",", ":"),
    )
    version = (
        session.scalar(select(func.max(Release.version)).where(Release.task_id == task_id)) or 0
    ) + 1
    release = Release(
        id=release_id or new_id("release"),
        task_id=task_id,
        version=version,
        source_draft_revision=draft.revision,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        approved_by=user.id,
        approval_note=req.approval_note,
        approved_at=utcnow(),
        task_snapshot={
            field: getattr(task, field)
            for field in ("title", "equipment", "language", "source_label")
        },
        knowledge_snapshot=units,
        evidence_snapshot=evidence_items,
    )
    try:
        with session.begin_nested():
            session.add(release)
            session.flush()
    except IntegrityError:
        existing = session.scalar(existing_query)
        if existing is None:
            raise
        return existing, False
    task.active_release_id = release.id
    task.status = "published"
    task.updated_at = utcnow()
    session.flush()
    logger.info(
        "release published task_id=%s release_id=%s version=%s", task_id, release.id, version
    )
    return release, True
