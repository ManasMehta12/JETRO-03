import ast
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.learning import service
from app.learning.interview_script import build_script
from app.learning.replay import replay
from tests.conftest import auth

BASE = "/api/v1/learning"


def actions(scenario="standard"):
    steps = [
        "inspect-base",
        "inspect-housing",
        "inspect-shaft",
        "inspect-bearing",
        "record-observation",
    ]
    workshop = [
        "pick:base",
        "place:base",
        "pick:housing",
        "place:housing",
        "tool:alignment-jig",
        "adjust:left",
        "adjust:left",
        "pick:shaft",
        "place:shaft",
        "tool:bearing-sleeve",
        "pick:bearing",
        "place:bearing",
        "press",
        "press",
        "press",
        "tool:hex-key",
        "tighten:A",
        "tighten:C",
        "tighten:B",
        "tighten:D",
        "tool:handwheel",
        "turn",
        "turn",
        "turn",
        "verify",
    ]
    return (
        steps
        + [f"workshop:{s}" for s in workshop]
        + [
            "answer:q1:b",
            "answer:q2:b",
            "answer:q3:c",
            "continue" if scenario == "standard" else "escalate",
        ]
    )


def watch(client, headers, monkeypatch):
    now = [datetime(2026, 10, 25, tzinfo=UTC)]
    monkeypatch.setattr(service, "utcnow", lambda: now[0])
    started = client.post(BASE + "/playback", headers=headers)
    assert started.status_code == 200, started.text
    sid = started.json()["session_id"]
    for pos in range(10, 61, 10):
        now[0] += timedelta(seconds=10)
        result = client.post(
            BASE + f"/playback/{sid}", json={"position_seconds": pos}, headers=headers
        )
        assert result.status_code == 200, result.text
    return result.json()


def test_missing_video_and_early_gates(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "apprentice")
        assert client.get(BASE + "/course", headers=headers).json()["video_configured"] is False
        assert client.post(BASE + "/playback", headers=headers).status_code == 409
        assert (
            client.post(
                BASE + "/playground",
                headers=headers,
                json={"scenario": "standard", "mode": "guided", "actions": actions()},
            ).status_code
            == 409
        )
        assert client.post(BASE + "/interview", headers=headers).status_code == 409
        assert not client.get(BASE + "/progress", headers=headers).json()["course_completed"]
        assert client.get(BASE + "/course", headers=auth(client, "expert")).status_code == 403


def test_requires_reviewed_release(make_client):
    with make_client(course_video_url="https://example.org/course.mp4") as client:
        headers = auth(client, "apprentice")
        assert client.post(BASE + "/playback", headers=headers).status_code == 409


def test_seeking_ownership_and_release_gate(make_client, monkeypatch):
    with make_client(
        demo_seed_state="approved_baseline", course_video_url="https://example.org/course.mp4"
    ) as client:
        headers = auth(client, "apprentice")
        now = datetime(2026, 10, 25, tzinfo=UTC)
        monkeypatch.setattr(service, "utcnow", lambda: now)
        sid = client.post(BASE + "/playback", headers=headers).json()["session_id"]
        assert (
            client.post(
                BASE + f"/playback/{sid}", headers=headers, json={"position_seconds": 60}
            ).status_code
            == 409
        )
        client.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            "other", "apprentice", "Other"
        )
        assert (
            client.post(
                BASE + f"/playback/{sid}", headers=headers, json={"position_seconds": 0}
            ).status_code
            == 404
        )
        client.app.dependency_overrides.pop(get_current_user, None)
        assert client.get(BASE + "/progress", headers=headers).json()["watched_seconds"] == 0


