"""Acceptance checks written against the specification before API implementation.

Fixture provider responses exercise orchestration without making network calls.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def api(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'acceptance.db'}", provider_mode="fixture")
    with TestClient(create_app(settings)) as client:
        yield client


def headers(token="demo-learner-token", key=None):
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key or str(uuid4())}


def start(api, attempt="attempt-demo-success", key=None):
    response = api.post("/api/v1/viva/sessions", headers=headers(key=key),
                        json={"attempt_id": attempt, "input_mode": "text"})
    assert response.status_code == 200, response.text
    return response.json()


def test_requires_auth_and_hides_another_learners_attempt(api):
    assert api.get("/api/v1/demo/bootstrap").status_code == 401
    result = api.post("/api/v1/viva/sessions", headers=headers(),
                      json={"attempt_id": "attempt-other", "input_mode": "text"})
    assert result.status_code == 404


def test_session_bound_to_original_release_and_unique_per_attempt(api):
    first = start(api)
    again = start(api)
    assert first["id"] == again["id"]
    assert first["release_id"] == "release-demo-v1"
    assert first["bundle_hash"]
    assert first["rubric_version"]
    assert "rubric" not in first
    assert "answer_key" not in first


def test_session_read_and_events_require_owner(api):
    session = start(api)
    for suffix in ("", "/events", "/evaluation", "/result"):
        result = api.get(f"/api/v1/viva/sessions/{session['id']}{suffix}",
                         headers=headers("demo-other-token"))
        assert result.status_code == 404, (suffix, result.text)


def test_idempotent_answer_does_not_duplicate_turn(api):
    session = start(api)
    path = f"/api/v1/viva/sessions/{session['id']}/answers"
    body = {"expected_revision": session["revision"], "question_id": session["current_question"]["id"],
            "client_turn_id": "acceptance-turn-1", "text": "I inspect the housing and gather the required observations before choosing a check."}
    key = str(uuid4())
    first = api.post(path, headers=headers(key=key), json=body)
    replay = api.post(path, headers=headers(key=key), json=body)
    assert first.status_code == 202, first.text
    assert replay.status_code == 202
    assert first.json() == replay.json()
    changed = api.post(path, headers=headers(key=key), json={**body, "text": "Changed content"})
    assert changed.status_code == 409
    restored = api.get(f"/api/v1/viva/sessions/{session['id']}", headers=headers()).json()
    learner_turns = [turn for turn in restored.get("transcript", []) if turn["speaker"] == "learner"]
    assert len(learner_turns) == 1


def test_stale_revision_cannot_pause_progress(api):
    session = start(api)
    response = api.post(f"/api/v1/viva/sessions/{session['id']}/pause", headers=headers(),
                        json={"expected_revision": session["revision"] + 100})
    assert response.status_code == 409
    restored = api.get(f"/api/v1/viva/sessions/{session['id']}", headers=headers()).json()
    assert restored["status"] == session["status"]


def test_wrong_question_answer_rejected_without_progress(api):
    session = start(api)
    response = api.post(f"/api/v1/viva/sessions/{session['id']}/answers", headers=headers(), json={
        "expected_revision": session["revision"], "question_id": "not-the-current-question",
        "client_turn_id": "wrong-question", "text": "An otherwise nonempty answer."})
    assert response.status_code in (409, 422)
    restored = api.get(f"/api/v1/viva/sessions/{session['id']}", headers=headers()).json()
    assert restored["revision"] == session["revision"]


def test_finish_is_unique_even_with_new_key_and_stale_revision(api):
    session = start(api)
    path = f"/api/v1/viva/sessions/{session['id']}/finish"
    body = {"expected_revision": session["revision"]}
    first = api.post(path, headers=headers(), json=body)
    second = api.post(path, headers=headers(), json=body)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["id"] == second.json()["id"]


def test_durable_events_are_ordered_and_cursor_does_not_repeat(api):
    session = start(api)
    path = f"/api/v1/viva/sessions/{session['id']}/events"
    response = api.get(path, headers=headers())
    assert response.status_code == 200
    first = response.json()
    sequences = [event["sequence"] for event in first["events"]]
    assert sequences == sorted(set(sequences))
    cursor = first["next_after"]
    second = api.get(path, headers=headers(), params={"after": cursor}).json()
    assert all(event["sequence"] > cursor for event in second["events"])


def test_result_not_available_before_finish(api):
    session = start(api)
    response = api.get(f"/api/v1/viva/sessions/{session['id']}/result", headers=headers())
    assert response.status_code == 409


def test_source_manifest_is_release_scoped(api):
    start(api)
    release = api.get("/api/v1/studio/releases/release-demo-v1", headers=headers())
    assert release.status_code == 200, release.text
    documents = release.json()["documents"]
    assert documents
    for doc in documents:
        resolved = api.get(f"/api/v1/studio/releases/release-demo-v1/documents/{doc['id']}", headers=headers())
        assert resolved.status_code == 200, resolved.text
    invalid = api.get("/api/v1/studio/releases/wrong-release/documents/unknown", headers=headers())
    assert invalid.status_code == 404


def test_early_finish_report_is_incomplete_and_indexes_entire_release(api):
    session = start(api)
    base = f"/api/v1/viva/sessions/{session['id']}"
    response = api.post(base + "/finish", headers=headers(),
                        json={"expected_revision": session["revision"]})
    assert response.status_code == 202, response.text
    result = api.get(base + "/result", headers=headers())
    assert result.status_code == 200, result.text
    report = result.json()
    assert report["completion"] == "incomplete"
    assert report["release_id"] == session["release_id"]
    assert report["bundle_hash"] == session["bundle_hash"]
    release = api.get("/api/v1/studio/releases/release-demo-v1", headers=headers()).json()
    expected = {doc["id"] for doc in release["documents"]}
    actual = {item["document"]["id"] for item in report["source_index"]}
    assert actual == expected
    assert all(item["score"] is None for item in report["assessments"])


def test_critical_playground_error_survives_viva_report(api):
    session = start(api, attempt="attempt-demo-critical")
    base = f"/api/v1/viva/sessions/{session['id']}"
    while session["status"] == "in_progress":
        response = api.post(base + "/answers", headers=headers(), json={
            "expected_revision": session["revision"],
            "question_id": session["current_question"]["id"], "client_turn_id": str(uuid4()),
            "text": "I compare observations against the approved evidence, reassess conflicting conditions, and stop and escalate when the evidence is insufficient."})
        assert response.status_code == 202, response.text
        session = response.json()["session"]
    report_response = api.get(base + "/result", headers=headers())
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["critical_error"] is True
    assert report["playground_scores"]
    valid_turns = {turn["id"] for turn in report["transcript"] if turn["speaker"] == "learner"}
    release = api.get("/api/v1/studio/releases/release-demo-v1", headers=headers()).json()
    evidence_ids = {evidence["id"] for evidence in release["evidence"]}
    for assessment in report["assessments"]:
        assert set(assessment["answer_turn_ids"]) <= valid_turns
        for source in assessment["sources"]:
            assert source["evidence_id"] in evidence_ids


def test_fixture_voice_cannot_claim_a_live_connection(api):
    result = api.post("/api/v1/viva/sessions", headers=headers(),
                      json={"attempt_id": "attempt-demo-success", "input_mode": "voice"})
    assert result.status_code == 200, result.text
    session = result.json()
    response = api.post(f"/api/v1/viva/sessions/{session['id']}/connection", headers=headers(), json={
        "expected_revision": session["revision"], "sdp_offer": "v=0\r\n", "microphone_consent": True})
    assert response.status_code == 503, response.text
    assert "sdp_answer" not in response.json()


def test_guarded_reset_requires_confirmation_and_preserves_knowledge(api):
    from app.cli import reset_demo
    from sqlalchemy import select
    from app.models import Release, VivaSession
    session = start(api)
    with pytest.raises(RuntimeError):
        reset_demo(api.app.state.db, confirm=False)
    counts = reset_demo(api.app.state.db, confirm=True)
    assert counts['viva_sessions'] == 1
    with api.app.state.db.session_factory() as db:
        assert db.get(Release, 'release-demo-v1') is not None
        assert db.get(VivaSession, session['id']) is None


def test_reset_then_seed_restores_attempts_without_republishing_release(api):
    from app.cli import reset_demo
    from app.seed import seed
    before = api.get('/api/v1/studio/releases/release-demo-v1', headers=headers()).json()
    reset_demo(api.app.state.db, confirm=True)
    seed(api.app.state.db)
    attempts = api.get('/api/v1/demo/bootstrap', headers=headers()).json()['attempts']
    assert attempts
    after = api.get('/api/v1/studio/releases/release-demo-v1', headers=headers()).json()
    assert before == after
