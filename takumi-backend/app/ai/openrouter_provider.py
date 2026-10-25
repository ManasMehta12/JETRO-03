import json
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.ai.base import ProviderError
from app.ai.ollama_provider import OllamaVideoExtractor, _normalize
from app.ai.prompts.transcript_extraction_v1 import PROMPT_VERSION, build_prompt
from app.ai.schemas import ProviderFile, TaskContext, VideoExtraction, VideoExtractionResult


def _openrouter_error(exc: Exception) -> ProviderError:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return ProviderError(
                "AI_PROVIDER_AUTH_FAILED", "AI provider authentication failed.", False
            )
        if status == 429:
            return ProviderError(
                "AI_PROVIDER_RATE_LIMITED", "AI provider rate limit reached.", True
            )
    return _normalize(exc)


class OpenRouterVideoExtractor(OllamaVideoExtractor):
    """Local whisper.cpp transcription followed by OpenRouter text extraction."""

    def __init__(self, settings):
        self.provider = "openrouter"
        # Comma-separated priority list; OpenRouter tries the next model when one errors.
        self._models = [m.strip() for m in settings.openrouter_model.split(",") if m.strip()]
        self.model_id = self._models[0]
        self._dir = Path(settings.media_storage_dir)
        self._timeout = settings.processing_provider_timeout_seconds
        self._http = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"},
            timeout=self._timeout,
        )
        self._stt = httpx.Client(base_url=settings.whisper_base_url, timeout=self._timeout)

    def check_model(self) -> None:
        try:
            # One reachable model is enough; OpenRouter skips the unavailable ones.
            for model in self._models:
                try:
                    self._http.get(f"/models/{model}/endpoints").raise_for_status()
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (401, 403):
                        raise
                    last_error = exc
            else:
                raise last_error
            self._stt.get("/")
        except Exception as exc:
            raise _openrouter_error(exc) from None

    def extract_video(
        self, file: ProviderFile, task: TaskContext, duration_ms: int, has_audio: bool
    ) -> VideoExtraction:
        try:
            try:
                transcript = json.loads((self._dir / file.name).read_text())
            except FileNotFoundError:
                raise ProviderError("AI_FILE_EXPIRED", "Transcript is unavailable.", True) from None
            response = self._http.post(
                "/chat/completions",
                json={
                    "models": self._models,
                    # Route only to providers that honor the strict JSON schema.
                    "provider": {"require_parameters": True},
                    "messages": [
                        {
                            "role": "user",
                            "content": build_prompt(task, duration_ms, transcript["segments"]),
                        }
                    ],
                    "stream": False,
                    "temperature": 0,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "video_extraction",
                            "strict": True,
                            "schema": VideoExtractionResult.model_json_schema(),
                        },
                    },
                },
            )
            response.raise_for_status()
            try:
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                result = VideoExtractionResult.model_validate_json(content)
            except (ValidationError, ValueError, KeyError, TypeError, IndexError):
                raise ProviderError(
                    "AI_RESPONSE_INVALID", "Model output did not match the extraction schema.", True
                ) from None
            for step in result.steps:
                step.source_modality = "spoken"
            result.detected_language = transcript["language"]
            usage_body = body.get("usage") or {}
            usage = {
                key: usage_body[key]
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if key in usage_body
            }
            return VideoExtraction(
                result=result,
                usage=usage or None,
                model_id=body.get("model") or self.model_id,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:
            raise _openrouter_error(exc) from None
