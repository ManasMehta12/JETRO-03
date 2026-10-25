from copy import deepcopy

import pytest
from sqlalchemy import select

from app.models.entities import Draft, DraftRevision
from app.services.knowledge_service import apply_field_updates
from tests.conftest import auth

PATH = "/api/v1/tasks/task_001/draft"


def patch(client, headers, fields, revision=1, unit="ku_001"):
    return client.patch(
        PATH,
        headers=headers,
        json={
            "expected_revision": revision,
            "changes": [{"knowledge_unit_id": unit, "fields": fields}],
        },
    )


def test_read_and_patch(client):
    headers = auth(client, "reviewer")
    draft = client.get(PATH, headers=headers).json()
    assert draft["revision"] == 1
    assert len(draft["knowledge_units"]) == len(draft["clarifications"]) == 3
    assert [c["id"] for c in draft["clarifications"]] == ["clar_001", "clar_002", "clar_003"]
    response = patch(client, headers, {"action": "Inspect housing visually"})
    assert response.status_code == 200
    result = response.json()
    assert result["revision"] == 2
    evidence_id = result["correction_evidence_ids"][0]
    evidence = client.get(f"/api/v1/evidence/{evidence_id}", headers=headers).json()
    assert evidence["type"] == "reviewer_correction"
    assert evidence["author"] == "Demo Reviewer"
    unit = client.get(PATH, headers=headers).json()["knowledge_units"][0]
    assert unit["action"] == "Inspect housing visually"
    assert evidence_id in unit["field_evidence"]["action"]
    stale = patch(client, headers, {"cue": "x"})
    assert stale.status_code == 409
    assert stale.json()["error"]["details"] == {"expected": 1, "actual": 2}
    with client.app.state.sessionmaker() as session:
        revisions = session.scalars(select(DraftRevision).order_by(DraftRevision.revision)).all()
        assert [row.revision for row in revisions] == [1, 2]
        assert revisions[0].knowledge_units[0]["action"] == "Inspect the bearing housing"


@pytest.mark.parametrize(
    "fields",
    [
        {"evidence_ids": ["ev_fake"]},
        {"review_status": "approved"},
        {},
        {"action": None},
        {"cue": "   "},
    ],
)
def test_reject_invalid_fields(client, fields):
    headers = auth(client, "expert")
    assert patch(client, headers, fields).status_code == 422
    assert client.get(PATH, headers=headers).json()["revision"] == 1


def test_unknown_and_duplicate_units_are_atomic(client):
    headers = auth(client, "expert")
    changes = [
        {"knowledge_unit_id": "ku_001", "fields": {"cue": "new"}},
        {"knowledge_unit_id": "missing", "fields": {"cue": "new"}},
    ]
    result = client.patch(PATH, headers=headers, json={"expected_revision": 1, "changes": changes})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "KNOWLEDGE_UNIT_NOT_FOUND"
    changes[1] = changes[0]
    result = client.patch(PATH, headers=headers, json={"expected_revision": 1, "changes": changes})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"
    with client.app.state.sessionmaker() as session:
        assert session.scalar(select(Draft)).revision == 1
    assert client.get(PATH, headers=auth(client, "apprentice")).status_code == 403


def test_clear_and_noop(client):
    headers = auth(client, "expert")
    response = patch(client, headers, {"cue": None}, unit="ku_002")
    assert response.status_code == 200
    unit = client.get(PATH, headers=headers).json()["knowledge_units"][1]
    assert unit["cue"] is None
    assert "cue" not in unit["field_evidence"]
    assert unit["evidence_ids"] == ["ev_003", *response.json()["correction_evidence_ids"]]
    response = patch(client, headers, {"cue": None}, revision=2, unit="ku_002")
    assert response.json()["revision"] == 3
    assert response.json()["correction_evidence_ids"] == []


def test_apply_field_updates_is_pure():
    unit = {
        "action": "x",
        "cue": "y",
        "field_evidence": {"cue": ["old"]},
        "evidence_ids": ["old"],
        "review_status": "draft",
    }
    original = deepcopy(unit)
    result = apply_field_updates(unit, {"cue": "new"}, "ev_new")
    assert unit == original
    assert result["field_evidence"]["cue"] == ["old", "ev_new"]
    assert apply_field_updates(result, {"cue": "newer"}, "ev_new")["evidence_ids"] == [
        "old",
        "ev_new",
    ]
