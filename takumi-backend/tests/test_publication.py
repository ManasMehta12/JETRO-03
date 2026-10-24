import hashlib
import json
from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DatabaseError

from app.core.security import CurrentUser
from app.models.entities import Draft, Release, Task
from app.models.schemas import PublishRequest
from app.services.publication_service import publish
from tests.conftest import auth


def publish_request(client, revision=1, role="reviewer"):
    if role == "reviewer":
        # Publication now has the same human review/evaluation gate on every API route.
        expert = auth(client, "expert")
        draft = client.get("/api/v1/tasks/task_001/draft", headers=expert).json()
        for gap in draft["clarifications"]:
            if gap["status"] == "pending":
                client.post(
                    f"/api/v1/clarifications/{gap['id']}/respond",
                    headers=expert,
                    json={
                        "expected_draft_revision": draft["revision"],
                        "disposition": "deferred",
                        "answer": "Explicitly deferred for review.",
                    },
                )
        client.post(
            "/api/v1/studio/tasks/task_001/evaluate",
            headers=expert,
            json={"expected_revision": revision},
        )
    return client.post(
        "/api/v1/tasks/task_001/publish",
        headers=auth(client, role),
        json={
            "expected_revision": revision,
            "approval_note": "Reviewed illustrative training pack.",
        },
    )


def edit_draft(app, edit):
    with app.state.sessionmaker() as session, session.begin():
        draft = session.get(Draft, "draft_001")
        units = deepcopy(draft.knowledge_units)
        edit(units)
        draft.knowledge_units = units
        draft.revision += 1
    return draft.revision


@pytest.mark.parametrize("role", ["expert", "apprentice"])
def test_publish_reviewer_only(client, role):
    response = publish_request(client, role=role)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_publish_and_retry(client):
    response = publish_request(client)
    assert response.status_code == 201
    result = response.json()
    assert result["version"] == 1
    assert len(result["content_hash"]) == 64
    int(result["content_hash"], 16)
    headers = auth(client, "apprentice")
    release = client.get("/api/v1/tasks/task_001/release", headers=headers).json()
    assert release["id"] == result["release_id"]
    assert all(unit["review_status"] == "approved" for unit in release["knowledge_units"])
    assert [item["id"] for item in release["evidence_items"]] == ["ev_001", "ev_003", "ev_004"]
    content = json.dumps(
        {
            "knowledge_units": release["knowledge_units"],
            "evidence_items": release["evidence_items"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert result["content_hash"] == hashlib.sha256(content.encode()).hexdigest()
    retry = publish_request(client)
    assert retry.status_code == 200
    assert retry.json() == result
    with client.app.state.sessionmaker() as session:
        assert all(
            unit["review_status"] == "draft"
            for unit in session.get(Draft, "draft_001").knowledge_units
        )


def test_publication_blocked_and_stale(client):
    edit_draft(client.app, lambda units: units[2].update(cue="unsupported observation"))
    blocked = publish_request(client, 2)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PUBLICATION_BLOCKED"
    assert {"knowledge_unit_id": "ku_003", "problem": "UNSUPPORTED_FIELD:cue"} in (
        blocked.json()["error"]["details"]["issues"]
    )
    stale = publish_request(client)
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["actual"] == 2


def test_immutable_snapshot_and_superseded_status(client):
    release_id = publish_request(client).json()["release_id"]
    headers = auth(client, "reviewer")
    path = f"/api/v1/releases/{release_id}"
    original = client.get(path, headers=headers).content
    edit_draft(client.app, lambda units: units[2].update(action="Inspect base fasteners"))
    assert client.get(path, headers=headers).content == original
    assert publish_request(client).json()["error"]["code"] == "REVISION_CONFLICT"
    next_release = publish_request(client, 2).json()
    assert next_release["version"] == 2
    assert (
        client.get("/api/v1/tasks/task_001/release", headers=headers).json()["id"]
        == (next_release["release_id"])
    )
    assert client.get(path, headers=headers).json()["status"] == "superseded"
    response = client.patch(path, headers=headers, json={})
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    with client.app.state.sessionmaker() as session:
        release = session.get(Release, release_id)
        release.approval_note = "Attempted mutation"
        with pytest.raises(DatabaseError, match="releases are immutable"):
            session.flush()
        session.rollback()


def test_cross_task_evidence_blocked(client):
    with client.app.state.sessionmaker() as session, session.begin():
        session.add(
            Task(
                id="task_other",
                title="Other",
                equipment="Bench",
                language="en",
                source_label="real",
                owner_id="expert_001",
                status="draft",
            )
        )
        session.flush()
        units = deepcopy(session.get(Draft, "draft_001").knowledge_units[:1])
        session.add(
            Draft(
                id="draft_other",
                task_id="task_other",
                revision=1,
                status="draft",
                knowledge_units=units,
            )
        )
    response = client.post(
        "/api/v1/tasks/task_other/publish",
        headers=auth(client, "reviewer"),
        json={"expected_revision": 1, "approval_note": "Review"},
    )
    assert response.status_code == 409
    assert {"knowledge_unit_id": "ku_001", "problem": "INVALID_EVIDENCE:ev_001"} in (
        response.json()["error"]["details"]["issues"]
    )


@pytest.mark.parametrize(
    "path,code",
    [
        ("/tasks/absent/release", "NO_ACTIVE_RELEASE"),
        ("/tasks/task_001/release", "NO_ACTIVE_RELEASE"),
        ("/releases/absent", "RELEASE_NOT_FOUND"),
    ],
)
def test_missing_release(client, path, code):
    response = client.get(f"/api/v1{path}", headers=auth(client, "apprentice"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == code


def test_publish_outer_rollback(client):
    with client.app.state.sessionmaker() as session:
        publish(
            session,
            "task_001",
            PublishRequest(expected_revision=1, approval_note="Review"),
            CurrentUser("reviewer_001", "reviewer", "Demo Reviewer"),
        )
        session.rollback()
    with client.app.state.sessionmaker() as session:
        assert session.scalar(select(func.count()).select_from(Release)) == 0
        assert session.get(Task, "task_001").active_release_id is None


@pytest.mark.parametrize(
    "change,problem",
    [
        (lambda units: units.clear(), "EMPTY_DRAFT"),
        (lambda units: units[0].update(action=""), "MISSING_ACTION"),
        (
            lambda units: units[0]["evidence_ids"].append("ev_missing"),
            "INVALID_EVIDENCE:ev_missing",
        ),
    ],
)
def test_publication_validation(client, change, problem):
    edit_draft(client.app, change)
    response = publish_request(client, 2)
    assert response.status_code == 409
    assert problem in [issue["problem"] for issue in response.json()["error"]["details"]["issues"]]
