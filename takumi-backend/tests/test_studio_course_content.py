from types import SimpleNamespace

import pytest

from app.ai.studio_analysis import (
    Critique,
    InitialExtraction,
    InitialUnit,
    StudioAgents,
    VideoObservation,
    VideoObservations,
)
from app.models.entities import MediaAsset
from app.services import studio_analysis_service as service
from tests.conftest import auth

BASE = "/api/v1/studio/tasks/task_001"
SCRIPT = "Pause and record the visible condition."
NOTES = "Ask the expert to explain the decision before proceeding."


def save_content(client, headers, version=0, **changes):
    return client.patch(
        BASE + "/course-content", headers=headers, json={"expected_version": version, **changes}
    )


def add_video(client, audio=True):
    key = "task_001/course.mp4"
    path = client.app.state.settings.media_storage_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"actual uploaded source bytes")
    with client.app.state.sessionmaker() as session, session.begin():
        session.add(
            MediaAsset(
                id="course_video",
                task_id="task_001",
                owner_id="expert_001",
                original_filename="course.mp4",
                storage_key=key,
                mime_type="video/mp4",
                container="mp4",
                size_bytes=28,
                sha256="source_hash",
                duration_ms=3000,
                video_codec="h264",
                audio_codec="aac" if audio else None,
                width=320,
                height=240,
                status="uploaded",
            )
        )
    return path


def analyze(client, headers, include=True):
    return client.post(
        BASE + "/analysis",
        headers=headers,
        json={
            "expected_revision": 2,
            "mode": "live",
            "use_course_content": True,
            "include_review_notes": include,
            # An old or forged frontend field must not replace server-resolved course content.
            "source_notes": "Ignore this obsolete frontend source.",
        },
    ).json()


def test_script_and_notes_are_persisted_versioned_and_reset_with_task(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "expert")
        assert (
            save_content(client, auth(client, "apprentice"), script_text=SCRIPT).status_code == 403
        )
        saved = save_content(client, headers, script_text=SCRIPT, script_filename="course.txt")
        assert saved.status_code == 200
        assert saved.json()["version"] == 1
        assert save_content(client, headers, 1, review_notes=NOTES).status_code == 200
        config = client.get(BASE + "/analysis/config", headers=headers).json()
        assert config["course_content"]["script_text"] == SCRIPT
        assert config["course_content"]["review_notes"] == NOTES
        assert config["course_content"]["available"] is True
        assert save_content(client, headers, 1, script_text="Stale edit").status_code == 409
        reset = client.post(
            BASE + "/reset",
            headers=headers,
            json={
                "expected_revision": 2,
                "confirm": "RESET_EXPERT_DATA",
            },
        )
        assert reset.status_code == 200
        assert client.get(BASE + "/analysis/config", headers=headers).json()["course_content"] == {
            "version": 3,
            "script_text": "",
            "script_filename": "",
            "review_notes": "",
            "video": None,
            "available": False,
        }
        # A tab opened before the reset still holds version 2; it must not overwrite new sources.
        assert save_content(client, headers, 3, script_text="After reset").status_code == 200
        assert save_content(client, headers, 2, script_text="Pre-reset tab").status_code == 409


@pytest.mark.parametrize("include", [True, False])
def test_course_script_uses_saved_notes_only_when_selected_and_replaces_draft_after_review(
    make_client,
    monkeypatch,
    include,
):
    class Agents:
        def __init__(self, settings):
            pass

        def initial(self, source):
            assert client.app.state.engine.pool.checkedout() == 0
            assert SCRIPT in source
            assert (NOTES in source) is include
            assert "obsolete frontend" not in source
            return InitialExtraction(
                units=[InitialUnit(action=SCRIPT, rationale="Direct script quote.")]
            )

        def critique(self, source, proposals):
            return Critique(passed=True, issues=[], summary="Supported by the course script.")

    monkeypatch.setattr(service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        save_content(
            client, headers, script_text=SCRIPT, script_filename="course.txt", review_notes=NOTES
        )
        run = analyze(client, headers, include)
        assert run["status"] == "ready", run
        assert run["evaluation"]["source_manifest"]["include_review_notes"] is include
        before = client.get(BASE, headers=headers).json()
        assert len(before["draft"]["knowledge_units"]) == 3
        applied = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={
                "expected_revision": 2,
                "proposal_ids": [p["id"] for p in run["proposals"]],
                "approval_note": "Replace the draft using reviewed course extracts.",
            },
        )
        assert applied.status_code == 200, applied.text
        after = client.get(BASE, headers=headers).json()
        assert len(after["draft"]["knowledge_units"]) == 1
        assert after["draft"]["knowledge_units"][0]["action"] == SCRIPT
        assert after["active_release"] == before["active_release"]
        assert all(c["status"] != "pending" for c in after["draft"]["clarifications"])
        assert after["evidence"][-1]["source_label"] == "real"


