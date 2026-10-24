from app.core.errors import AppError


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
