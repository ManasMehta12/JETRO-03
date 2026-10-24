"""Revision-bound tutor authorization; all writes remain inside caller transactions."""

import hashlib
import json

from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import DEMO_USERS
from app.database import new_id
from app.models.entities import Clarification, DraftRevision, Evidence, Task
from app.models.schemas import PublishRequest, TaskOut
from app.models.studio import StudioAudit, StudioAuthorization, StudioEvaluation
from app.services import knowledge_service, publication_service
from app.services.evidence_service import evidence_out


def row_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def audit(session, task_id, user, action, **details):
    session.add(
        StudioAudit(
            id=new_id("audit"), task_id=task_id, actor_id=user.id, action=action, details=details
        )
    )
    session.flush()


def inspect(session, task_id):
    draft = knowledge_service.get_draft(session, task_id)
    evidence = session.scalars(select(Evidence).where(Evidence.task_id == task_id)).all()
    evidence_map = {item.id: item for item in evidence}
    issues = []
    referenced = set()
    for unit in draft.knowledge_units:
        if not unit.get("action", "").strip():
            issues.append({"knowledge_unit_id": unit["id"], "problem": "MISSING_ACTION"})
        for field in publication_service.CONTENT_FIELDS:
            ids = unit.get("field_evidence", {}).get(field, [])
            if unit.get(field) is not None and not ids:
                issues.append(
                    {"knowledge_unit_id": unit["id"], "problem": f"UNSUPPORTED_FIELD:{field}"}
                )
        ids = set(unit.get("evidence_ids", []))
        ids.update(eid for values in unit.get("field_evidence", {}).values() for eid in values)
        referenced.update(ids)
        for eid in sorted(ids):
            if eid not in evidence_map:
                issues.append(
                    {"knowledge_unit_id": unit["id"], "problem": f"INVALID_EVIDENCE:{eid}"}
                )
    if not draft.knowledge_units:
        issues.append({"knowledge_unit_id": None, "problem": "EMPTY_DRAFT"})
    clarifications = session.scalars(
        select(Clarification).where(Clarification.task_id == task_id)
    ).all()
    for clarification in clarifications:
        if clarification.status == "pending":
            issues.append(
                {
                    "knowledge_unit_id": clarification.knowledge_unit_id,
                    "problem": f"UNRESOLVED_CLARIFICATION:{clarification.id}",
                }
            )
    content = {
        "clarifications": [
            {"id": row.id, "status": row.status, "answer": row.answer}
            for row in sorted(clarifications, key=lambda row: row.id)
        ],
        "units": draft.knowledge_units,
        "evidence": [
            evidence_out(evidence_map[eid]).model_dump(mode="json")
            for eid in sorted(referenced)
            if eid in evidence_map
        ],
    }
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return draft, digest, issues


def evaluate(session, task_id, expected_revision, user):
    draft, digest, issues = inspect(session, task_id)
    knowledge_service.check_revision(session, draft, expected_revision)
    evaluation = StudioEvaluation(
        id=new_id("evaluation"),
        task_id=task_id,
        revision=draft.revision,
        content_hash=digest,
        passed=not issues,
        issues=issues,
        evaluated_by=user.id,
    )
    session.add(evaluation)
    session.flush()
    audit(
        session,
        task_id,
        user,
        "evaluated",
        evaluation_id=evaluation.id,
        revision=draft.revision,
        passed=evaluation.passed,
        issues=issues,
    )
    return row_dict(evaluation)


def authorize(session, task_id, req, user):
    draft, digest, issues = inspect(session, task_id)
    evaluation = session.get(StudioEvaluation, req.evaluation_id)
    if evaluation is None or evaluation.task_id != task_id:
        raise AppError("EVALUATION_NOT_FOUND", "Evaluation not found.", 404)
    if not evaluation.passed or issues:
        raise AppError("EVALUATION_FAILED", "Resolve evaluation issues before authorization.", 409)
    if evaluation.revision != draft.revision or evaluation.content_hash != digest:
        raise AppError("EVALUATION_STALE", "Evaluate the current draft before authorization.", 409)
    if not any(
        identity[0] == req.expert_id and identity[1] == "expert" for identity in DEMO_USERS.values()
    ):
        raise AppError("INVALID_EXPERT", "Select a registered expert identity.", 422)
    grant = StudioAuthorization(
        id=new_id("authorization"),
        task_id=task_id,
        evaluation_id=evaluation.id,
        revision=draft.revision,
        content_hash=digest,
        expert_id=req.expert_id,
        authorized_by=user.id,
        note=req.note.strip(),
        release_id=None,
    )
    session.add(grant)
    session.flush()
    audit(
        session,
        task_id,
        user,
        "authorized",
        authorization_id=grant.id,
        evaluation_id=evaluation.id,
        revision=draft.revision,
        expert_id=req.expert_id,
        note=grant.note,
    )
    return {**row_dict(grant), "status": "authorized"}


