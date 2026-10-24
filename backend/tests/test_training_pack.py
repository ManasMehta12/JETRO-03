from tests.conftest import auth
from tests.test_publication import edit_draft, publish_request


def test_training_pack_snapshot(client):
    release_id = publish_request(client).json()["release_id"]
    path = f"/api/v1/releases/{release_id}/training-pack"
    headers = auth(client, "apprentice")
    response = client.get(path, headers=headers)
    assert response.status_code == 200
    pack = response.json()
    assert pack["schema_version"] == "1.0"
    assert pack["release_id"] == release_id
    assert pack["source_label"] == "illustrative"
    assert [unit["id"] for unit in pack["knowledge_units"]] == ["ku_001", "ku_002", "ku_003"]
    evidence_ids = {item["id"] for item in pack["evidence_items"]}
    for unit in pack["knowledge_units"]:
        assert "review_status" not in unit
        assert set(unit["evidence_ids"]) <= evidence_ids
        assert all(set(ids) <= evidence_ids for ids in unit["field_evidence"].values())
    edit_draft(client.app, lambda units: units[2].update(action="Draft-only action"))
    assert client.get(path, headers=headers).content == response.content


def test_training_pack_disabled(make_client):
    with make_client(enable_training_pack_export=False) as client:
        release_id = publish_request(client).json()["release_id"]
        response = client.get(
            f"/api/v1/releases/{release_id}/training-pack", headers=auth(client, "apprentice")
        )
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "FEATURE_DISABLED"


def test_training_pack_missing(client):
    response = client.get("/api/v1/releases/absent/training-pack", headers=auth(client, "expert"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RELEASE_NOT_FOUND"
