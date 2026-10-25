from app.ai.studio_analysis import Critique, InitialExtraction, InitialUnit
from app.models.analysis import StudioAnalysisRun
from app.services import studio_analysis_service
from app.services.seed_service import seed_demo
from tests.conftest import auth

BASE = "/api/v1/studio/tasks/task_001"


def reset(client, headers, revision):
    return client.post(
        BASE + "/reset",
        headers=headers,
        json={"expected_revision": revision, "confirm": "RESET_EXPERT_DATA"},
    )


def test_reset_empties_panels_preserves_task_and_other_tasks(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "expert")
        other = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={"title": "Unrelated task", "equipment": "Other bench"},
        ).json()
        before = client.get(BASE, headers=headers).json()
        assert reset(client, headers, before["draft"]["revision"]).status_code == 200
        workspace = client.get("/api/v1/studio/workspace", headers=headers).json()
        after = workspace["overview"]
        assert after["task"]["id"] == before["task"]["id"]
        assert after["task"]["title"] == before["task"]["title"]
        assert after["draft"]["revision"] == before["draft"]["revision"] + 1
        for name in ("knowledge_units", "clarifications"):
            assert after["draft"][name] == []
        for name in ("evidence", "audit", "analysis_runs"):
            assert after[name] == []
        for name in ("active_release", "evaluation", "authorization"):
            assert after[name] is None
        assert workspace["analysis"]["source_notes"] == ""
        assert workspace["latest_run"] is None
        assert client.get(f"/api/v1/tasks/{other['id']}", headers=headers).json() == other
        learner = auth(client, "apprentice")
        assert client.get("/api/v1/learning/course", headers=learner).json()["release_id"] is None
        with client.app.state.sessionmaker() as session, session.begin():
            assert seed_demo(session, "approved_baseline") is False


def test_reset_requires_role_confirmation_current_revision_and_feature_flag(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        expert = auth(client, "expert")
        assert reset(client, auth(client, "apprentice"), 2).status_code == 403
        assert reset(client, auth(client, "reviewer"), 2).status_code == 403
        assert (
            client.post(
                BASE + "/reset",
                headers=expert,
                json={
                    "expected_revision": 2,
                    "confirm": "wrong",
                },
            ).json()["error"]["code"]
            == "CONFIRMATION_REQUIRED"
        )
        assert reset(client, expert, 1).json()["error"]["code"] == "REVISION_CONFLICT"
        client.app.state.settings.enable_demo_reset = False
        assert reset(client, expert, 2).status_code == 501
        assert client.get(BASE, headers=expert).json()["active_release"] is not None


def test_reset_refuses_a_running_diagnosis(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "admin")
        with client.app.state.sessionmaker() as session, session.begin():
            session.add(
                StudioAnalysisRun(
                    id="busy",
                    task_id="task_001",
                    revision=2,
                    source_hash="test",
                    source_notes="test",
                    source_label="real",
                    mode="live",
                    model="test",
                    status="running",
                    stage="extracting",
                    requested_by="expert_001",
                    proposals=[],
                )
            )
        response = reset(client, headers, 2)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RESET_BUSY"
        assert client.get(BASE, headers=headers).json()["active_release"] is not None


def test_empty_workspace_can_extract_and_save_new_units(make_client, monkeypatch):
    source = "Record the observation. Ask the instructor to review it."

    class Agents:
        def __init__(self, settings):
            pass

        def initial(self, notes):
            assert notes == source
            return InitialExtraction(
                units=[
                    InitialUnit(
                        action="Record the observation.",
                        decision="Ask the instructor to review it.",
                        rationale="Both fields are explicitly stated by the source.",
                    )
                ]
            )

        def critique(self, notes, proposals):
            return Critique(passed=True, issues=[], summary="Exact source extracts.")

    monkeypatch.setattr(studio_analysis_service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        assert reset(client, headers, 2).status_code == 200
        run = client.post(
            BASE + "/analysis",
            headers=headers,
            json={
                "expected_revision": 3,
                "mode": "live",
                "source_notes": source,
            },
        ).json()
        assert run["status"] == "ready"
        assert run["evaluation"]["initial_extraction"] is True
        assert client.get(BASE, headers=headers).json()["draft"]["knowledge_units"] == []
        req = {"expected_revision": 3, "approval_note": "Reviewed source extracts."}
        decision = next(p for p in run["proposals"] if p["field"] == "decision")
        invalid = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={**req, "proposal_ids": [decision["id"]]},
        )
        assert invalid.status_code == 422
        saved = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={**req, "proposal_ids": [p["id"] for p in run["proposals"]]},
        )
        assert saved.status_code == 200, saved.text
        unit = saved.json()["draft"]["knowledge_units"][0]
        assert unit["action"] == "Record the observation."
        assert unit["decision"] == "Ask the instructor to review it."
        assert unit["cue"] is None
        assert unit["field_evidence"]["action"]
        assert client.get(BASE, headers=headers).json()["active_release"] is None


