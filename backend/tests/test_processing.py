from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.ai.base import ProviderError
from app.ai.schemas import ExtractedStep, ProviderFile, VideoExtraction, VideoExtractionResult
from app.database import utcnow
from app.models.entities import Draft, MediaAsset, ProcessingJob
from app.models.schemas import KnowledgeUnit
from app.services import extraction_service, processing_worker
from scripts.demo_flow import run_flow
from tests.conftest import auth
from tests.test_media import upload


class FakeExtractor:
    provider = "gemini"
    model_id = "fake-model"

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def check_model(self):
        self.calls.append("check")

    def upload_file(self, path, mime_type, display_name):
        self.calls.append("upload")
        assert path.exists()
        return ProviderFile(
            name="files/fake", uri="fake://file", mime_type=mime_type, state="PROCESSING"
        )

    def wait_until_active(self, name, on_poll):
        self.calls.append("wait")
        on_poll()
        return ProviderFile(name=name, uri="fake://file", mime_type="video/mp4", state="ACTIVE")

    def extract_video(self, file, task, duration_ms, has_audio):
        self.calls.append("extract")
        result = self.results.pop(0) if self.results else extraction()
        if isinstance(result, Exception):
            raise result
        return result

    def delete_file(self, name):
        self.calls.append("delete")


def extraction(**changes):
    step = dict(
        start_ms=100,
        end_ms=1000,
        action="Inspect the bearing housing",
        cue="Look for a polished contact mark",
        source_modality="visual",
    )
    step.update(changes)
    return VideoExtraction(
        result=VideoExtractionResult(task_summary="Inspection", steps=[ExtractedStep(**step)]),
        model_id="fake-model",
        prompt_version="video_extraction_v1",
        usage={"total_token_count": 10},
    )


@pytest.fixture
def live_client(make_client):
    with make_client(
        ai_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="fake-model",
        enable_media_upload=True,
        enable_media_streaming=True,
        enable_media_processing=True,
        enable_live_extraction=True,
        enable_processing_worker=True,
        processing_max_retries=2,
    ) as client:
        yield client


def setup_recording(client, sample_videos):
    response = client.post(
        "/api/v1/tasks",
        headers=auth(client, "expert"),
        json={
            "title": "Bearing inspection",
            "equipment": "Demonstration bench",
            "language": "en",
        },
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]
    response = upload(client, sample_videos, task_id=task_id)
    assert response.status_code == 201, response.text
    return task_id, response.json()["media_id"]


def process(client, task_id, media_id, request_id="request-1", mode="live", role="expert"):
    return client.post(
        f"/api/v1/tasks/{task_id}/process",
        headers=auth(client, role),
        json={
            "media_id": media_id,
            "mode": mode,
            "request_id": request_id,
        },
    )


def run(client, fake, worker="test-worker"):
    return processing_worker.run_once(
        client.app.state.sessionmaker, client.app.state.settings, fake, worker
    )


def job(client, job_id):
    response = client.get(f"/api/v1/jobs/{job_id}", headers=auth(client, "expert"))
    assert response.status_code == 200
    return response.json()


def make_due(client, job_id):
    with client.app.state.sessionmaker() as session, session.begin():
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                next_attempt_at=utcnow() - timedelta(seconds=1),
            )
        )


def draft(client, task_id):
    return client.get(f"/api/v1/tasks/{task_id}/draft", headers=auth(client, "expert"))


