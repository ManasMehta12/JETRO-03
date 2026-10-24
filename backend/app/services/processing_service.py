from sqlalchemy import select

from app.ai.prompts.transcript_extraction_v1 import PROMPT_VERSION as TRANSCRIPT_PROMPT_VERSION
from app.ai.prompts.video_extraction_v1 import PROMPT_VERSION
from app.core.errors import AppError
from app.database import new_id
from app.models.entities import Draft, MediaAsset, ProcessingJob
from app.models.schemas import PROGRESS_LABELS, JobError, JobOut
from app.services.task_service import get_task


def create_job(session, settings, task_id, req, user) -> ProcessingJob:
    get_task(session, task_id, user)
    media = session.get(MediaAsset, req.media_id)
    if media is None or media.task_id != task_id:
        raise AppError("MEDIA_NOT_FOUND", "Media not found.", 404)
    existing = session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.task_id == task_id,
            ProcessingJob.media_id == media.id,
            ProcessingJob.mode == req.mode,
            ProcessingJob.request_id == req.request_id,
        )
    )
    if existing is not None:
        return existing
    if req.mode == "demo":
        raise AppError(
            "FIXTURE_NOT_AVAILABLE",
            "Demo mode cannot analyze uploaded recordings; use the seeded task_001 demo.",
            422,
        )
    if settings.ai_provider not in ("gemini", "ollama") or not settings.enable_live_extraction:
        raise AppError(
            "AI_PROVIDER_UNAVAILABLE",
            "Live extraction is not configured.",
            503,
            {
                "required": [
                    "AI_PROVIDER=gemini",
                    "ENABLE_LIVE_EXTRACTION=true",
                    "GEMINI_API_KEY",
                    "GEMINI_MODEL",
                ],
            },
        )
    if settings.ai_provider == "ollama" and media.audio_codec is None:
        raise AppError(
            "MEDIA_HAS_NO_AUDIO",
            "Transcript-based extraction needs a recording with narration audio.",
            422,
        )
    if session.scalar(select(Draft.id).where(Draft.task_id == task_id)):
        raise AppError(
            "DRAFT_ALREADY_EXISTS",
            "This task already has a draft; create a new task for a new recording.",
            409,
            {"task_id": task_id},
        )
    active = session.scalar(
        select(ProcessingJob).where(
            ProcessingJob.task_id == task_id,
            ProcessingJob.status.in_(["queued", "running"]),
        )
    )
    if active is not None:
        raise AppError(
            "PROCESSING_ALREADY_RUNNING",
            "Processing is already running for this task.",
            409,
            {"job_id": active.id},
        )
    ollama = settings.ai_provider == "ollama"
    job = ProcessingJob(
        id=new_id("job"),
        task_id=task_id,
        media_id=media.id,
        mode=req.mode,
        request_id=req.request_id,
        requested_by=user.id,
        status="queued",
        stage="uploaded",
        provider=settings.ai_provider,
        model_id=settings.ollama_model if ollama else settings.gemini_model,
        prompt_version=TRANSCRIPT_PROMPT_VERSION if ollama else PROMPT_VERSION,
        input_sha256=media.sha256,
    )
    session.add(job)
    session.flush()
    return job


def get_job(session, job_id) -> ProcessingJob:
    job = session.get(ProcessingJob, job_id)
    if job is None:
        raise AppError("PROCESSING_JOB_NOT_FOUND", "Processing job not found.", 404)
    return job


def job_out(job) -> JobOut:
    return JobOut(
        job_id=job.id,
        task_id=job.task_id,
        media_id=job.media_id,
        mode=job.mode,
        status=job.status,
        stage=job.stage,
        progress_label="Processing failed"
        if job.status == "failed"
        else PROGRESS_LABELS[job.stage],
        attempt_count=job.attempt_count,
        draft_id=job.result_draft_id,
        error=JobError(code=job.error_code, message=job.error_message) if job.error_code else None,
        warnings=job.warnings,
        provider=job.provider,
        model_id=job.model_id,
        prompt_version=job.prompt_version,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
