from tests.conftest import auth


def test_create_get_list(client):
    headers = auth(client, "expert")
    payload = {"title": "New task", "equipment": "Bench", "description": "Inspection"}
    response = client.post("/api/v1/tasks", headers=headers, json=payload)
    assert response.status_code == 201
    task = response.json()
    assert task["status"] == "created"
    assert task["source_label"] == "real"
    assert task["active_release_id"] is None
    assert client.get(f"/api/v1/tasks/{task['id']}", headers=headers).json() == task
    assert task in client.get("/api/v1/tasks", headers=headers).json()["items"]
    response = client.get(f"/api/v1/tasks/{task['id']}/draft", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DRAFT_NOT_FOUND"


def test_visibility_and_auth(client):
    expert = auth(client, "expert")
    apprentice = auth(client, "apprentice")
    response = client.get("/api/v1/tasks/missing", headers=expert)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
    assert client.get("/api/v1/tasks/task_001", headers=apprentice).status_code == 404
    assert client.get("/api/v1/tasks", headers=apprentice).json() == {"items": []}
    assert (
        client.post(
            "/api/v1/tasks", headers=apprentice, json={"title": "x", "equipment": "y"}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/tasks").status_code == 401