def test_saved_units_keep_extraction_order_regardless_of_selection_order(make_client, monkeypatch):
    actions = ["First record the observation.", "Then ask the instructor to review it."]

    class Agents:
        def __init__(self, settings):
            pass

        def initial(self, notes):
            return InitialExtraction(
                units=[InitialUnit(action=action, rationale="Stated.") for action in actions]
            )

        def critique(self, notes, proposals):
            return Critique(passed=True, issues=[], summary="Exact source extracts.")

    monkeypatch.setattr(studio_analysis_service, "StudioAgents", Agents)
    with make_client(demo_seed_state="approved_baseline", gemini_api_key="test-key") as client:
        headers = auth(client, "expert")
        assert reset(client, headers, 2).status_code == 200
        run = client.post(
            BASE + "/analysis",
            headers=headers,
            json={"expected_revision": 3, "mode": "live", "source_notes": " ".join(actions)},
        ).json()
        assert run["status"] == "ready", run
        saved = client.post(
            BASE + f"/analysis/{run['id']}/apply",
            headers=headers,
            json={
                "expected_revision": 3,
                "approval_note": "Reviewed source extracts.",
                "proposal_ids": [p["id"] for p in reversed(run["proposals"])],
            },
        )
        assert saved.status_code == 200, saved.text
        assert [u["action"] for u in saved.json()["draft"]["knowledge_units"]] == actions


def test_reset_removes_task_files_and_linked_progress_only(make_client):
    from app.database import utcnow
    from app.learning.models import Enrollment, ManualCompletion
    from app.models.entities import MediaAsset

    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "expert")
        other = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "title": "Other task",
                "equipment": "Other bench",
            },
        ).json()
        root = client.app.state.settings.media_storage_dir
        for task_id, media_id in [("task_001", "to_clear"), (other["id"], "to_keep")]:
            key = f"{task_id}/{media_id}.mp4"
            path = root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test media")
            with client.app.state.sessionmaker() as session, session.begin():
                session.add(
                    MediaAsset(
                        id=media_id,
                        task_id=task_id,
                        owner_id="expert_001",
                        original_filename="test.mp4",
                        storage_key=key,
                        mime_type="video/mp4",
                        container="mp4",
                        size_bytes=10,
                        sha256="test",
                        duration_ms=1000,
                        video_codec="h264",
                        audio_codec=None,
                        width=100,
                        height=100,
                        status="uploaded",
                    )
                )
        with client.app.state.sessionmaker() as session, session.begin():
            for user_id, release_id in [("linked", "release_001"), ("other", "other_release")]:
                session.add(Enrollment(user_id=user_id, release_id=release_id, context=user_id))
                session.add(
                    ManualCompletion(
                        user_id=user_id,
                        context=user_id,
                        stage="video",
                        completed_at=utcnow(),
                    )
                )
        assert reset(client, headers, 2).status_code == 200
        assert not (root / "task_001/to_clear.mp4").exists()
        assert (root / f"{other['id']}/to_keep.mp4").read_bytes() == b"test media"
        with client.app.state.sessionmaker() as session:
            assert session.get(MediaAsset, "to_clear") is None
            assert session.get(MediaAsset, "to_keep") is not None
            assert session.get(Enrollment, "linked") is None
            assert session.get(Enrollment, "other") is not None
            assert session.get(ManualCompletion, ("linked", "linked", "video")) is None
            assert session.get(ManualCompletion, ("other", "other", "video")) is not None
