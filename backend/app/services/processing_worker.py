import logging
import os
import sys
import time
from datetime import timedelta
from functools import partial
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker as make_sessionmaker

from app.ai.base import ProviderError, VideoExtractor, get_video_extractor
from app.ai.schemas import TaskContext, VideoExtractionResult
from app.core.errors import AppError
from app.database import build_engine, init_db, utcnow
from app.models.entities import MediaAsset, ProcessingJob, Task
from app.services import extraction_service, media_service

logger = logging.getLogger("takumi.worker")


class LeaseLost(Exception):
    pass


def claim_next_job(sessionmaker, settings, worker_id) -> str | None:
    now = utcnow()
    with sessionmaker() as session, session.begin():
        expired = and_(ProcessingJob.status == "running", ProcessingJob.lease_expires_at < now)
        session.execute(
            update(ProcessingJob)
            .where(
                expired,
                ProcessingJob.attempt_count > settings.processing_max_retries,
            )
            .values(
                status="failed",
                error_code="PROCESSING_TIMEOUT",
                error_message="Processing lease expired too many times.",
                lease_owner=None,
                lease_expires_at=None,
                completed_at=now,
                updated_at=now,
            )
        )
        job = session.scalar(
            select(ProcessingJob)
            .where(
                or_(
                    and_(
                        ProcessingJob.status == "queued",
                        or_(
                            ProcessingJob.next_attempt_at.is_(None),
                            ProcessingJob.next_attempt_at <= now,
                        ),
                    ),
                    expired,
                )
            )
            .order_by(ProcessingJob.created_at)
            .limit(1)
        )
        if job is None:
            return None
        job.status = "running"
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=settings.processing_job_lease_seconds)
        job.attempt_count += 1
        job.started_at = job.started_at or now
        job.updated_at = now
        return job.id


def _guard(job_id, worker_id):
    return (
        ProcessingJob.id == job_id,
        ProcessingJob.lease_owner == worker_id,
        ProcessingJob.status == "running",
    )


def _update(sessionmaker, job_id, worker_id, *, lease_seconds=180, **values) -> None:
    now = utcnow()
    values.setdefault("lease_expires_at", now + timedelta(seconds=lease_seconds))
    with sessionmaker() as session, session.begin():
        changed = session.execute(
            update(ProcessingJob)
            .where(*_guard(job_id, worker_id))
            .values(
                **values,
                updated_at=now,
            )
        )
        if changed.rowcount == 0:
            raise LeaseLost


