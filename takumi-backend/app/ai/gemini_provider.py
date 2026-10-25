import re
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.base import ProviderError
from app.ai.prompts.video_extraction_v1 import PROMPT_VERSION, build_prompt
from app.ai.schemas import ProviderFile, TaskContext, VideoExtraction, VideoExtractionResult


def _retry_delay(details) -> float | None:
    if isinstance(details, dict):
        delay = details.get("retryDelay")
        if isinstance(delay, str) and re.fullmatch(r"\d+(?:\.\d+)?s", delay):
            return float(delay[:-1])
        for value in details.values():
            found = _retry_delay(value)
            if found is not None:
                return found
    elif isinstance(details, list):
        for value in details:
            found = _retry_delay(value)
            if found is not None:
                return found
    return None


def _normalize(
    exc: Exception,
    missing=("AI_FILE_EXPIRED", "AI provider file is unavailable.", True),
) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, errors.ClientError):
        if exc.code == 429:
            return ProviderError(
                "AI_PROVIDER_RATE_LIMITED",
                "AI provider rate limit reached.",
                True,
                _retry_delay(exc.details),
            )
        if exc.code in (401, 403):
            return ProviderError(
                "AI_PROVIDER_AUTH_FAILED", "AI provider authentication failed.", False
            )
        if exc.code == 404:
            return ProviderError(*missing)
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError("PROCESSING_TIMEOUT", "AI provider request timed out.", True)
    if isinstance(exc, (errors.ServerError, httpx.TransportError)):
        return ProviderError("AI_PROVIDER_UNAVAILABLE", "AI provider is unavailable.", True)
    return ProviderError("PROCESSING_FAILED", "AI provider request failed.", False)


def _provider_file(file: types.File) -> ProviderFile:
    return ProviderFile(
        name=file.name,
        uri=file.uri,
        mime_type=file.mime_type,
        state=getattr(file.state, "name", str(file.state)),
        expires_at=file.expiration_time,
    )


class GeminiAIProvider:
    def __init__(self, settings):
        self.provider = "gemini"
        self.model_id = settings.gemini_model
        self._poll_interval = settings.processing_poll_interval_seconds
        self._timeout = settings.processing_provider_timeout_seconds
        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=self._timeout * 1000),
        )

    def check_model(self) -> None:
        try:
            model = self._client.models.get(model=self.model_id)
            actions = getattr(model, "supported_actions", None)
            if actions and "generateContent" not in actions:
                raise ProviderError(
                    "AI_PROVIDER_UNAVAILABLE",
                    "Configured model does not support generateContent.",
                    False,
                )
        except Exception as exc:
            raise _normalize(
                exc,
                missing=("AI_PROVIDER_UNAVAILABLE", "Configured model was not found.", False),
            ) from None

    def upload_file(self, path: Path, mime_type: str, display_name: str) -> ProviderFile:
        try:
            return _provider_file(
                self._client.files.upload(
                    file=path,
                    config=types.UploadFileConfig(mime_type=mime_type, display_name=display_name),
                )
            )
        except Exception as exc:
            raise _normalize(exc) from None

    def wait_until_active(self, name: str, on_poll: Callable[[], None]) -> ProviderFile:
        started = time.monotonic()
        while True:
            if time.monotonic() - started >= self._timeout:
                raise ProviderError("PROCESSING_TIMEOUT", "AI file processing timed out.", True)
            on_poll()
            try:
                file = self._client.files.get(name=name)
                if file.state == types.FileState.ACTIVE:
                    return _provider_file(file)
                if file.state == types.FileState.FAILED:
                    raise ProviderError(
                        "AI_FILE_PROCESSING_FAILED",
                        "AI provider could not process the file.",
                        False,
                    )
            except Exception as exc:
                raise _normalize(exc) from None
            time.sleep(self._poll_interval)

    def extract_video(
        self, file: ProviderFile, task: TaskContext, duration_ms: int, has_audio: bool
    ) -> VideoExtraction:
        try:
            response = self._client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type),
                    build_prompt(task, duration_ms, has_audio),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VideoExtractionResult,
                    temperature=0,
                ),
            )
            try:
                result = VideoExtractionResult.model_validate_json(response.text or "")
            except (ValidationError, ValueError):
                raise ProviderError(
                    "AI_RESPONSE_INVALID", "Model output did not match the extraction schema.", True
                ) from None
            return VideoExtraction(
                result=result,
                usage=(
                    response.usage_metadata.model_dump(exclude_none=True, mode="json")
                    if response.usage_metadata
                    else None
                ),
                model_id=self.model_id,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:
            raise _normalize(exc) from None

    def delete_file(self, name: str) -> None:
        try:
            self._client.files.delete(name=name)
        except Exception as exc:
            raise _normalize(exc) from None
