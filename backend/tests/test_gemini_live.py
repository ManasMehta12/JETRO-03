import os
import time
from pathlib import Path

import pytest

from app.ai.gemini_provider import GeminiAIProvider
from tests.conftest import auth

LIVE_ENABLED = os.getenv("TAKUMI_LIVE_GEMINI") == "1" and all(
    os.getenv(name) for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "TAKUMI_LIVE_VIDEO")
)


@pytest.mark.skipif(
    not LIVE_ENABLED, reason="Live Gemini unverified: explicit credentials and video required"
)
def test_live_gemini_extraction(make_client):
    from app.models.entities import ProcessingJob
    from app.services import processing_worker

    video = Path(os.environ["TAKUMI_LIVE_VIDEO"])
    assert video.is_file(), "TAKUMI_LIVE_VIDEO must point to a real MP4"
    with make_client(
        ai_provider="gemini",
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        gemini_model=os.environ["GEMINI_MODEL"],
        enable_media_upload=True,
        enable_media_processing=True,
        enable_live_extraction=True,
        enable_processing_worker=True,
    ) as client:
        headers = auth(client, "expert")
        response = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "title": "Live video extraction",
                "equipment": "Demonstration bench",
                "language": "en",
            },
        )
        assert response.status_code == 201, response.text
        task_id = response.json()["id"]
        with video.open("rb") as source:
            response = client.post(
                f"/api/v1/tasks/{task_id}/media",
                headers=headers,
                files={"file": (video.name, source, "video/mp4")},
            )
        assert response.status_code == 201, response.text
        media_id = response.json()["media_id"]
        response = client.post(
            f"/api/v1/tasks/{task_id}/process",
            headers=headers,
            json={"media_id": media_id, "mode": "live", "request_id": "live-test"},
        )
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        settings = client.app.state.settings
        extractor = GeminiAIProvider(settings)
        extractor.check_model()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            processing_worker.run_once(
                client.app.state.sessionmaker, settings, extractor, "live-test-worker"
            )
            response = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            assert response.status_code == 200, response.text
            job = response.json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(settings.processing_poll_interval_seconds)
        assert job["status"] == "completed", job
        assert job["draft_id"]
        with client.app.state.sessionmaker() as session:
            assert session.get(ProcessingJob, job_id).provider_file_name
        response = client.get(f"/api/v1/tasks/{task_id}/draft", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["knowledge_units"]
