import hashlib
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select

from app.core import security
from app.core.errors import AppError
from app.database import utcnow
from app.models.entities import Evidence, MediaAsset, Release
from app.services import evidence_service, media_service
from tests.conftest import auth


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


def upload(client, sample_videos, name="ok.mp4", role="expert", task_id="task_001"):
    with (sample_videos / name).open("rb") as source:
        return client.post(
            f"/api/v1/tasks/{task_id}/media",
            headers=auth(client, role),
            files={"file": (name, source, "video/mp4")},
        )


def assert_empty(client):
    with client.app.state.sessionmaker() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0
    root = client.app.state.settings.media_storage_dir / ".tmp"
    assert not root.exists() or not list(root.iterdir())


@pytest.mark.parametrize("name,has_audio", [("ok.mp4", True), ("silent.mp4", False)])
def test_valid_upload(make_client, sample_videos, name, has_audio):
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        response = upload(client, sample_videos, name)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["has_audio"] is has_audio
        assert 2900 <= body["duration_ms"] <= 3100
        assert body["video_codec"] == "h264"
        assert (body["width"], body["height"]) == (320, 240)
        source = (sample_videos / name).read_bytes()
        assert body["sha256"] == hashlib.sha256(source).hexdigest()
        assert body["size_bytes"] == len(source)
        root = client.app.state.settings.media_storage_dir
        with client.app.state.sessionmaker() as session:
            media = session.get(MediaAsset, body["media_id"])
            assert media.storage_key == f"task_001/{media.id}.mp4"
            assert (root / media.storage_key).read_bytes() == source
        assert not list((root / ".tmp").iterdir())


@pytest.mark.parametrize(
    "payload,code",
    [
        (b"fake", "INVALID_MEDIA"),
        (b"", "INVALID_MEDIA"),
        (b"x" * (1024 * 1024 + 1), "MEDIA_TOO_LARGE"),
    ],
)
def test_bad_uploads_clean_temporary_files(make_client, payload, code):
    with make_client(enable_media_upload=True, max_upload_mb=1) as client:
        response = client.post(
            "/api/v1/tasks/task_001/media",
            headers=auth(client, "expert"),
            files={"file": ("fake.mp4", payload, "video/mp4")},
        )
        assert response.status_code == (413 if code == "MEDIA_TOO_LARGE" else 422)
        assert response.json()["error"]["code"] == code
        if not payload:
            assert response.json()["error"]["details"]["reason"] == "empty_file"
        assert_empty(client)


