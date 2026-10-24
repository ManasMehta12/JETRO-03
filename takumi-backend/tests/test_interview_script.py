from copy import deepcopy
from types import SimpleNamespace

from app.learning import service
from app.learning.interview_script import build_script
from app.models.entities import Draft
from tests.conftest import auth


def test_published_fields_change_script_and_rubric_without_unpublished_input():
    release = SimpleNamespace(
        id="release-2",
        version=2,
        content_hash="approved-hash",
        knowledge_snapshot=[
            {
                "id": "unit",
                "action": "Reviewed inspection",
                "cue": "Reviewed cue",
                "interpretation": "Reviewed interpretation",
                "decision": "Reviewed decision",
                "exception": "Reviewed exception",
                "evidence_ids": ["proof", "unpublished"],
            }
        ],
        evidence_snapshot=[{"id": "proof"}],
    )
    script = build_script(release)
    assert script["source_release_id"] == release.id
    assert script["source_content_hash"] == "approved-hash"
    for field in ("action", "cue", "interpretation", "decision", "exception"):
        assert release.knowledge_snapshot[0][field] in script["bank"][0]["source_context"]
    assert "Reviewed decision" in script["bank"][1]["options"][1]["label"]
    assert "Reviewed exception" in script["bank"][2]["options"][2]["feedback"]
    assert all(o["evidence_ids"] == ["proof"] for q in script["bank"] for o in q["options"])
    changed = deepcopy(release)
    changed.knowledge_snapshot[0]["decision"] = "New tutor approved decision"
    assert build_script(changed)["bundle_hash"] != script["bundle_hash"]
    assert "New tutor approved decision" in build_script(changed)["bank"][1]["options"][1]["label"]


def test_apprentice_interview_uses_release_not_current_draft(make_client):
    with make_client(demo_seed_state="approved_baseline") as client:
        with client.app.state.sessionmaker() as session, session.begin():
            draft = session.get(Draft, "draft_001")
            # Modify an unpublished draft without touching the immutable release.
            units = deepcopy(draft.knowledge_units)
            units[0]["decision"] = "UNPUBLISHED SECRET DECISION"
            draft.knowledge_units = units
            release = service.active_release(session)[1]
            expected = build_script(release)
        headers = auth(client, "apprentice")
        for stage in ("course", "playground"):
            assert (
                client.post(
                    "/api/v1/learning/complete", headers=headers, json={"stage": stage}
                ).status_code
                == 200
            )
        response = client.post("/api/v1/learning/interview", headers=headers)
        assert response.status_code == 200, response.text
        interview = response.json()["interview"]
        assert interview["script_hash"] == expected["bundle_hash"]
        assert interview["source_content_hash"] == expected["source_content_hash"]
        assert "UNPUBLISHED SECRET DECISION" not in response.text
        course = client.get("/api/v1/learning/course", headers=headers).json()
        assert course["release_version"] == 1
        assert "UNPUBLISHED SECRET DECISION" not in str(course)
