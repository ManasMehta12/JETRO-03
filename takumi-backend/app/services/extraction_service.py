from sqlalchemy import select

from app.ai.base import ProviderError
from app.ai.schemas import VideoExtractionResult
from app.database import new_id, utcnow
from app.models.entities import Clarification, Draft, DraftRevision, Evidence, MediaAsset, Task
from app.models.schemas import KnowledgeUnit
from app.services.evidence_service import interval_problem, validate_evidence_items
from app.services.gap_detection import detect_gaps


def build_draft_content(
    result: VideoExtractionResult, media: MediaAsset, author_label: str
) -> tuple[list[dict], list[dict], list[str]]:
    units, evidence_rows, warnings = [], [], []
    intervals = {}
    for index, step in enumerate(result.steps, 1):
        fields = {
            name: (getattr(step, name) or "").strip() or None
            for name in ("action", "cue", "interpretation", "decision", "exception")
        }
        if fields["action"] is None:
            warnings.append(f"step {index}: empty action dropped")
            continue
        problem = interval_problem(step.start_ms, step.end_ms, media.duration_ms)
        evidence_ids = []
        if problem:
            warnings.append(
                f"INVALID_EVIDENCE_INTERVAL step {index} "
                f"({step.start_ms}-{step.end_ms} ms): {problem}"
            )
        else:
            interval = (step.start_ms, step.end_ms)
            if interval not in intervals:
                evidence_id = new_id("ev")
                intervals[interval] = evidence_id
                description = (step.evidence_description or "").strip() or fields["action"]
                evidence_rows.append(
                    dict(
                        id=evidence_id,
                        type="video_segment",
                        author_id="ai_extraction",
                        author_label=author_label,
                        content=(
                            f"[AI-extracted, unreviewed; source: {step.source_modality}] "
                            f"{description}"
                        ),
                        media_id=media.id,
                        start_ms=step.start_ms,
                        end_ms=step.end_ms,
                        source_label="real",
                    )
                )
            evidence_ids = [intervals[interval]]
        if media.audio_codec is None and step.source_modality != "visual":
            warnings.append(
                f"step {index}: reports spoken content but the recording has no audio track"
            )
        units.append(
            KnowledgeUnit.model_validate(
                dict(
                    id=new_id("ku"),
                    **fields,
                    evidence_ids=evidence_ids,
                    field_evidence={
                        name: evidence_ids for name, value in fields.items() if value is not None
                    }
                    if evidence_ids
                    else {},
                    review_status="draft",
                )
            ).model_dump()
        )
    warnings.extend(f"model: {warning}" for warning in result.processing_warnings)
    if not units:
        raise ProviderError("AI_RESPONSE_INVALID", "Extraction contained no usable steps.", True)
    validate_evidence_items(evidence_rows, media.task_id, media.duration_ms, media.id)
    return units, evidence_rows, warnings


def persist_extraction(session, job, media, units, evidence_rows, warnings) -> str:
    if session.scalar(select(Draft.id).where(Draft.task_id == job.task_id)):
        raise ProviderError(
            "DRAFT_ALREADY_EXISTS", "A draft was created for this task while processing.", False
        )
    for row in evidence_rows:
        session.add(Evidence(**row, task_id=job.task_id, created_at=utcnow()))
    draft = Draft(
        id=new_id("draft"),
        task_id=job.task_id,
        revision=1,
        status="draft",
        knowledge_units=units,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(draft)
    session.flush()
    session.add(
        DraftRevision(
            draft_id=draft.id,
            revision=1,
            knowledge_units=units,
            actor_id=job.requested_by,
            reason="extraction",
            created_at=utcnow(),
        )
    )
    for candidate in detect_gaps(units):
        session.add(
            Clarification(
                id=new_id("clar"),
                task_id=job.task_id,
                draft_id=draft.id,
                **candidate.model_dump(),
                status="pending",
                created_at=utcnow(),
            )
        )
    task = session.get(Task, job.task_id)
    task.status = "draft"
    task.updated_at = utcnow()
    session.flush()
    return draft.id
