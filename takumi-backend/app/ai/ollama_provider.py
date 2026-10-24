import asyncio
import json
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.ai.base import ProviderError
from app.ai.prompts.transcript_extraction_v1 import PROMPT_VERSION, build_prompt
from app.ai.schemas import ProviderFile, TaskContext, VideoExtraction, VideoExtractionResult

# Ollama defaults to a small context; transcript + schema + output need ~4k tokens.
NUM_CTX = 8192


def _normalize(exc: Exception) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired, httpx.TimeoutException)):
        return ProviderError("PROCESSING_TIMEOUT", "AI provider request timed out.", True)
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 404:
            return ProviderError(
                "AI_PROVIDER_UNAVAILABLE", "AI model or service endpoint is not available.", False
            )
        if exc.response.status_code >= 500:
            return ProviderError("AI_PROVIDER_UNAVAILABLE", "AI provider is unavailable.", True)
    if isinstance(exc, httpx.TransportError):
        return ProviderError("AI_PROVIDER_UNAVAILABLE", "AI provider is unavailable.", True)
    return ProviderError("PROCESSING_FAILED", "AI provider request failed.", False)


def _is_marker(text: str) -> bool:
    # whisper.cpp emits non-speech markers like [BLANK_AUDIO] or (music); they are not narration.
    text = text.strip()
    return (text[:1], text[-1:]) in (("[", "]"), ("(", ")"))


def _transcript_file(name: str) -> ProviderFile:
    return ProviderFile(name=name, uri=name, mime_type="application/json", state="ACTIVE")


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Transcription deadline exceeded.")
    return remaining


class OllamaVideoExtractor:
    """Transcript-based extraction: ffmpeg here, whisper.cpp and Ollama on a LAN host."""

    def __init__(self, settings):
        self.provider = "ollama"
        self.model_id = settings.ollama_model
        self._dir = Path(settings.media_storage_dir)
        self._timeout = settings.processing_provider_timeout_seconds
        self._http = httpx.Client(base_url=settings.ollama_base_url, timeout=self._timeout)
        self._stt = httpx.Client(base_url=settings.whisper_base_url, timeout=self._timeout)

    def _stt_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._stt.base_url,
            headers=self._stt.headers,
            timeout=self._timeout,
        )

    def _request_transcription(self, audio: bytes, deadline: float) -> httpx.Response:
        async def request():
            # Both routes share the budget left after conversion. Per-chunk activity
            # must not extend it. Cancellation closes the client and local request.
            async with asyncio.timeout(_remaining(deadline)):
                async with self._stt_client() as client:
                    response = await client.post(
                        "/inference",
                        files={"file": ("audio.wav", audio, "audio/wav")},
                        data={"response_format": "verbose_json", "temperature": "0.0"},
                    )
                    # Only a missing route triggers WhisperServer.app fallback.
                    if response.status_code == 404:
                        response = await client.post(
                            "/v1/audio/transcriptions",
                            files={"file": ("audio.wav", audio, "audio/wav")},
                            data={
                                "response_format": "verbose_json",
                                "temperature": "0.0",
                                "timestamp_granularities[]": "segment",
                            },
                        )
                    return response

        return asyncio.run(request())

    def _transcribe(self, path: Path, deadline: float) -> tuple[str | None, list[dict]]:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "audio.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1"]
                    + ["-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                    check=True,
                    capture_output=True,
                    timeout=_remaining(deadline),
                )
            except TimeoutError:
                raise
            except (subprocess.CalledProcessError, OSError):
                raise ProviderError(
                    "PROCESSING_FAILED", "Could not extract audio from the recording.", False
                ) from None
            audio = wav.read_bytes()
            response = self._request_transcription(audio, deadline)
        response.raise_for_status()
        try:
            body = response.json()
            segments = [
                {
                    "start_ms": round(s["start"] * 1000),
                    "end_ms": round(s["end"] * 1000),
                    "text": s["text"].strip(),
                }
                for s in body.get("segments", [])
                if s["text"].strip() and not _is_marker(s["text"])
            ]
            return body.get("language"), segments
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ProviderError(
                "PROCESSING_FAILED",
                "Transcription service returned an unexpected response.",
                False,
            ) from None

    def check_model(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise ProviderError(
                "AI_PROVIDER_UNAVAILABLE", "ffmpeg is required to extract audio.", False
            )
        try:
            self._http.post("/api/show", json={"model": self.model_id}).raise_for_status()
            # Any HTTP response proves whisper-server is up; its "/" may 404 on some installs.
            self._stt.get("/")
        except Exception as exc:
            raise _normalize(exc) from None

    def upload_file(self, path: Path, mime_type: str, display_name: str) -> ProviderFile:
        deadline = time.monotonic() + self._timeout
        try:
            language, segments = self._transcribe(path, deadline)
            # Parsing and temporary-file cleanup also consume the stage's budget.
            _remaining(deadline)
        except Exception as exc:
            raise _normalize(exc) from None
        if not segments:
            raise ProviderError(
                "NO_SPEECH_DETECTED",
                "No speech was detected; transcript extraction needs narration.",
                False,
            )
        # Relative name: the job row must not store an absolute host path.
        name = f"transcripts/{display_name}.json"
        target = self._dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"language": language, "segments": segments}))
        return _transcript_file(name)

    def wait_until_active(self, name: str, on_poll: Callable[[], None]) -> ProviderFile:
        if (self._dir / name).exists():
            return _transcript_file(name)
        raise ProviderError("AI_FILE_EXPIRED", "Transcript is unavailable.", True)

    def extract_video(
        self, file: ProviderFile, task: TaskContext, duration_ms: int, has_audio: bool
    ) -> VideoExtraction:
        try:
            try:
                transcript = json.loads((self._dir / file.name).read_text())
            except FileNotFoundError:
                raise ProviderError("AI_FILE_EXPIRED", "Transcript is unavailable.", True) from None
            response = self._http.post(
                "/api/chat",
                json={
                    "model": self.model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": build_prompt(task, duration_ms, transcript["segments"]),
                        }
                    ],
                    "stream": False,
                    "format": VideoExtractionResult.model_json_schema(),
                    "options": {"temperature": 0, "num_ctx": NUM_CTX},
                },
            )
            response.raise_for_status()
            try:
                body = response.json()
                result = VideoExtractionResult.model_validate_json(body["message"]["content"])
            except (ValidationError, ValueError, KeyError, TypeError):
                raise ProviderError(
                    "AI_RESPONSE_INVALID", "Model output did not match the extraction schema.", True
                ) from None
            # The model only read a transcript; never let it claim visual evidence.
            for step in result.steps:
                step.source_modality = "spoken"
            result.detected_language = transcript["language"]
            keys = ("prompt_eval_count", "eval_count", "total_duration")
            usage = {k: body[k] for k in keys if k in body}
            return VideoExtraction(
                result=result,
                usage=usage or None,
                model_id=self.model_id,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:
            raise _normalize(exc) from None

    def delete_file(self, name: str) -> None:
        (self._dir / name).unlink(missing_ok=True)