def publish_release(session, task_id, req, user, settings):
    draft, digest, issues = inspect(session, task_id)
    knowledge_service.check_revision(session, draft, req.expected_revision)
    grant = None
    if not settings.demo_mode:
        grant = session.scalar(
            select(StudioAuthorization)
            .where(
                StudioAuthorization.task_id == task_id,
                StudioAuthorization.revision == draft.revision,
                StudioAuthorization.content_hash == digest,
                StudioAuthorization.expert_id == user.id,
            )
            .order_by(StudioAuthorization.created_at.desc())
        )
        if grant is None:
            raise AppError(
                "AUTHORIZATION_REQUIRED",
                "A tutor administrator must authorize this evaluated revision for you.",
                403,
            )
    if issues:
        raise AppError("PUBLICATION_BLOCKED", "Draft cannot be published.", 409, {"issues": issues})
    evaluation = session.scalar(
        select(StudioEvaluation)
        .where(
            StudioEvaluation.task_id == task_id,
            StudioEvaluation.revision == draft.revision,
            StudioEvaluation.content_hash == digest,
            StudioEvaluation.passed.is_(True),
        )
        .order_by(StudioEvaluation.created_at.desc())
    )
    if evaluation is None:
        raise AppError(
            "EVALUATION_REQUIRED", "Evaluate the current draft successfully before publishing.", 409
        )
    release, created = publication_service.publish(
        session,
        task_id,
        PublishRequest(expected_revision=req.expected_revision, approval_note=req.approval_note),
        user,
    )
    if grant is not None and grant.release_id is None:
        grant.release_id = release.id
    if created:
        audit(
            session,
            task_id,
            user,
            "published",
            authorization_id=grant.id if grant else None,
            evaluation_id=evaluation.id,
            revision=draft.revision,
            release_id=release.id,
            approval_note=req.approval_note,
            approval_policy="demo_human_review" if settings.demo_mode else "tutor_authorization",
        )
    return release, created


def publish(session, task_id, req, user, settings):
    release, _ = publish_release(session, task_id, req, user, settings)
    return publication_service.release_out(session, release)


def overview(session, task_id):
    task = session.get(Task, task_id)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    draft, digest, _ = inspect(session, task_id)
    evaluation = session.scalar(
        select(StudioEvaluation)
        .where(StudioEvaluation.task_id == task_id)
        .order_by(StudioEvaluation.created_at.desc())
    )
    grant = session.scalar(
        select(StudioAuthorization)
        .where(StudioAuthorization.task_id == task_id)
        .order_by(StudioAuthorization.created_at.desc())
    )
    authorization = row_dict(grant) if grant else None
    if authorization:
        authorization["status"] = (
            "stale"
            if grant.revision != draft.revision or grant.content_hash != digest
            else "published"
            if grant.release_id
            else "authorized"
        )
    events = [
        row_dict(event)
        for event in session.scalars(
            select(StudioAudit)
            .where(StudioAudit.task_id == task_id)
            .order_by(StudioAudit.created_at.desc())
        ).all()
    ]
    for revision in session.scalars(
        select(DraftRevision).where(DraftRevision.draft_id == draft.id)
    ).all():
        events.append(
            {
                "id": f"revision_{revision.id}",
                "task_id": task_id,
                "action": "draft_updated",
                "actor_id": revision.actor_id,
                "details": {"revision": revision.revision, "reason": revision.reason},
                "created_at": revision.created_at,
            }
        )
    for clarification in session.scalars(
        select(Clarification).where(Clarification.task_id == task_id)
    ).all():
        if clarification.answered_at:
            events.append(
                {
                    "id": f"clarification_{clarification.id}",
                    "task_id": task_id,
                    "action": "clarification_resolved",
                    "actor_id": clarification.answered_by,
                    "details": {
                        "clarification_id": clarification.id,
                        "status": clarification.status,
                        "answer": clarification.answer,
                        "evidence_id": clarification.evidence_id,
                    },
                    "created_at": clarification.answered_at,
                }
            )
    events.sort(key=lambda event: event["created_at"].isoformat(), reverse=True)
    active = (
        publication_service.active_release(session, task_id) if task.active_release_id else None
    )
    return {
        "task": TaskOut.model_validate(task),
        "draft": knowledge_service.read_draft(session, task_id),
        "evidence": [
            evidence_out(row)
            for row in session.scalars(select(Evidence).where(Evidence.task_id == task_id)).all()
        ],
        "evaluation": {
            **row_dict(evaluation),
            "stale": evaluation.revision != draft.revision or evaluation.content_hash != digest,
        }
        if evaluation
        else None,
        "authorization": authorization,
        "audit": events,
        "active_release": publication_service.release_out(session, active) if active else None,
        "evaluation_scope": (
            "Evidence coverage and release consistency checks. "
            "Tutor review is required to judge technical accuracy."
        ),
    }