def test_complete_journey_replay_private_grades_and_idempotency(make_client, monkeypatch):
    with make_client(
        demo_seed_state="approved_baseline", course_video_url="https://example.org/course.mp4"
    ) as client:
        headers = auth(client, "apprentice")
        assert watch(client, headers, monkeypatch)["playground_unlocked"]
        payload = {"scenario": "standard", "mode": "assessment", "actions": ["continue"]}
        assert client.post(BASE + "/playground", headers=headers, json=payload).status_code == 422
        payload["actions"] = actions()
        payload["scores"] = {"judgment": 100}
        assert client.post(BASE + "/playground", headers=headers, json=payload).status_code == 422
        del payload["scores"]
        result = client.post(BASE + "/playground", headers=headers, json=payload).json()
        assert result["playground_result"]["scores"] == {
            "procedure": 100,
            "judgment": 100,
            "knowledge": 100,
        }
        assert result["interview_unlocked"]
        assert client.post(BASE + "/playground", headers=headers, json=payload).json() == result
        started = client.post(BASE + "/interview", headers=headers).json()
        interview = started["interview"]
        assert client.post(BASE + "/interview", headers=headers).json() == started
        assert "points" not in str(interview["current_question"])
        assert "bank" not in interview
        wrong = {
            "session_id": interview["id"],
            "question_id": "evidence-limits",
            "option_id": "c",
            "expected_revision": 0,
        }
        assert (
            client.post(BASE + "/interview/answers", headers=headers, json=wrong).status_code == 422
        )
        receipts = []
        for index, choice in enumerate(["b", "b", "c"]):
            request = {
                "session_id": interview["id"],
                "question_id": interview["current_question"]["id"],
                "option_id": choice,
                "expected_revision": index,
                "reflection": "Ungraded reflection",
            }
            response = client.post(BASE + "/interview/answers", headers=headers, json=request)
            assert response.status_code == 200, response.text
            if index == 0:
                stale = {**request, "option_id": "a"}
                assert (
                    client.post(
                        BASE + "/interview/answers", headers=headers, json=stale
                    ).status_code
                    == 409
                )
                client.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
                    "other", "apprentice", "Other"
                )
                assert (
                    client.post(
                        BASE + "/interview/answers", headers=headers, json=request
                    ).status_code
                    == 404
                )
                client.app.dependency_overrides.pop(get_current_user, None)
            receipts.append((request, response.json()))
            interview = response.json()["interview"]
        assert interview["status"] == "completed"
        assert interview["result"]["explanation_points"] == 6
        assert interview["current_question"] is None
        for request, stored in receipts:
            assert (
                client.post(BASE + "/interview/answers", headers=headers, json=request).json()
                == stored
            )
        assert (
            client.get(BASE + "/progress", headers=headers).json()["interview"]["status"]
            == "completed"
        )
        # A different playback source invalidates the old course completion and downstream results.
        client.app.state.settings.course_video_url = "https://example.org/new.mp4"
        reset = client.get(BASE + "/progress", headers=headers).json()
        assert not reset["course_completed"] and reset["interview"] is None


def test_replay_retains_critical_error_and_new_attempt_clears_interview(make_client, monkeypatch):
    with make_client(
        demo_seed_state="approved_baseline", course_video_url="https://example.org/course.mp4"
    ) as client:
        headers = auth(client, "apprentice")
        watch(client, headers, monkeypatch)
        payload = {
            "scenario": "uncertain",
            "mode": "guided",
            "actions": actions("uncertain")[:-1] + ["continue"],
        }
        result = client.post(BASE + "/playground", headers=headers, json=payload).json()
        assert result["playground_result"]["critical_error"]
        assert result["playground_result"]["scores"]["judgment"] == 0
        client.post(BASE + "/interview", headers=headers)
        payload["actions"] = actions("uncertain")
        assert (
            client.post(BASE + "/playground", headers=headers, json=payload).json()["interview"]
            is None
        )


@pytest.mark.parametrize(
    "bad",
    [
        "align-shaft",
        "seat-bearing",
        "verify-fit",
        "record-observation",
        "workshop:pick:base",
        "answer:q1:b:extra",
    ],
)
def test_replay_rejects_legacy_or_out_of_order_actions(bad):
    with pytest.raises(AppError):
        replay([bad], "standard")


def test_replay_matches_frontend_shared_action_fixture():
    # Read the exact authored histories consumed by the TypeScript simulation tests.
    fixture = Path(__file__).resolve().parents[2] / "src" / "test-fixtures.ts"
    source = fixture.read_text(encoding="utf-8")

    def array(name):
        match = re.search(r"const " + name + r" = (\[[\s\S]*?\]);?", source)
        return ast.literal_eval(match.group(1))

    history = (
        array("inspectionActions")
        + ["workshop:" + action for action in array("workshopActions")]
        + array("quizActions")
    )
    assert replay(history + ["continue"], "standard")["scores"] == {
        "procedure": 100,
        "judgment": 100,
        "knowledge": 100,
    }
    assert replay(history + ["continue"], "uncertain")["critical_error"]
    assert replay(history + ["escalate"], "uncertain")["scores"]["judgment"] == 100
    broken = history.copy()
    broken[broken.index("workshop:tighten:A")] = "workshop:tighten:B"
    with pytest.raises(AppError):
        replay(broken + ["continue"], "standard")


