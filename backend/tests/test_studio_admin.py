from tests.conftest import auth

BASE = "/api/v1/studio/tasks/task_001"


def resolve_gaps(client, expert):
    draft = client.get(BASE, headers=expert).json()["draft"]
    for gap in draft["clarifications"]:
        if gap["status"] == "pending":
            response = client.post(
                f"/api/v1/clarifications/{gap['id']}/respond",
                headers=expert,
                json={
                    "expected_draft_revision": draft["revision"],
                    "disposition": "deferred",
                    "answer": "Tutor review deferred this unanswered observation; no claim added.",
                },
            )
            assert response.status_code == 200
    return draft["revision"]


def test_admin_authorizes_evaluated_revision_expert_publishes(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        expert, admin, apprentice = (
            auth(client, role) for role in ("expert", "admin", "apprentice")
        )
        assert client.get(BASE, headers=apprentice).status_code == 403
        revision = resolve_gaps(client, expert)
        # Create a new correction without altering the already published snapshot.
        draft = client.get(BASE, headers=expert).json()["draft"]
        change = {
            "expected_revision": revision,
            "changes": [
                {
                    "knowledge_unit_id": draft["knowledge_units"][0]["id"],
                    "fields": {
                        "decision": "Pause and ask the instructor to review the observed condition."
                    },
                }
            ],
        }
        assert (
            client.patch("/api/v1/tasks/task_001/draft", headers=expert, json=change).status_code
            == 200
        )
        revision += 1
        req = {
            "expected_revision": revision,
            "approval_note": "Reviewed supporting evidence and limits.",
        }
        assert client.post(BASE + "/publish", headers=expert, json=req).status_code == 403
        evaluation = client.post(
            BASE + "/evaluate", headers=expert, json={"expected_revision": revision}
        ).json()
        assert evaluation["passed"] is True
        grant = {
            "evaluation_id": evaluation["id"],
            "expert_id": "expert_001",
            "note": "Checked technical accuracy and evidence.",
        }
        assert client.post(BASE + "/authorize", headers=expert, json=grant).status_code == 403
        assert client.post(BASE + "/authorize", headers=admin, json=grant).status_code == 200
        published = client.post(BASE + "/publish", headers=expert, json=req)
        assert published.status_code == 200, published.text
        release_id = published.json()["id"]
        assert (
            client.get("/api/v1/learning/course", headers=apprentice).json()["release_id"]
            == release_id
        )
        assert client.post(BASE + "/publish", headers=expert, json=req).json()["id"] == release_id
        overview = client.get(BASE, headers=admin).json()
        assert overview["authorization"]["status"] == "published"
        events = overview["audit"]
        assert sum(row["action"] == "published" for row in events) == 1
        assert {row["action"] for row in events} >= {
            "evaluated",
            "authorized",
            "published",
            "draft_updated",
        }
        assert all(row["actor_id"] and row["created_at"] for row in events)


def test_changed_revision_invalidates_evaluation_and_authorization(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        expert, admin = auth(client, "expert"), auth(client, "admin")
        revision = resolve_gaps(client, expert)
        evaluation = client.post(
            BASE + "/evaluate", headers=expert, json={"expected_revision": revision}
        ).json()
        grant = {"evaluation_id": evaluation["id"], "note": "Reviewed", "expert_id": "expert_001"}
        assert client.post(BASE + "/authorize", headers=admin, json=grant).status_code == 200
        draft = client.get(BASE, headers=expert).json()["draft"]
        client.patch(
            "/api/v1/tasks/task_001/draft",
            headers=expert,
            json={
                "expected_revision": revision,
                "changes": [
                    {
                        "knowledge_unit_id": draft["knowledge_units"][0]["id"],
                        "fields": {"decision": "Seek instructor review before proceeding."},
                    }
                ],
            },
        )
        assert (
            client.post(BASE + "/authorize", headers=admin, json=grant).json()["error"]["code"]
            == "EVALUATION_STALE"
        )
        assert (
            client.post(
                BASE + "/publish",
                headers=expert,
                json={"expected_revision": revision + 1, "approval_note": "Reviewed"},
            ).json()["error"]["code"]
            == "AUTHORIZATION_REQUIRED"
        )
        overview = client.get(BASE, headers=admin).json()
        assert overview["authorization"]["status"] == "stale"
        assert overview["evaluation"]["stale"] is True


def test_unresolved_clarifications_block_authorization(client):
    expert, admin = auth(client, "expert"), auth(client, "admin")
    evaluation = client.post(
        BASE + "/evaluate", headers=expert, json={"expected_revision": 1}
    ).json()
    assert evaluation["passed"] is False
    assert any(
        issue["problem"].startswith("UNRESOLVED_CLARIFICATION") for issue in evaluation["issues"]
    )
    result = client.post(
        BASE + "/authorize",
        headers=admin,
        json={"evaluation_id": evaluation["id"], "note": "Review"},
    )
    assert result.json()["error"]["code"] == "EVALUATION_FAILED"


def test_failed_evidence_evaluation_cannot_be_authorized(client):
    from sqlalchemy import select

    from app.models.entities import Draft

    expert, admin = auth(client, "expert"), auth(client, "admin")
    resolve_gaps(client, expert)
    with client.app.state.sessionmaker() as session, session.begin():
        draft = session.scalar(select(Draft).where(Draft.task_id == "task_001"))
        units = list(draft.knowledge_units)
        units[0] = {**units[0], "field_evidence": {}}
        draft.knowledge_units = units
    evaluation = client.post(
        BASE + "/evaluate", headers=expert, json={"expected_revision": 1}
    ).json()
    assert evaluation["passed"] is False
    assert any(issue["problem"].startswith("UNSUPPORTED_FIELD") for issue in evaluation["issues"])
    assert (
        client.post(
            BASE + "/authorize",
            headers=admin,
            json={"evaluation_id": evaluation["id"], "note": "Review"},
        ).status_code
        == 409
    )
