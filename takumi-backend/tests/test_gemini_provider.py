import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from google.genai import errors, types

from app.ai.base import ProviderError
from app.ai.gemini_provider import GeminiAIProvider
from app.ai.prompts.video_extraction_v1 import INSTRUCTIONS, PROMPT_VERSION, build_prompt
from app.ai.schemas import ProviderFile, TaskContext, VideoExtractionResult


@pytest.fixture
def task():
    return TaskContext(
        task_id="task_test", title="Bearing inspection", equipment="Bench", language="en"
    )


@pytest.fixture
def active_file():
    return ProviderFile(
        name="files/test", uri="https://example.invalid/test", mime_type="video/mp4", state="ACTIVE"
    )


def sdk_file(state="ACTIVE"):
    return types.File(
        name="files/test",
        uri="https://example.invalid/test",
        mime_type="video/mp4",
        state=state,
        expiration_time=datetime(2030, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def provider(settings_factory, monkeypatch):
    fake = SimpleNamespace(files=Mock(), models=Mock())
    constructor = Mock(return_value=fake)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", constructor)
    settings = settings_factory(
        ai_provider="gemini", gemini_api_key="secret-test-key", gemini_model="fake-model"
    )
    result = GeminiAIProvider(settings)
    assert constructor.call_args.kwargs["api_key"] == "secret-test-key"
    assert constructor.call_args.kwargs["http_options"].timeout == 120_000
    return result


def valid_output():
    return {
        "task_summary": "Inspect bearing",
        "detected_language": "en",
        "steps": [
            {
                "start_ms": 0,
                "end_ms": 1000,
                "action": "Inspect bearing",
                "source_modality": "visual",
            }
        ],
    }


def test_upload_and_delete(provider):
    provider._client.files.upload.return_value = sdk_file("PROCESSING")
    uploaded = provider.upload_file(Path("source.mp4"), "video/mp4", "media_test")
    assert uploaded.state == "PROCESSING"
    assert uploaded.expires_at == datetime(2030, 1, 1, tzinfo=UTC)
    call = provider._client.files.upload.call_args.kwargs
    assert call["file"] == Path("source.mp4")
    assert isinstance(call["config"], types.UploadFileConfig)
    assert call["config"].mime_type == "video/mp4"
    assert call["config"].display_name == "media_test"
    provider.delete_file(uploaded.name)
    provider._client.files.delete.assert_called_once_with(name="files/test")


def test_poll_processing_to_active(provider, monkeypatch):
    provider._client.files.get.side_effect = [sdk_file("PROCESSING"), sdk_file()]
    sleep = Mock()
    monkeypatch.setattr("app.ai.gemini_provider.time.sleep", sleep)
    heartbeat = Mock()
    assert provider.wait_until_active("files/test", heartbeat).state == "ACTIVE"
    assert heartbeat.call_count == 2
    sleep.assert_called_once_with(2.0)
    assert provider._client.files.get.call_args.kwargs == {"name": "files/test"}


def test_failed_file(provider):
    provider._client.files.get.return_value = sdk_file("FAILED")
    with pytest.raises(ProviderError) as error:
        provider.wait_until_active("files/test", Mock())
    assert error.value.code == "AI_FILE_PROCESSING_FAILED"
    assert not error.value.retryable


def test_poll_timeout(provider, monkeypatch):
    provider._timeout = 0.001
    provider._client.files.get.return_value = sdk_file("PROCESSING")
    monkeypatch.setattr("app.ai.gemini_provider.time.monotonic", Mock(side_effect=[0, 0, 0.002]))
    monkeypatch.setattr("app.ai.gemini_provider.time.sleep", Mock())
    with pytest.raises(ProviderError) as error:
        provider.wait_until_active("files/test", Mock())
    assert error.value.code == "PROCESSING_TIMEOUT"
    assert error.value.retryable


def test_heartbeat_exception_is_not_normalized(provider):
    # Lease loss belongs to the worker, not the provider error mapper.
    heartbeat = Mock(side_effect=RuntimeError("lease lost"))
    with pytest.raises(RuntimeError, match="lease lost"):
        provider.wait_until_active("files/test", heartbeat)
    provider._client.files.get.assert_not_called()


@pytest.mark.parametrize("actions", [None, [], ["generateContent"]])
def test_check_model(provider, actions):
    provider._client.models.get.return_value = types.Model(supported_actions=actions)
    provider.check_model()
    provider._client.models.get.assert_called_once_with(model="fake-model")


def test_check_model_without_supported_actions(provider):
    provider._client.models.get.return_value = SimpleNamespace()
    provider.check_model()


def test_unsupported_model(provider):
    provider._client.models.get.return_value = types.Model(supported_actions=["embedContent"])
    with pytest.raises(ProviderError) as error:
        provider.check_model()
    assert error.value.code == "AI_PROVIDER_UNAVAILABLE"
    assert not error.value.retryable


def test_valid_extraction_and_sdk_schema_validation(provider, task, active_file):
    def generate_content(**kwargs):
        # Real installed SDK validation runs before the fake receives this config.
        config = types.GenerateContentConfig.model_validate(kwargs["config"])
        assert config.response_schema is VideoExtractionResult
        assert config.response_mime_type == "application/json"
        assert config.temperature == 0
        assert kwargs["model"] == "fake-model"
        part, prompt = kwargs["contents"]
        assert isinstance(part, types.Part)
        assert part.file_data.file_uri == active_file.uri
        assert part.file_data.mime_type == "video/mp4"
        assert "3000 ms" in prompt
        return SimpleNamespace(
            text=json.dumps(valid_output()),
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=12),
        )

    provider._client.models.generate_content.side_effect = generate_content
    extracted = provider.extract_video(active_file, task, 3000, True)
    assert extracted.result.steps[0].action == "Inspect bearing"
    assert extracted.usage == {"prompt_token_count": 12}
    assert extracted.model_id == "fake-model"
    assert extracted.prompt_version == PROMPT_VERSION


@pytest.mark.parametrize(
    "text",
    [
        "not JSON",
        "",
        None,
        "[]",
        json.dumps(
            {
                "task_summary": "x",
                "steps": [{"start_ms": 0, "end_ms": 1, "source_modality": "visual"}],
            }
        ),
    ],
)
def test_invalid_extraction(provider, task, active_file, text):
    provider._client.models.generate_content.return_value = SimpleNamespace(
        text=text, usage_metadata=None
    )
    with pytest.raises(ProviderError) as error:
        provider.extract_video(active_file, task, 3000, True)
    assert error.value.code == "AI_RESPONSE_INVALID"
    assert error.value.retryable


@pytest.mark.parametrize(
    "exception,code,retryable",
    [
        (
            errors.ClientError(404, {"error": {"message": "secret-test-key"}}),
            "AI_FILE_EXPIRED",
            True,
        ),
        (errors.ClientError(401, {}), "AI_PROVIDER_AUTH_FAILED", False),
        (errors.ClientError(403, {}), "AI_PROVIDER_AUTH_FAILED", False),
        (errors.ClientError(400, {}), "PROCESSING_FAILED", False),
        (errors.ServerError(503, {}), "AI_PROVIDER_UNAVAILABLE", True),
        (httpx.ReadTimeout("secret-test-key"), "PROCESSING_TIMEOUT", True),
        (httpx.ConnectError("secret-test-key"), "AI_PROVIDER_UNAVAILABLE", True),
        (RuntimeError("secret-test-key"), "PROCESSING_FAILED", False),
    ],
)
@pytest.mark.parametrize(
    "method", ["check_model", "upload_file", "wait_until_active", "extract_video", "delete_file"]
)
def test_normalized_errors(provider, task, active_file, exception, code, retryable, method):
    methods = {
        "check_model": (provider._client.models.get, []),
        "upload_file": (
            provider._client.files.upload,
            [Path("private.mp4"), "video/mp4", "media_test"],
        ),
        "wait_until_active": (provider._client.files.get, ["files/test", Mock()]),
        "extract_video": (
            provider._client.models.generate_content,
            [active_file, task, 3000, True],
        ),
        "delete_file": (provider._client.files.delete, ["files/test"]),
    }
    fake_method, args = methods[method]
    fake_method.side_effect = exception
    with pytest.raises(ProviderError) as error:
        getattr(provider, method)(*args)
    assert (error.value.code, error.value.retryable) == (code, retryable)
    assert "secret-test-key" not in str(error.value)
    assert "private.mp4" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("delay,expected", [("30s", 30), ("0.5s", 0.5), ("invalid", None)])
def test_rate_limit_retry_delay(provider, delay, expected):
    provider._client.models.get.side_effect = errors.ClientError(
        429, {"error": {"details": [{"@type": "google.rpc.RetryInfo", "retryDelay": delay}]}}
    )
    with pytest.raises(ProviderError) as error:
        provider.check_model()
    assert error.value.code == "AI_PROVIDER_RATE_LIMITED"
    assert error.value.retryable
    assert error.value.retry_after_seconds == expected


def test_prompt(task):
    prompt = build_prompt(task, 4321, False)
    assert INSTRUCTIONS in prompt
    assert "The recording lasts 4321 ms" in prompt
    assert "0 <= start_ms < end_ms <= 4321" in prompt
    assert (
        "This recording has no audio track. Do not report spoken content; "
        'use source_modality "visual".' in prompt
    )
    assert '"task_title": "Bearing inspection"' in prompt
    assert '"equipment": "Bench"' in prompt
    assert '"expected_language": "en"' in prompt
    assert "never invent steps to reach a count" in prompt
    assert "no audio track" not in build_prompt(task, 4321, True)
