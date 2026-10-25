import shutil
import subprocess
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings_factory(tmp_path):
    def factory(**overrides):
        values = dict(
            database_url=f"sqlite:///{tmp_path}/test.db",
            media_storage_dir=tmp_path / "media",
            app_env="test",
            demo_signing_secret="test-secret",
            demo_seed_state="fresh",
        )
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return factory


@pytest.fixture
def make_client(settings_factory):
    @contextmanager
    def factory(**overrides):
        raise_server_exceptions = overrides.pop("raise_server_exceptions", True)
        with TestClient(
            create_app(settings_factory(**overrides)),
            raise_server_exceptions=raise_server_exceptions,
        ) as client:
            yield client

    return factory


@pytest.fixture
def client(make_client):
    with make_client() as client:
        yield client


def auth(client, role):
    response = client.post("/api/v1/auth/demo-login", json={"demo_user": role})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def sample_videos(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for media tests")
    root = tmp_path_factory.mktemp("videos")
    for name, audio in [("ok.mp4", True), ("silent.mp4", False)]:
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=320x240:rate=10",
        ]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=duration=3"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            command += ["-c:a", "aac", "-shortest"]
        command += [str(root / name)]
        subprocess.run(command, check=True, capture_output=True)
    (root / "fake.mp4").write_bytes(b"not a video")
    return root
