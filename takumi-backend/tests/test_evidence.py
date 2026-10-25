import pytest

from app.core.errors import AppError
from app.models.entities import Release, Task
from app.services.evidence_service import validate_evidence_items
from tests.conftest import auth


def test_evidence_read_and_visibility(client):
    reviewer = auth(client, "reviewer")
    apprentice = auth(client, "apprentice")
    response = client.get("/api/v1/evidence/ev_001", headers=reviewer)
    assert response.status_code == 200
    evidence = response.json()
    assert evidence["task_id"] == "task_001"
    assert evidence["source_label"] == "illustrative"
    response = client.get("/api/v1/evidence/ev_001", headers=apprentice)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"
    assert client.get("/api/v1/evidence/missing", headers=reviewer).status_code == 404
    assert client.get("/api/v1/evidence/ev_001").status_code == 401
    with client.app.state.sessionmaker() as session, session.begin():
        session.add(
            Release(
                id="release_test",
                task_id="task_001",
                version=1,
                source_draft_revision=1,
                content_hash="hash",
                approved_by="reviewer_001",
                approval_note="Test",
                task_snapshot={},
                knowledge_snapshot=[],
                evidence_snapshot=[evidence],
            )
        )
    assert client.get("/api/v1/evidence/ev_001", headers=apprentice).status_code == 200
    assert client.get("/api/v1/evidence/ev_003", headers=apprentice).status_code == 404


def test_cross_task_snapshot_does_not_grant_access(client):
    with client.app.state.sessionmaker() as session, session.begin():
        session.add(
            Task(
                id="task_other",
                title="Other",
                equipment="Bench",
                language="en",
                source_label="real",
                owner_id="expert_001",
                status="published",
            )
        )
        session.flush()
        session.add(
            Release(
                id="release_other",
                task_id="task_other",
                version=1,
                source_draft_revision=1,
                content_hash="hash",
                approved_by="reviewer_001",
                approval_note="Test",
                task_snapshot={},
                knowledge_snapshot=[],
                evidence_snapshot=[{"id": "ev_001"}],
            )
        )
    response = client.get("/api/v1/evidence/ev_001", headers=auth(client, "apprentice"))
    assert response.status_code == 404


@pytest.mark.parametrize(
    "items,duration",
    [
        ([{"start_ms": 5, "end_ms": 5}], None),
        ([{"start_ms": 1, "end_ms": 20}], 10),
        ([{"start_ms": 1, "end_ms": 2}] * 2, None),
        ([{"start_ms": -1, "end_ms": 2}], None),
        ([{"start_ms": 1, "end_ms": 2, "media_id": "missing"}], None),
    ],
)
def test_invalid_evidence(items, duration):
    items = [
        {"id": "ev_test", "type": "video_segment", "source_label": "illustrative", **item}
        for item in items
    ]
    with pytest.raises(AppError) as error:
        validate_evidence_items(items, "task_001", duration)
    assert error.value.code == "INVALID_EVIDENCE"