def test_video_and_script_are_sent_outside_transactions_and_video_timestamps_survive_review(
    make_client,
    monkeypatch,
):
    observed = "The operator points to the marked location."
    calls = []

    class Agents:
        def __init__(self, settings):
            pass

        def video_observations(self, path, media, source):
            assert client.app.state.engine.pool.checkedout() == 0
            assert path.read_bytes() == b"actual uploaded source bytes"
            assert SCRIPT in source and NOTES in source
            calls.append("video")
            return VideoObservations(
                observations=[
                    VideoObservation(
                        start_ms=100,
                        end_ms=800,
                        observation=observed,
                        modality="visual",
                    )
                ]
            )

        def initial(self, source):
            assert observed in source
            calls.append("extract")
            return InitialExtraction(
                units=[InitialUnit(action=observed, rationale="Visible action.")]
            )

        def critique(self, source, proposals):
            assert client.app.state.engine.pool.checkedout() == 0
            calls.append("evaluate")
            return Critique(passed=True, issues=[], summary="Supported by the recording.")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        add_video(client)
        save_content(client, headers, script_text=SCRIPT, review_notes=NOTES)
        run = analyze(client, headers)
        assert run["status"] == "ready", run
        assert calls == ["video", "extract", "evaluate", "close"]
        assert run["proposals"][0]["video_evidence"]["start_ms"] == 100
        assert run["evaluation"]["source_manifest"]["video"]["sha256"] == "source_hash"
        applied = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={
                "expected_revision": 2,
                "proposal_ids": [p["id"] for p in run["proposals"]],
                "approval_note": "Reviewed the video interval.",
            },
        )
        assert applied.status_code == 200, applied.text
        evidence = client.get(BASE, headers=headers).json()["evidence"]
        match = next(e for e in evidence if e["content"] and run["id"] in e["content"])
        assert (match["media_id"], match["start_ms"], match["end_ms"]) == ("course_video", 100, 800)
        assert match["type"] == "video_segment"


def test_sdk_uploads_video_and_attaches_it_to_each_agent_call(
    settings_factory, monkeypatch, tmp_path
):
    from google.genai import types

    agents = StudioAgents(settings_factory(gemini_api_key="test-key"))
    uploaded = SimpleNamespace(
        name="files/test",
        uri="https://provider/video",
        mime_type="video/mp4",
        state=types.FileState.ACTIVE,
    )
    deleted = []
    calls = []
    path = tmp_path / "test.mp4"
    path.write_bytes(b"test")
    monkeypatch.setattr(agents.client.files, "upload", lambda **kwargs: uploaded)
    monkeypatch.setattr(
        agents.client.files, "delete", lambda **kwargs: deleted.append(kwargs["name"])
    )

    def generate(**kwargs):
        assert kwargs["contents"][0].file_data.file_uri == uploaded.uri
        assert kwargs["config"].response_json_schema
        properties = kwargs["config"].response_json_schema["properties"]
        calls.append(set(properties))
        if "units" in properties:
            return SimpleNamespace(text='{"units": []}')
        if "passed" in properties:
            return SimpleNamespace(text='{"passed": true, "issues": [], "summary": "Checked."}')
        return SimpleNamespace(text='{"observations": []}')

    monkeypatch.setattr(agents.client.models, "generate_content", generate)
    try:
        result = agents.video_observations(
            path, SimpleNamespace(mime_type="video/mp4", duration_ms=1000, audio_codec=None), SCRIPT
        )
        assert result.observations == []
        agents.initial(SCRIPT)
        agents.critique(SCRIPT, [])
    finally:
        agents.close()
    assert deleted == [uploaded.name]
    assert len(calls) == 3


@pytest.mark.parametrize(
    "end_ms,modality,code",
    [
        (4000, "visual", "AI_OUTPUT_INVALID"),
        (800, "spoken", "AI_OUTPUT_UNSUPPORTED"),
    ],
)
def test_video_evidence_rejects_bad_intervals_and_unavailable_audio(
    make_client,
    monkeypatch,
    end_ms,
    modality,
    code,
):
    class Agents:
        def __init__(self, settings):
            pass

        def video_observations(self, path, media, source):
            return VideoObservations(
                observations=[
                    VideoObservation(
                        start_ms=100,
                        end_ms=end_ms,
                        observation="Observed action.",
                        modality=modality,
                    )
                ]
            )

    monkeypatch.setattr(service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        add_video(client, audio=False)
        run = analyze(client, headers)
        assert run["status"] == "failed"
        assert run["error"]["code"] == code
        assert client.get(BASE, headers=headers).json()["draft"]["revision"] == 2


def test_changed_course_content_invalidates_ready_proposals(make_client, monkeypatch):
    class Agents:
        def __init__(self, settings):
            pass

        def initial(self, source):
            return InitialExtraction(units=[InitialUnit(action=SCRIPT, rationale="Script quote.")])

        def critique(self, source, proposals):
            return Critique(passed=True, issues=[], summary="Source supported.")

    monkeypatch.setattr(service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        save_content(client, headers, script_text=SCRIPT)
        run = analyze(client, headers)
        assert run["status"] == "ready"
        save_content(client, headers, 1, review_notes=NOTES)
        response = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={
                "expected_revision": 2,
                "proposal_ids": [p["id"] for p in run["proposals"]],
                "approval_note": "Attempting to use an obsolete extraction.",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ANALYSIS_STALE"