def test_manual_sequential_completion_and_unassessed_interview(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "apprentice")
        assert (
            client.post(
                BASE + "/complete", headers=headers, json={"stage": "playground"}
            ).status_code
            == 409
        )
        course = client.post(BASE + "/complete", headers=headers, json={"stage": "course"}).json()
        assert course["course_completed"] and course["playground_unlocked"]
        assert not course["interview_unlocked"]
        assert course["watched_seconds"] == 0 and course["playground_result"] is None
        assert "course" in course["manual_completion"]
        assert (
            client.post(BASE + "/complete", headers=headers, json={"stage": "course"}).json()
            == course
        )
        playground = client.post(
            BASE + "/complete", headers=headers, json={"stage": "playground"}
        ).json()
        assert playground["interview_unlocked"] and playground["playground_result"] is None
        assert "playground" in playground["manual_completion"]
        assert client.get(BASE + "/progress", headers=headers).json() == playground
        interview = client.post(BASE + "/interview", headers=headers).json()["interview"]
        for index, choice in enumerate(["b", "b", "c"]):
            request = {
                "session_id": interview["id"],
                "question_id": interview["current_question"]["id"],
                "option_id": choice,
                "expected_revision": index,
            }
            response = client.post(BASE + "/interview/answers", headers=headers, json=request)
            assert response.status_code == 200, response.text
            interview = response.json()["interview"]
        assert interview["status"] == "completed"
        assert interview["result"]["playground_assessed"] is False
        assert interview["result"]["critical_playground_error"] is False
        assert "no simulation score recorded" in interview["result"]["notice"]
        assert client.get(BASE + "/progress", headers=headers).json()["playground_result"] is None


def test_manual_completion_requires_release_and_is_scoped_to_user(make_client):
    with make_client() as client:
        headers = auth(client, "apprentice")
        assert (
            client.post(BASE + "/complete", headers=headers, json={"stage": "course"}).status_code
            == 409
        )


def test_reset_progress_clears_all_student_knowledge(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        headers = auth(client, "apprentice")
        # Complete course & playground stages
        for stage in ["course", "playground"]:
            client.post(BASE + "/complete", headers=headers, json={"stage": stage})
        client.post(BASE + "/interview", headers=headers)
        progress = client.get(BASE + "/progress", headers=headers).json()
        assert progress["course_completed"] is True
        assert progress["playground_unlocked"] is True
        assert progress["interview_unlocked"] is True
        assert progress["interview"] is not None

        # Reset all student progress
        reset_res = client.post(BASE + "/reset", headers=headers)
        assert reset_res.status_code == 200
        cleared = reset_res.json()
        assert cleared["watched_seconds"] == 0
        assert cleared["course_completed"] is False
        assert cleared["playground_unlocked"] is False
        assert cleared["interview_unlocked"] is False
        assert cleared["playground_result"] is None
        assert cleared["interview"] is None
        assert cleared["manual_completion"] == {}

        # Verify get /progress matches cleared
        refetched = client.get(BASE + "/progress", headers=headers).json()
        assert refetched == cleared


@pytest.mark.parametrize("question_index", range(3))
@pytest.mark.parametrize("option_index", range(3))
def test_private_rubric_option_matrix(make_client, question_index, option_index):
    with make_client(demo_seed_state="approved_baseline") as client:
        with client.app.state.sessionmaker() as session:
            bank = build_script(service.active_release(session)[1])["bank"]
        headers = auth(client, "apprentice")
        for stage in ["course", "playground"]:
            client.post(BASE + "/complete", headers=headers, json={"stage": stage})
        interview = client.post(BASE + "/interview", headers=headers).json()["interview"]
        for index in range(question_index + 1):
            option = bank[index]["options"][option_index if index == question_index else 0]
            request = {
                "session_id": interview["id"],
                "question_id": bank[index]["id"],
                "option_id": option["id"],
                "expected_revision": index,
                "reflection": "This text must never affect points.",
            }
            response = client.post(BASE + "/interview/answers", headers=headers, json=request)
            assert response.status_code == 200, response.text
            interview = response.json()["interview"]
            recorded = interview["answers"][-1]
            assert recorded["feedback"] == option["feedback"]
            assert recorded["points"] == option["points"]
            assert recorded["recognizes_limits"] == option["recognizes_limits"]
            assert set(recorded["evidence_ids"]) <= set(option["evidence_ids"])
