import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import issue_playback_token
from app.database import new_id
from app.models.entities import MediaAsset, Release
from app.models.schemas import MediaOut

CHUNK = 1024 * 1024
FFPROBE_TIMEOUT = 30
ALLOWED_VIDEO_CODECS = {"h264", "av1"}


def _invalid(reason: str, **details) -> AppError:
    return AppError(
        "INVALID_MEDIA",
        "Uploaded file is not valid supported media.",
        422,
        {"reason": reason, **details},
    )


def probe(path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height",
                str(path),
            ],
            capture_output=True,
            timeout=FFPROBE_TIMEOUT,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(
            "FFPROBE_UNAVAILABLE", "Media inspection tool is not installed on the server.", 503
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise _invalid("inspection_failed") from exc
    if result.returncode or len(result.stdout) > 1_000_000:
        raise _invalid("inspection_failed")
    try:
        data = json.loads(result.stdout)
        metadata = data.get("format", {})
        if (
            "mp4" not in metadata.get("format_name", "").split(",")
            or metadata.get("tags", {}).get("major_brand", "").strip().lower() == "qt"
        ):
            raise _invalid("unsupported_container")
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video is None:
            raise _invalid("no_video_stream")
        codec = video.get("codec_name")
        if codec not in ALLOWED_VIDEO_CODECS:
            raise _invalid("unsupported_codec", codec=codec)
        try:
            duration = float(metadata.get("duration", 0))
        except (ValueError, TypeError):
            raise _invalid("no_duration") from None
        if not math.isfinite(duration) or duration <= 0:
            raise _invalid("no_duration")
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        return dict(
            container="mp4",
            duration_ms=max(1, round(duration * 1000)),
            video_codec=codec,
            audio_codec=audio.get("codec_name"),
            width=int(video["width"]),
            height=int(video["height"]),
        )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _invalid("inspection_failed") from exc


@dataclass
class ReceivedMedia:
    temp_path: Path
    original_filename: str
    size_bytes: int
    sha256: str
    container: str
    duration_ms: int
    video_codec: str
    audio_codec: str | None
    width: int
    height: int


def receive_upload(settings, upload: UploadFile) -> ReceivedMedia:
    temporary_dir = settings.media_storage_dir / ".tmp"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        digest = hashlib.sha256()
        size = 0
        with NamedTemporaryFile(dir=temporary_dir, delete=False, suffix=".upload") as target:
            temp_path = Path(target.name)
            while chunk := upload.file.read(CHUNK):
                size += len(chunk)
                if size > settings.max_upload_mb * CHUNK:
                    raise AppError(
                        "MEDIA_TOO_LARGE",
                        "Upload exceeds the configured limit.",
                        413,
                        {"max_upload_mb": settings.max_upload_mb},
                    )
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise _invalid("empty_file")
        metadata = probe(temp_path)
        if metadata["duration_ms"] > settings.max_video_duration_seconds * 1000:
            raise AppError(
                "MEDIA_TOO_LONG",
                "Media exceeds the configured duration limit.",
                422,
                {
                    "duration_ms": metadata["duration_ms"],
                    "max_seconds": settings.max_video_duration_seconds,
                },
            )
        return ReceivedMedia(
            temp_path=temp_path,
            original_filename=Path(upload.filename or "upload.mp4").name[:255],
            size_bytes=size,
            sha256=digest.hexdigest(),
            **metadata,
        )
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _stored_path(settings, storage_key: str) -> Path:
    root = settings.media_storage_dir.resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Media storage path escapes storage directory")
    return path


def save_media(session, settings, task_id, user, received) -> MediaAsset:
    media_id = new_id("media")
    storage_key = f"{task_id}/{media_id}.mp4"
    final = _stored_path(settings, storage_key)
    values = asdict(received)
    values.pop("temp_path")
    media = MediaAsset(
        id=media_id,
        task_id=task_id,
        owner_id=user.id,
        storage_key=storage_key,
        mime_type="video/mp4",
        status="uploaded",
        **values,
    )
    session.add(media)
    session.flush()
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(received.temp_path, final)
    return media


def discard(settings, received, storage_key: str | None):
    received.temp_path.unlink(missing_ok=True)
    if storage_key is not None:
        _stored_path(settings, storage_key).unlink(missing_ok=True)


def remove_stored_files(settings, storage_keys: list[str]) -> None:
    for key in storage_keys:
        try:
            _stored_path(settings, key).unlink(missing_ok=True)
        except OSError:
            pass


def get_visible_media(session, media_id, user) -> MediaAsset:
    media = session.get(MediaAsset, media_id)
    if media is not None and user.role == "apprentice":
        snapshots = session.scalars(
            select(Release.evidence_snapshot).where(Release.task_id == media.task_id)
        )
        if not any(item.get("media_id") == media.id for snapshot in snapshots for item in snapshot):
            media = None
    if media is None:
        raise AppError("MEDIA_NOT_FOUND", "Media not found.", 404)
    return media


def media_path(settings, media) -> Path:
    path = _stored_path(settings, media.storage_key)
    if not path.is_file():
        raise AppError("MEDIA_NOT_FOUND", "Media source file is unavailable.", 404)
    return path


def media_out(media, settings, key, user) -> MediaOut:
    token, expires = issue_playback_token(media.id, user, key)
    return MediaOut(
        media_id=media.id,
        task_id=media.task_id,
        filename=media.original_filename,
        status=media.status,
        duration_ms=media.duration_ms,
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        sha256=media.sha256,
        video_codec=media.video_codec,
        audio_codec=media.audio_codec,
        has_audio=media.audio_codec is not None,
        width=media.width,
        height=media.height,
        created_at=media.created_at,
        playback_url=f"/api/v1/media/{media.id}/stream?token={token}",
        playback_expires_at=expires,
    )
