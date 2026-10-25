import logging

from app.ai.schemas import ApprovedContext
from app.models.schemas import AskOut
from app.services.publication_service import active_release
from app.services.qa_matching import INSUFFICIENT_MSG

logger = logging.getLogger(__name__)


def ask(session, task_id, req, user, provider) -> AskOut:
    release = active_release(session, task_id)
    context = ApprovedContext(
        release_id=release.id,
        knowledge_units=release.knowledge_snapshot,
        evidence_ids={item["id"] for item in release.evidence_snapshot},
    )
    result = provider.answer_question(req.question, req.language, context)
    unit_ids = {unit["id"] for unit in release.knowledge_snapshot}
    evidence_ids = {item["id"] for item in release.evidence_snapshot}
    claims = []
    for claim in result.claims:
        if (
            claim.knowledge_unit_id not in unit_ids
            or not claim.evidence_ids
            or not set(claim.evidence_ids) <= evidence_ids
        ):
            logger.warning("qa claim rejected task_id=%s release_id=%s", task_id, release.id)
        else:
            claims.append(claim)
    status, missing = result.status, result.missing_information
    if status == "answered" and not claims:
        status, missing = "insufficient_evidence", [INSUFFICIENT_MSG]
    logger.info("qa task_id=%s release_id=%s status=%s", task_id, release.id, status)
    return AskOut(
        status=status,
        release_id=release.id,
        claims=claims,
        missing_information=missing,
        review_required=False,
    )