def run_once(sessionmaker, settings, extractor: VideoExtractor, worker_id: str) -> str | None:
    job_id = claim_next_job(sessionmaker, settings, worker_id)
    if job_id is None:
        return None
    started = time.monotonic()
    stage_started = started
    with sessionmaker() as session, session.begin():
        job = session.get(ProcessingJob, job_id)
        if job is None:
            logger.info("job_id=%s lease lost", job_id)
            return job_id
        media = session.get(MediaAsset, job.media_id)
        task = session.get(Task, job.task_id)
        context = TaskContext(
            task_id=task.id, title=task.title, equipment=task.equipment, language=task.language
        )
        session.expunge_all()
    heartbeat = partial(
        _update,
        sessionmaker,
        job_id,
        worker_id,
        lease_seconds=settings.processing_job_lease_seconds,
    )

    def log_stage(status="running", error_code=None):
        nonlocal stage_started
        now = time.monotonic()
        logger.info(
            "job_id=%s task_id=%s media_id=%s provider=%s model_id=%s prompt_version=%s "
            "input_sha256=%s stage=%s status=%s attempt_count=%s stage_duration_ms=%d "
            "total_duration_ms=%d error_code=%s",
            job.id,
            job.task_id,
            job.media_id,
            job.provider,
            job.model_id,
            job.prompt_version,
            job.input_sha256,
            job.stage,
            status,
            job.attempt_count,
            (now - stage_started) * 1000,
            (now - started) * 1000,
            error_code,
        )
        stage_started = now

    def stage(name):
        log_stage()
        heartbeat(stage=name)
        job.stage = name

    try:
        path = media_service.media_path(settings, media)
        if job.extraction is None:
            stage("preparing_media")
            file = None
            if job.provider_file_name:
                try:
                    file = extractor.wait_until_active(job.provider_file_name, heartbeat)
                except ProviderError as error:
                    if error.code != "AI_FILE_EXPIRED":
                        raise
                    heartbeat(
                        provider_file_name=None,
                        provider_file_uri=None,
                        provider_file_state=None,
                        provider_uploaded_at=None,
                        provider_expires_at=None,
                    )
                    job.provider_file_name = None
            if file is None:
                file = extractor.upload_file(path, media.mime_type, media.id)
                job.provider_file_name = file.name
                heartbeat(
                    provider_file_name=file.name,
                    provider_file_uri=file.uri,
                    provider_file_state=file.state,
                    provider_uploaded_at=utcnow(),
                    provider_expires_at=file.expires_at,
                )
                file = extractor.wait_until_active(file.name, heartbeat)
            heartbeat(provider_file_state="ACTIVE")
            stage("extracting")
            extraction = extractor.extract_video(
                file, context, media.duration_ms, media.audio_codec is not None
            )
            result = extraction.result
            job.model_id = extraction.model_id
            # Reject unusable output before checkpointing, so the retry asks the model again.
            draft_content = extraction_service.build_draft_content(
                result, media, f"AI extraction ({job.model_id}, unreviewed)"
            )
            heartbeat(
                extraction=result.model_dump(mode="json"),
                usage=extraction.usage,
                model_id=extraction.model_id,
            )
        else:
            draft_content = extraction_service.build_draft_content(
                VideoExtractionResult.model_validate(job.extraction),
                media,
                f"AI extraction ({job.model_id}, unreviewed)",
            )
        stage("detecting_gaps")
        units, evidence_rows, warnings = draft_content
        try:
            with sessionmaker() as session, session.begin():
                draft_id = extraction_service.persist_extraction(
                    session,
                    job,
                    media,
                    units,
                    evidence_rows,
                    warnings,
                )
                changed = session.execute(
                    update(ProcessingJob)
                    .where(*_guard(job_id, worker_id))
                    .values(
                        status="completed",
                        stage="ready_for_review",
                        result_draft_id=draft_id,
                        warnings=warnings,
                        completed_at=utcnow(),
                        updated_at=utcnow(),
                        lease_owner=None,
                        lease_expires_at=None,
                        next_attempt_at=None,
                        error_code=None,
                        error_message=None,
                    )
                )
                if changed.rowcount == 0:
                    raise LeaseLost
        except SQLAlchemyError:
            raise ProviderError(
                "DRAFT_PERSISTENCE_FAILED", "Could not persist extracted draft.", False
            ) from None
        log_stage()
        job.stage = "ready_for_review"
        log_stage("completed")
        if job.provider_file_name:
            try:
                extractor.delete_file(job.provider_file_name)
            except ProviderError as error:
                logger.warning("error_code=%s", error.code)
            else:
                with sessionmaker() as session, session.begin():
                    session.execute(
                        update(ProcessingJob)
                        .where(ProcessingJob.id == job_id)
                        .values(
                            provider_file_state="DELETED",
                        )
                    )
    except LeaseLost:
        logger.info("job_id=%s lease lost", job_id)
    except Exception as error:
        if isinstance(error, AppError):
            error = ProviderError(error.code, error.message, False)
        elif not isinstance(error, ProviderError):
            # Exception text may contain provider payloads or private paths.
            logger.error("job_id=%s error_code=PROCESSING_FAILED", job_id)
            error = ProviderError("PROCESSING_FAILED", "Unexpected processing error.", False)
        retryable = error.retryable and not (
            error.code == "AI_RESPONSE_INVALID" and job.error_code == "AI_RESPONSE_INVALID"
        )
        retry = retryable and job.attempt_count <= settings.processing_max_retries
        status = "queued" if retry else "failed"
        delay = error.retry_after_seconds or min(
            60,
            settings.processing_poll_interval_seconds * 2**job.attempt_count,
        )
        try:
            heartbeat(
                status=status,
                lease_owner=None,
                lease_expires_at=None,
                next_attempt_at=utcnow() + timedelta(seconds=delay) if retry else None,
                completed_at=None if retry else utcnow(),
                error_code=error.code,
                error_message=error.message,
            )
            log_stage(status, error.code)
        except LeaseLost:
            logger.info("job_id=%s lease lost", job_id)
    return job_id


def run_forever(settings) -> int:
    if not settings.enable_processing_worker:
        print("ENABLE_PROCESSING_WORKER is false", file=sys.stderr)
        return 2
    if settings.ai_provider not in ("gemini", "ollama"):
        print("Worker requires AI_PROVIDER=gemini or ollama", file=sys.stderr)
        return 2
    engine = build_engine(settings)
    try:
        init_db(engine)
        sessionmaker = make_sessionmaker(engine, expire_on_commit=False)
        extractor = get_video_extractor(settings)
        try:
            extractor.check_model()
        except ProviderError as error:
            print(f"{error.code}: {error.message}", file=sys.stderr)
            return 2
        worker_id = f"worker_{os.getpid()}_{uuid4().hex[:6]}"
        while True:
            if run_once(sessionmaker, settings, extractor, worker_id) is None:
                time.sleep(settings.processing_poll_interval_seconds)
    except KeyboardInterrupt:
        return 0
    finally:
        engine.dispose()