def test_processing_persists_reviewable_draft(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    response = process(client, task_id, media_id)
    assert response.status_code == 202
    queued = response.json()
    assert (queued["status"], queued["stage"], queued["progress_label"]) == (
        "queued",
        "uploaded",
        "Queued",
    )
    fake = FakeExtractor()
    assert run(client, fake) == queued["job_id"]
    result = job(client, queued["job_id"])
    assert (result["status"], result["stage"]) == ("completed", "ready_for_review")
    body = draft(client, task_id).json()
    assert body["draft_id"] == result["draft_id"]
    assert 0 < len(body["clarifications"]) <= 3
    assert all(item["status"] == "pending" for item in body["clarifications"])
    unit = body["knowledge_units"][0]
    assert KnowledgeUnit.model_validate(unit).review_status == "draft"
    evidence_id = unit["field_evidence"]["action"][0]
    evidence = client.get(f"/api/v1/evidence/{evidence_id}", headers=auth(client, "expert")).json()
    assert evidence["type"] == "video_segment"
    assert evidence["media_id"] == media_id
    assert (evidence["start_ms"], evidence["end_ms"]) == (100, 1000)
    assert "unreviewed" in evidence["content"]
    assert fake.calls == ["upload", "wait", "extract", "delete"]
    with client.app.state.sessionmaker() as session:
        stored = session.get(ProcessingJob, queued["job_id"])
        assert stored.extraction["steps"] and stored.usage
        assert stored.provider_file_state == "DELETED"


@pytest.mark.parametrize("kind", ["malformed", "missing action", "empty"])
def test_schema_invalid_retries_once(live_client, sample_videos, kind):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    error = ProviderError(
        "AI_RESPONSE_INVALID", "Model output did not match the extraction schema.", True
    )
    fake = FakeExtractor(error, error)
    run(client, fake)
    assert job(client, job_id)["status"] == "queued"
    assert job(client, job_id)["error"]["code"] == "AI_RESPONSE_INVALID"
    make_due(client, job_id)
    run(client, fake)
    assert job(client, job_id)["status"] == "failed"
    assert job(client, job_id)["attempt_count"] == 2
    assert draft(client, task_id).status_code == 404
    assert fake.calls.count("upload") == 1


def test_invalid_interval_keeps_unit_without_evidence(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    run(client, FakeExtractor(extraction(end_ms=100000)))
    result = job(client, job_id)
    assert result["status"] == "completed"
    assert "INVALID_EVIDENCE_INTERVAL" in result["warnings"][0]
    body = draft(client, task_id).json()
    assert body["knowledge_units"][0]["field_evidence"] == {}
    assert body["knowledge_units"][0]["evidence_ids"] == []
    response = client.post(
        f"/api/v1/tasks/{task_id}/publish",
        headers=auth(client, "reviewer"),
        json={"expected_revision": 1, "approval_note": "Review"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PUBLICATION_BLOCKED"


def test_timeouts_exhaust_retry_budget_preserve_media(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    error = ProviderError("PROCESSING_TIMEOUT", "Provider timed out.", True)
    fake = FakeExtractor(error, error, error)
    for attempt in range(1, 4):
        run(client, fake)
        result = job(client, job_id)
        assert result["attempt_count"] == attempt
        assert result["status"] == ("queued" if attempt < 3 else "failed")
        make_due(client, job_id)
    assert result["draft_id"] is None
    with client.app.state.sessionmaker() as session:
        media = session.get(MediaAsset, media_id)
        assert (client.app.state.settings.media_storage_dir / media.storage_key).exists()


def test_retry_reuses_provider_file(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    fake = FakeExtractor(
        ProviderError("AI_PROVIDER_UNAVAILABLE", "Unavailable.", True), extraction()
    )
    run(client, fake)
    make_due(client, job_id)
    run(client, fake)
    assert job(client, job_id)["status"] == "completed"
    assert fake.calls.count("upload") == 1
    with client.app.state.sessionmaker() as session:
        assert (
            session.scalar(select(func.count()).select_from(Draft).where(Draft.task_id == task_id))
            == 1
        )


def test_crash_recovery_and_lease_guard(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    sessions, settings = client.app.state.sessionmaker, client.app.state.settings
    assert processing_worker.claim_next_job(sessions, settings, "old") == job_id
    with sessions() as session, session.begin():
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                lease_expires_at=utcnow() - timedelta(seconds=1),
            )
        )
    run(client, FakeExtractor(), "new")
    assert job(client, job_id)["status"] == "completed"
    assert job(client, job_id)["attempt_count"] == 2
    with pytest.raises(processing_worker.LeaseLost):
        processing_worker._update(sessions, job_id, "old", stage="extracting")


def test_request_idempotency_and_task_conflicts(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    first = process(client, task_id, media_id).json()
    assert process(client, task_id, media_id).json()["job_id"] == first["job_id"]
    response = process(client, task_id, media_id, "different")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROCESSING_ALREADY_RUNNING"
    run(client, FakeExtractor())
    assert process(client, task_id, media_id).json()["job_id"] == first["job_id"]
    response = process(client, task_id, media_id, "different")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRAFT_ALREADY_EXISTS"


def test_extracted_draft_uses_full_v1_flow(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    process(client, task_id, media_id)
    run(client, FakeExtractor())
    body = draft(client, task_id).json()
    unit = body["knowledge_units"][0]
    clarification = next(
        item for item in body["clarifications"] if item["gap_type"] == "missing_reasoning"
    )
    response = client.post(
        f"/api/v1/clarifications/{clarification['id']}/respond",
        headers=auth(client, "expert"),
        json={
            "expected_draft_revision": 1,
            "disposition": "answered",
            "answer": "A polished contact mark indicates the bearing housing is rubbing.",
            "knowledge_update": {
                "knowledge_unit_id": unit["id"],
                "fields": {
                    "interpretation": (
                        "A polished contact mark indicates rubbing at the bearing housing."
                    ),
                },
            },
        },
    )
    assert response.status_code == 200, response.text
    evidence_id = response.json()["evidence_id"]
    response = client.post(
        f"/api/v1/tasks/{task_id}/publish",
        headers=auth(client, "reviewer"),
        json={
            "expected_revision": 2,
            "approval_note": "Reviewed recording and expert explanation.",
        },
    )
    assert response.status_code == 201, response.text
    release_id = response.json()["release_id"]
    pack = client.get(
        f"/api/v1/releases/{release_id}/training-pack", headers=auth(client, "reviewer")
    ).json()
    assert evidence_id in {item["id"] for item in pack["evidence_items"]}
    for question, status in [
        ("Why do you inspect the bearing housing?", "answered"),
        ("What is the torque specification for the housing bolts?", "insufficient_evidence"),
    ]:
        answer = client.post(
            f"/api/v1/tasks/{task_id}/ask",
            headers=auth(client, "apprentice"),
            json={"question": question},
        ).json()
        assert answer["status"] == status
        if status == "answered":
            assert any(evidence_id in claim["evidence_ids"] for claim in answer["claims"])


def test_fixture_flow_still_runs(client):
    run_flow(client)


def test_unconfigured_and_demo_preserve_media(make_client, sample_videos):
    with make_client(
        enable_media_upload=True, enable_media_streaming=True, enable_media_processing=True
    ) as client:
        task_id, media_id = setup_recording(client, sample_videos)
        for mode, status, code in [
            ("live", 503, "AI_PROVIDER_UNAVAILABLE"),
            ("demo", 422, "FIXTURE_NOT_AVAILABLE"),
        ]:
            response = process(client, task_id, media_id, mode=mode)
            assert response.status_code == status
            assert response.json()["error"]["code"] == code
        assert (
            client.get(
                f"/api/v1/media/{media_id}/stream", headers=auth(client, "expert")
            ).status_code
            == 200
        )


def test_processing_flags_and_access(client, live_client):
    body = {"media_id": "missing", "mode": "live", "request_id": "test"}
    response = client.post(
        "/api/v1/tasks/task_001/process", headers=auth(client, "expert"), json=body
    )
    assert response.status_code == 501
    assert client.get("/api/v1/jobs/missing", headers=auth(client, "expert")).status_code == 501
    response = live_client.get("/api/v1/jobs/missing", headers=auth(live_client, "expert"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROCESSING_JOB_NOT_FOUND"
    assert (
        live_client.get("/api/v1/jobs/missing", headers=auth(live_client, "apprentice")).status_code
        == 403
    )
    assert (
        live_client.post(
            "/api/v1/tasks/task_001/process", headers=auth(live_client, "apprentice"), json=body
        ).status_code
        == 403
    )


def test_extraction_deduplicates_intervals_and_warns():
    media = MediaAsset(id="media-test", task_id="task-test", duration_ms=3000, audio_codec=None)
    result = extraction(source_modality="spoken").result
    result.steps.append(result.steps[0].model_copy(update={"action": " Check again "}))
    result.steps.append(result.steps[0].model_copy(update={"action": "   "}))
    result.processing_warnings = ["Uncertain view"]
    units, evidence, warnings = extraction_service.build_draft_content(
        result, media, "AI extraction"
    )
    assert len(units) == 2 and len(evidence) == 1
    assert units[0]["evidence_ids"] == units[1]["evidence_ids"]
    assert units[1]["action"] == "Check again"
    assert "step 3: empty action dropped" in warnings
    assert "model: Uncertain view" in warnings
    assert any("no audio track" in warning for warning in warnings)
    with pytest.raises(ProviderError, match="no usable steps"):
        extraction_service.build_draft_content(
            VideoExtractionResult(task_summary="Empty"), media, "AI"
        )


def test_checkpoint_resume_skips_provider_extraction(live_client, sample_videos, monkeypatch):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    build = extraction_service.build_draft_content

    def interrupted(*args):
        raise ProviderError("PROCESSING_TIMEOUT", "Interrupted after checkpoint.", True)

    monkeypatch.setattr(extraction_service, "build_draft_content", interrupted)
    fake = FakeExtractor()
    run(client, fake)
    assert job(client, job_id)["status"] == "queued"
    monkeypatch.setattr(extraction_service, "build_draft_content", build)
    make_due(client, job_id)
    run(client, fake)
    assert job(client, job_id)["status"] == "completed"
    assert fake.calls.count("extract") == 1
    assert fake.calls.count("upload") == 1


def test_lease_loss_rolls_back_draft_and_evidence(live_client, sample_videos, monkeypatch):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    persist = extraction_service.persist_extraction

    def lose_lease(session, job, *args):
        draft_id = persist(session, job, *args)
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job.id)
            .values(
                lease_owner="other-worker",
            )
        )
        return draft_id

    monkeypatch.setattr(extraction_service, "persist_extraction", lose_lease)
    run(client, FakeExtractor())
    assert draft(client, task_id).status_code == 404
    with client.app.state.sessionmaker() as session:
        from app.models.entities import Evidence

        assert (
            session.scalar(
                select(func.count())
                .select_from(Evidence)
                .where(
                    Evidence.task_id == task_id,
                )
            )
            == 0
        )
    assert job(client, job_id)["status"] == "running"


def test_cleanup_failure_keeps_completed_job(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]

    class CleanupFailure(FakeExtractor):
        def delete_file(self, name):
            raise ProviderError("AI_PROVIDER_UNAVAILABLE", "Cleanup unavailable.", True)

    run(client, CleanupFailure())
    assert job(client, job_id)["status"] == "completed"
    with client.app.state.sessionmaker() as session:
        assert session.get(ProcessingJob, job_id).provider_file_state == "ACTIVE"


def test_expired_provider_file_reuploads(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    with client.app.state.sessionmaker() as session, session.begin():
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                provider_file_name="files/expired",
                provider_file_uri="fake://expired",
                provider_file_state="ACTIVE",
            )
        )

    class ExpiredFile(FakeExtractor):
        def wait_until_active(self, name, on_poll):
            if name == "files/expired":
                raise ProviderError("AI_FILE_EXPIRED", "Expired.", True)
            return super().wait_until_active(name, on_poll)

    fake = ExpiredFile()
    run(client, fake)
    assert job(client, job_id)["status"] == "completed"
    assert fake.calls.count("upload") == 1


def test_exhausted_expired_lease_fails(live_client, sample_videos):
    client = live_client
    task_id, media_id = setup_recording(client, sample_videos)
    job_id = process(client, task_id, media_id).json()["job_id"]
    with client.app.state.sessionmaker() as session, session.begin():
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(
                status="running",
                lease_owner="dead",
                attempt_count=3,
                lease_expires_at=utcnow() - timedelta(seconds=1),
            )
        )
    assert run(client, FakeExtractor()) is None
    assert job(client, job_id)["status"] == "failed"
    assert job(client, job_id)["error"]["code"] == "PROCESSING_TIMEOUT"