def test_declared_upload_limit(make_client):
    with make_client(enable_media_upload=True, max_upload_mb=1) as client:
        response = client.post(
            "/api/v1/tasks/task_001/media",
            content=b"x",
            headers={**auth(client, "expert"), "Content-Length": str(2 * 1024 * 1024 + 1)},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "MEDIA_TOO_LARGE"
        assert_empty(client)


def test_video_duration_limit(make_client, sample_videos):
    with make_client(enable_media_upload=True, max_video_duration_seconds=1) as client:
        response = upload(client, sample_videos)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "MEDIA_TOO_LONG"
        assert_empty(client)


def test_upload_auth_and_flags(make_client, sample_videos):
    with make_client(enable_media_upload=True) as client:
        assert upload(client, sample_videos).status_code == 201
        assert upload(client, sample_videos, role="reviewer").status_code == 201
        assert upload(client, sample_videos, role="apprentice").status_code == 403
        assert client.post("/api/v1/tasks/task_001/media").status_code == 401
        response = upload(client, sample_videos, task_id="missing")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
    with make_client() as client:
        response = upload(client, sample_videos)
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "FEATURE_DISABLED"


def test_streaming_and_token_scope(make_client, sample_videos, monkeypatch):
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        media = upload(client, sample_videos).json()
        media_id = media["media_id"]
        path = f"/api/v1/media/{media_id}"
        headers = auth(client, "expert")
        assert client.get(path, headers=headers).status_code == 200
        response = client.get(path + "/stream", headers=headers)
        assert response.status_code == 200
        assert response.content == (sample_videos / "ok.mp4").read_bytes()
        assert int(response.headers["Content-Length"]) == media["size_bytes"]
        response = client.get(path + "/stream", headers={**headers, "Range": "bytes=0-1023"})
        assert response.status_code == 206
        assert response.content == (sample_videos / "ok.mp4").read_bytes()[:1024]
        assert response.headers["Content-Range"] == f"bytes 0-1023/{media['size_bytes']}"
        assert response.headers["Accept-Ranges"] == "bytes"
        response = client.get(path + "/stream", headers={**headers, "Range": "bytes=999999999-"})
        assert response.status_code == 416
        assert response.headers["Content-Range"] == f"bytes */{media['size_bytes']}"
        assert client.get(path + "/stream").status_code == 401
        assert client.get(path).status_code == 401
        response = client.get("/api/v1/media/missing/stream", headers=headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MEDIA_NOT_FOUND"
        assert client.get(media["playback_url"]).status_code == 200
        token = parse_qs(urlsplit(media["playback_url"]).query)["token"][0]
        assert client.get(f"/api/v1/media/other/stream?token={token}").status_code == 401
        assert (
            client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"}).status_code
            == 401
        )
        future = utcnow() + timedelta(minutes=11)
        monkeypatch.setattr(security, "utcnow", lambda: future)
        assert client.get(media["playback_url"]).status_code == 401


def test_apprentice_visibility_and_evidence(make_client, sample_videos):
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        media = upload(client, sample_videos).json()
        path = f"/api/v1/media/{media['media_id']}"
        headers = auth(client, "apprentice")
        assert client.get(path, headers=headers).status_code == 404
        assert client.get(path + "/stream", headers=headers).status_code == 404
        item = dict(
            id="ev_media",
            type="video_segment",
            media_id=media["media_id"],
            start_ms=500,
            end_ms=1500,
            source_label="real",
        )
        evidence_service.validate_evidence_items(
            [item], "task_001", media["duration_ms"], media["media_id"]
        )
        with pytest.raises(AppError, match="exceeds media duration"):
            evidence_service.validate_evidence_items(
                [{**item, "end_ms": media["duration_ms"] + 1}],
                "task_001",
                media["duration_ms"],
                media["media_id"],
            )
        with pytest.raises(AppError, match="Media references are not available in V1"):
            evidence_service.validate_evidence_items([item], "task_001")
        with client.app.state.sessionmaker() as session, session.begin():
            session.add(
                Evidence(
                    **item,
                    task_id="task_001",
                    author_id="expert_001",
                    author_label="Demo Expert",
                    content="Recording",
                )
            )
            session.add(
                Release(
                    id="release_media",
                    task_id="task_001",
                    version=1,
                    source_draft_revision=1,
                    content_hash="test",
                    approved_by="reviewer_001",
                    approval_note="Reviewed",
                    task_snapshot={},
                    knowledge_snapshot=[],
                    evidence_snapshot=[item],
                )
            )
        response = client.get("/api/v1/evidence/ev_media", headers=headers)
        assert response.status_code == 200
        assert response.json()["media_id"] == media["media_id"]
        assert response.json()["start_ms"] == 500
        assert response.json()["end_ms"] == 1500
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path + "/stream", headers=headers).status_code == 200


def test_persistence(make_client, sample_videos):
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        media = upload(client, sample_videos).json()
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        path = f"/api/v1/media/{media['media_id']}"
        headers = auth(client, "reviewer")
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path + "/stream", headers=headers).status_code == 200


def test_reset_removes_stored_media(make_client, sample_videos):
    with make_client(enable_media_upload=True, enable_media_streaming=True) as client:
        media = upload(client, sample_videos).json()
        root = client.app.state.settings.media_storage_dir
        stored = root / "task_001" / f"{media['media_id']}.mp4"
        assert stored.is_file()
        response = client.post(
            "/api/v1/demo/reset",
            headers=auth(client, "reviewer"),
            json={"scope": "full_demo", "confirm": "RESET_DEMO_DATA", "state": "fresh"},
        )
        assert response.status_code == 200
        assert not stored.exists()
        assert_empty(client)


@pytest.mark.parametrize(
    "metadata,reason",
    [
        ({"format": {"format_name": "matroska"}}, "unsupported_container"),
        (
            {"format": {"format_name": "mov,mp4", "tags": {"major_brand": "qt  "}}},
            "unsupported_container",
        ),
        ({"format": {"format_name": "mp4"}, "streams": []}, "no_video_stream"),
        (
            {
                "format": {"format_name": "mp4"},
                "streams": [{"codec_type": "video", "codec_name": "mpeg4"}],
            },
            "unsupported_codec",
        ),
        (
            {
                "format": {"format_name": "mp4"},
                "streams": [{"codec_type": "video", "codec_name": "h264"}],
            },
            "no_duration",
        ),
    ],
)
def test_probe_rejections(monkeypatch, metadata, reason):
    monkeypatch.setattr(
        media_service.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(metadata).encode(), stderr=b""
        ),
    )
    with pytest.raises(AppError) as exc:
        media_service.probe(Path("unused"))
    assert exc.value.code == "INVALID_MEDIA"
    assert exc.value.details["reason"] == reason


@pytest.mark.parametrize(
    "failure,code",
    [
        (FileNotFoundError(), "FFPROBE_UNAVAILABLE"),
        (subprocess.TimeoutExpired("ffprobe", 30), "INVALID_MEDIA"),
    ],
)
def test_probe_tool_failures(monkeypatch, failure, code):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(media_service.subprocess, "run", fail)
    with pytest.raises(AppError) as exc:
        media_service.probe(Path("unused"))
    assert exc.value.code == code
