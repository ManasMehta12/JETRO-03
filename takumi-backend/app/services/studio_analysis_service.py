import hashlib
import json
import logging
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select

from app.ai.base import ProviderError
from app.ai.fixture_provider import FIXTURE_PATH
from app.ai.studio_analysis import StudioAgents
from app.core.errors import AppError
from app.database import new_id, utcnow
from app.models.analysis import StudioAnalysisRun
from app.models.entities import Clarification, Evidence, Task
from app.models.schemas import PublishRequest
from app.services import knowledge_service, publication_service, studio_service

logger = logging.getLogger(__name__)


def demo_source():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["studio_analysis"]


def configuration(settings, session=None, task_id=None):
    live = bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip())
    task = session.get(Task, task_id) if session is not None and task_id else None
    evidence = (
        session.scalars(
            select(Evidence)
            .where(Evidence.task_id == task_id)
            .order_by(Evidence.created_at, Evidence.id)
        ).all()
        if task is not None
        else []
    )
    return {
        "enabled": settings.enable_studio_ai_analysis,
        "mode": "live" if live else "unconfigured",
        "provider": "gemini",
        "model": settings.gemini_model or settings.studio_ai_model,
        "source_notes": "\n\n".join(
            f"[{item.id}; {item.author_label}; {item.source_label}]\n{item.content}"
            for item in evidence
            if item.content
        )[:20000],
        "source_label": task.source_label if task else None,
        "source_kind": "stored_evidence" if evidence else "expert_notes_required",
        "rehearsal_available": settings.demo_mode,
        "rehearsal_source_notes": demo_source()["source_notes"] if settings.demo_mode else None,
        "agent_roles": [
            {"stage": "extracting", "label": "Extract source facts"},
            {"stage": "proposing", "label": "Propose tacit patches"},
            {"stage": "evaluating", "label": "Evaluate source support"},
        ],
        "notice": (
            "Three live Gemini agents analyze source notes. Human approval is required."
            if live
            else "Live AI requires GEMINI_API_KEY in backend/.env and a backend restart. "
            "No AI results will be simulated automatically."
        ),
    }


def workspace(session, settings, user):
    from app.learning.service import active_release

    task, _ = active_release(session)
    if task is None:
        raise AppError("TASK_NOT_FOUND", "No task is connected to the apprentice course.", 404)
    try:
        latest = output(get_run(session, task.id))
    except AppError as exc:
        if exc.code != "ANALYSIS_NOT_FOUND":
            raise
        latest = None
    return {
        "overview": studio_service.overview(session, task.id),
        "analysis": configuration(settings, session, task.id),
        "latest_run": latest,
        "user": {"id": user.id, "role": user.role, "display_name": user.display_name},
    }


def output(run):
    result = studio_service.row_dict(run)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.replace(tzinfo=UTC).isoformat()
    return result


def get_run(session, task_id, run_id=None):
    run = (
        session.get(StudioAnalysisRun, run_id)
        if run_id
        else session.scalar(
            select(StudioAnalysisRun)
            .where(StudioAnalysisRun.task_id == task_id)
            .order_by(StudioAnalysisRun.created_at.desc())
        )
    )
    if not run or run.task_id != task_id:
        raise AppError("ANALYSIS_NOT_FOUND", "Analysis run not found.", 404)
    return run


def _store(factory, run_id, **fields):
    with factory() as session, session.begin():
        run = session.get(StudioAnalysisRun, run_id)
        for name, value in fields.items():
            setattr(run, name, value)
        run.updated_at = utcnow()
        return output(run)


def validate_proposals(proposals, source, units):
    known = {unit["id"]: unit for unit in units}
    result, seen = [], set()
    for proposal in proposals:
        p = dict(proposal)
        key = (p["knowledge_unit_id"], p["field"])
        if key in seen or key[0] not in known:
            raise ProviderError(
                "AI_OUTPUT_INVALID", "AI proposed duplicate or unknown knowledge fields.", False
            )
        if p["source_quote"] not in source or p["after"] != p["source_quote"]:
            raise ProviderError(
                "AI_OUTPUT_UNSUPPORTED", "AI patch is not an exact source extract.", False
            )
        seen.add(key)
        before = known[key[0]].get(key[1])
        if before != p["after"]:
            result.append({**p, "id": new_id("proposal"), "before": before})
    return result


