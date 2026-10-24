from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core import security
from app.database import utcnow
from tests.conftest import auth


def test_defaults():
    settings = Settings(_env_file=None)
    assert settings.ai_provider == "fixture"
    for name in type(settings).model_fields:
        if name.startswith(("enable_live_", "enable_media_")):
            assert getattr(settings, name) is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ai_provider": "gemini"}, "reserved for Checkpoint 5"),
        ({"enable_live_qa": True}, "reserved for Checkpoint 6"),
        ({"app_env": "production"}, "must be false when APP_ENV=production"),
        ({"demo_mode": False}, "requires DEMO_MODE=true"),
    ],
)
def test_invalid_settings(overrides, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **overrides)


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "secret" not in response.text
    assert "gemini_api_key" not in response.text
    assert response.headers["X-Request-ID"]
    assert client.get("/openapi.json").status_code == 200


def test_disabled_login(make_client):
    with make_client(enable_demo_auth=False) as client:
        response = client.post("/api/v1/auth/demo-login", json={"demo_user": "expert"})
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "FEATURE_DISABLED"


def test_reserved_media_auth(client):
    response = client.post("/api/v1/tasks/task_001/media", headers=auth(client, "expert"))
    assert response.status_code == 501
    assert response.json()["error"]["details"]["flag"] == "ENABLE_MEDIA_UPLOAD"
    response = client.post("/api/v1/tasks/task_001/media")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_tampered_token(client):
    headers = auth(client, "expert")
    headers["Authorization"] += "x"
    response = client.post("/api/v1/tasks/task_001/media", headers=headers)
    assert response.status_code == 401


def test_expired_token(client, monkeypatch):
    past = utcnow() - timedelta(days=2)
    monkeypatch.setattr(security, "utcnow", lambda: past)
    token, _ = security.issue_token(
        "expert", client.app.state.settings, client.app.state.signing_key
    )
    monkeypatch.undo()
    response = client.post(
        "/api/v1/tasks/task_001/media", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_error_envelopes_and_body_limit(client):
    assert client.patch("/api/v1/health").json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    response = client.post("/api/v1/auth/demo-login", json={"demo_user": "invalid"})
    assert response.status_code == 422
    assert "input" not in response.json()["error"]["details"]["errors"][0]
    response = client.post(
        "/api/v1/auth/demo-login",
        content="x",
        headers={"Content-Length": str(1024 * 1024 + 1), "X-Request-ID": "test-id"},
    )
    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "test-id"
