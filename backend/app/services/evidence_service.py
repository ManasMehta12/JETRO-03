from sqlalchemy import select

from app.core.errors import AppError
from app.models.entities import Evidence, Release
from app.models.schemas import EvidenceItemOut


def evidence_out(evidence) -> EvidenceItemOut:
    return EvidenceItemOut(
        id=evidence.id,
        task_id=evidence.task_id,
        type=evidence.type,
        author=evidence.author_label,
        author_id=evidence.author_id,
        content=evidence.content,
        media_id=evidence.media_id,
        start_ms=evidence.start_ms,
        end_ms=evidence.end_ms,
        source_label=evidence.source_label,
        created_at=evidence.created_at,
    )


def validate_evidence_items(items, task_id, media_duration_ms: int | None = None):
    seen = set()
    for item in items:
        item = item.model_dump() if hasattr(item, "model_dump") else item
        evidence_id = item.get("id")
        problem = None
        if evidence_id in seen:
            problem = "Duplicate evidence id."
        elif item.get("type") not in {"video_segment", "expert_response", "reviewer_correction"}:
            problem = "Unsupported evidence type."
        elif item.get("source_label") not in {"real", "illustrative"}:
            problem = "Unsupported source label."
        elif item.get("media_id") is not None:
            problem = "Media references are not available in V1."
        elif item.get("type") == "video_segment":
            start, end = item.get("start_ms"), item.get("end_ms")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end:
                problem = "Invalid video evidence interval."
            elif media_duration_ms is not None and end > media_duration_ms:
                problem = "Video evidence interval exceeds media duration."
        if problem:
            raise AppError("INVALID_EVIDENCE", problem, 422, {"evidence_id": evidence_id})
        seen.add(evidence_id)


def get_evidence(session, evidence_id, user):
    evidence = session.get(Evidence, evidence_id)
    if evidence is not None and user.role == "apprentice":
        snapshots = session.scalars(
            select(Release.evidence_snapshot).where(Release.task_id == evidence.task_id)
        )
        if not any(item["id"] == evidence_id for snapshot in snapshots for item in snapshot):
            evidence = None
    if evidence is None:
        raise AppError("EVIDENCE_NOT_FOUND", "Evidence not found.", 404)
    return evidence_out(evidence)
