import logging

from sqlalchemy import update

from app.core.errors import AppError
from app.database import new_id, utcnow
from app.models.entities import Clarification, Draft, Evidence
from app.models.schemas import ClarificationRespondOut
from app.services import knowledge_service

logger = logging.getLogger(__name__)


def respond(session, clarification_id, req, user, evidence_id=None, source_label="real"):
    clarification = session.get(Clarification, clarification_id)
    if clarification is None:
        raise AppError("CLARIFICATION_NOT_FOUND", "Clarification not found.", 404)
    if clarification.status != "pending":
        raise AppError("INVALID_STATE_TRANSITION", "Clarification is no longer pending.", 409)
    answer = req.answer.strip() if req.answer else None
    knowledge_update = req.knowledge_update
    if req.disposition == "answered" and not answer:
        raise AppError("INVALID_KNOWLEDGE_UPDATE", "An answered response requires an answer.", 422)
    if knowledge_update is not None and (
        req.disposition != "answered"
        or knowledge_update.knowledge_unit_id != clarification.knowledge_unit_id
        or not knowledge_update.fields.model_fields_set
    ):
        raise AppError("INVALID_KNOWLEDGE_UPDATE", "Invalid clarification knowledge update.", 422)
    draft = session.get(Draft, clarification.draft_id)
    knowledge_service.check_revision(session, draft, req.expected_draft_revision)
    response_evidence_id = None
    if answer:
        response_evidence_id = evidence_id or new_id("ev")
        session.add(
            Evidence(
                id=response_evidence_id,
                task_id=clarification.task_id,
                type="expert_response",
                author_id=user.id,
                author_label=user.display_name,
                content=answer,
                source_label=source_label,
            )
        )
        session.flush()
    revision = draft.revision
    if req.disposition == "answered":
        fields = knowledge_update.fields.model_dump(exclude_unset=True) if knowledge_update else {}
        units = []
        for unit in draft.knowledge_units:
            if unit["id"] == clarification.knowledge_unit_id:
                unit = knowledge_service.apply_field_updates(unit, fields, response_evidence_id)
                unit["evidence_ids"] = list(
                    dict.fromkeys([*unit["evidence_ids"], response_evidence_id])
                )
            units.append(unit)
        knowledge_service.bump_draft(
            session, draft, req.expected_draft_revision, units, user.id, "clarification"
        )
        revision = req.expected_draft_revision + 1
    result = session.execute(
        update(Clarification)
        .where(Clarification.id == clarification_id, Clarification.status == "pending")
        .values(
            status=req.disposition,
            answer=answer,
            evidence_id=response_evidence_id,
            answered_by=user.id,
            answered_at=utcnow(),
        )
    )
    if result.rowcount == 0:
        raise AppError("INVALID_STATE_TRANSITION", "Clarification is no longer pending.", 409)
    session.flush()
    logger.info(
        "clarification answered task_id=%s clarification_id=%s evidence_id=%s",
        clarification.task_id,
        clarification_id,
        response_evidence_id,
    )
    return ClarificationRespondOut(
        clarification_id=clarification_id,
        status=req.disposition,
        evidence_id=response_evidence_id,
        knowledge_unit_id=clarification.knowledge_unit_id,
        draft_revision=revision,
    )