def analyze(factory, settings, task_id, req, user):
    config = configuration(settings)
    if not config["enabled"]:
        raise AppError("FEATURE_DISABLED", "Studio AI diagnosis is disabled.", 501)
    mode = req.mode
    if mode == "live" and config["mode"] != "live":
        raise AppError("AI_KEY_REQUIRED", "Configure GEMINI_API_KEY to run live AI diagnosis.", 409)
    if mode == "rehearsal" and not settings.demo_mode:
        raise AppError(
            "FEATURE_DISABLED", "Illustrative rehearsal is only available in demo mode.", 501
        )
    with factory() as session, session.begin():
        draft = knowledge_service.get_draft(session, task_id)
        knowledge_service.check_revision(session, draft, req.expected_revision)
        task = session.get(Task, task_id)
        config = configuration(settings, session, task_id)
        source = req.source_notes if req.source_notes is not None else config["source_notes"]
        if mode == "rehearsal" and source != demo_source()["source_notes"]:
            raise AppError(
                "REHEARSAL_SOURCE_REQUIRED", "Load the illustrative source to run rehearsal.", 409
            )
        if not source.strip():
            raise AppError("SOURCE_REQUIRED", "Provide expert source notes before diagnosis.", 422)
        running = session.scalar(
            select(StudioAnalysisRun).where(
                StudioAnalysisRun.task_id == task_id, StudioAnalysisRun.status == "running"
            )
        )
        if running:
            raise AppError("ANALYSIS_RUNNING", "Diagnosis is already running for this task.", 409)
        units = deepcopy(draft.knowledge_units)
        run = StudioAnalysisRun(
            id=new_id("analysis"),
            task_id=task_id,
            revision=draft.revision,
            source_hash=hashlib.sha256(source.encode()).hexdigest(),
            source_notes=source,
            source_label="illustrative"
            if mode == "rehearsal" or source == demo_source()["source_notes"]
            else task.source_label,
            mode=mode,
            model=config["model"] if mode == "live" else "illustrative-v1",
            status="running",
            stage="extracting",
            requested_by=user.id,
            proposals=[],
        )
        session.add(run)
        session.flush()
        run_id = run.id
        studio_service.audit(
            session, task_id, user, "analysis_started", run_id=run_id, mode=run.mode
        )
    # Provider calls happen between short, closed database sessions.
    try:
        if mode == "live":
            agents = StudioAgents(settings)
            findings = agents.extract(source, units)
            _store(factory, run_id, stage="proposing")
            candidates = agents.patch(source, units, findings).model_dump()["proposals"]
        else:
            _store(factory, run_id, stage="proposing")
            candidates = demo_source()["proposals"]
        proposals = validate_proposals(candidates, source, units)
        _store(factory, run_id, stage="evaluating", proposals=proposals)
        if not proposals:
            evaluation = {
                "passed": True,
                "issues": [],
                "summary": "No changed source-supported fields found.",
            }
        elif mode == "live":
            evaluation = agents.critique(source, proposals).model_dump()
        else:
            evaluation = {
                "passed": True,
                "issues": [],
                "summary": "Authored rehearsal: source checks passed. Expert review required.",
            }
        evaluation["scope"] = "Source consistency only; human technical review required."
        with factory() as session, session.begin():
            draft = knowledge_service.get_draft(session, task_id)
            knowledge_service.check_revision(session, draft, req.expected_revision)
            evaluation["unresolved_clarifications"] = [
                {"id": c.id, "question": c.question, "knowledge_unit_id": c.knowledge_unit_id}
                for c in session.scalars(
                    select(Clarification).where(
                        Clarification.task_id == task_id, Clarification.status == "pending"
                    )
                ).all()
            ]
        return _store(
            factory, run_id, status="ready", stage="ready_for_review", evaluation=evaluation
        )
    except Exception as exc:
        logger.exception("Studio AI diagnosis run %s failed: %s", run_id, exc)
        if isinstance(exc, (ProviderError, AppError)):
            code, message = exc.code, exc.message
        else:
            code, message = "ANALYSIS_FAILED", "AI diagnosis failed. Check configuration and retry."
        return _store(
            factory,
            run_id,
            status="failed",
            stage="failed",
            error={"code": code, "message": message},
        )


def approve_publish(session, task_id, run_id, req, user, settings):
    run = get_run(session, task_id, run_id)
    if run.status == "published":
        release = publication_service.get_release(session, run.release_id)
        return {"run": output(run), "release": publication_service.release_out(session, release)}
    if run.status != "ready" or not run.evaluation or not run.evaluation.get("passed"):
        raise AppError(
            "ANALYSIS_NOT_APPROVABLE",
            "Run must pass evaluation before review and publication.",
            409,
        )
    draft = knowledge_service.get_draft(session, task_id)
    knowledge_service.check_revision(session, draft, req.expected_revision)
    if run.revision != draft.revision:
        raise AppError(
            "ANALYSIS_STALE", "The draft changed. Run diagnosis again before approval.", 409
        )
    proposals = {p["id"]: p for p in run.proposals}
    if (
        not req.proposal_ids
        or len(set(req.proposal_ids)) != len(req.proposal_ids)
        or not set(req.proposal_ids) <= proposals.keys()
    ):
        raise AppError(
            "INVALID_PROPOSALS", "Choose at least one valid, unique patch proposal.", 422
        )
    units = deepcopy(draft.knowledge_units)
    by_id = {u["id"]: u for u in units}
    for proposal_id in req.proposal_ids:
        p = proposals[proposal_id]
        unit = by_id[p["knowledge_unit_id"]]
        if unit.get(p["field"]) != p["before"]:
            raise AppError("ANALYSIS_STALE", "A proposed field changed. Run diagnosis again.", 409)
        evidence = Evidence(
            id=new_id("ev"),
            task_id=task_id,
            type="reviewer_correction",
            author_id=user.id,
            author_label=user.display_name,
            source_label=run.source_label,
            content=f"Human-reviewed source extract ({run.id}): {p['source_quote']}",
        )
        session.add(evidence)
        by_id[unit["id"]] = knowledge_service.apply_field_updates(
            unit, {p["field"]: p["after"]}, evidence.id
        )
    knowledge_service.bump_draft(
        session, draft, draft.revision, list(by_id.values()), user.id, f"reviewed_analysis:{run.id}"
    )
    session.expire(draft)
    if req.defer_unanswered:
        for clarification in session.scalars(
            select(Clarification).where(
                Clarification.task_id == task_id, Clarification.status == "pending"
            )
        ).all():
            clarification.status = "deferred"
            clarification.answer = "Unknown; explicitly deferred by reviewer. " + req.approval_note
            clarification.answered_by = user.id
            clarification.answered_at = utcnow()
            studio_service.audit(
                session,
                task_id,
                user,
                "clarification_deferred",
                clarification_id=clarification.id,
                run_id=run.id,
                note=req.approval_note,
            )
        session.flush()
    evaluated = studio_service.evaluate(session, task_id, req.expected_revision + 1, user)
    if not evaluated["passed"]:
        raise AppError(
            "EVALUATION_FAILED",
            "Resolve draft issues before publication.",
            409,
            {"issues": evaluated["issues"]},
        )
    published = studio_service.publish(
        session,
        task_id,
        PublishRequest(
            expected_revision=req.expected_revision + 1, approval_note=req.approval_note
        ),
        user,
        settings,
    )
    release = publication_service.get_release(session, published.id)
    run.status, run.stage, run.release_id = "published", "published", release.id
    run.updated_at = utcnow()
    studio_service.audit(
        session,
        task_id,
        user,
        "analysis_approved_published",
        run_id=run.id,
        proposal_ids=req.proposal_ids,
        release_id=release.id,
        approval_note=req.approval_note,
    )
    session.flush()
    return {"run": output(run), "release": publication_service.release_out(session, release)}


def recover_interrupted(session):
    for run in session.scalars(
        select(StudioAnalysisRun).where(StudioAnalysisRun.status == "running")
    ).all():
        run.status = "failed"
        run.stage = "failed"
        run.error = {
            "code": "ANALYSIS_INTERRUPTED",
            "message": "Server restarted during diagnosis. Run diagnosis again.",
        }
        run.updated_at = utcnow()
    session.flush()
