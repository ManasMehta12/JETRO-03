import json
from contextlib import ExitStack

import httpx
import pytest

from app.ai.base import ProviderError
from app.ai.openrouter_provider import OpenRouterVideoExtractor
from app.ai.prompts.transcript_extraction_v1 import PROMPT_VERSION
from app.ai.schemas import ProviderFile, TaskContext, VideoExtractionResult


@pytest.fixture
def setup_provider(settings_factory, tmp_path):
    with ExitStack() as clients:
        settings = settings_factory(
            ai_provider="openrouter",
            openrouter_api_key="test-key",
            openrouter_model="provider/model, backup/model:free",
            whisper_base_url="http://whisper.test",
            media_storage_dir=tmp_path,
        )
        provider = OpenRouterVideoExtractor(settings)
        provider._http.close()
        provider._stt.close()
        provider._http = clients.enter_context(
            httpx.Client(
                base_url="https://openrouter.ai/api/v1",
                headers={"Authorization": "Bearer test-key"},
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={"id": "model", "data": {"id": "provider/model"}},
                    )
                ),
            )
        )
        provider._stt = clients.enter_context(
            httpx.Client(
                base_url="http://whisper.test",
                transport=httpx.MockTransport(lambda request: httpx.Response(404)),
            )
        )
        yield provider


def test_openrouter_structured_extraction(setup_provider, tmp_path):
    provider = setup_provider
    transcript_name = "transcripts/media_test.json"
    transcript_path = tmp_path / transcript_name
    transcript_path.parent.mkdir()
    transcript_path.write_text(
        json.dumps(
            {
                "language": "english",
                "segments": [{"start_ms": 0, "end_ms": 1500, "text": "Inspect the housing"}],
            }
        )
    )

    def chat(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/api/v1/chat/completions"
        body = json.loads(request.content)
        assert body["models"] == ["provider/model", "backup/model:free"]
        assert body["provider"] == {"require_parameters": True}
        assert body["temperature"] == 0
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"] == (
            VideoExtractionResult.model_json_schema()
        )
        return httpx.Response(
            200,
            json={
                "model": "backup/model:free",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "task_summary": "Inspect bearing",
                                    "detected_language": "en",
                                    "steps": [
                                        {
                                            "start_ms": 0,
                                            "end_ms": 1500,
                                            "action": "Inspect the housing",
                                            "source_modality": "visual",
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
            },
        )

    provider._http.close()
    provider._http = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(chat),
    )
    extracted = provider.extract_video(
        ProviderFile(
            name=transcript_name,
            uri=transcript_name,
            mime_type="application/json",
            state="ACTIVE",
        ),
        TaskContext(task_id="task", title="Bearing inspection", equipment="Bench", language="en"),
        3000,
        True,
    )
    assert extracted.result.steps[0].source_modality == "spoken"
    assert extracted.result.detected_language == "english"
    assert extracted.usage == {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}
    assert extracted.model_id == "backup/model:free"
    assert extracted.prompt_version == PROMPT_VERSION


def test_openrouter_auth_error_is_not_retried(setup_provider):
    setup_provider._http.close()
    setup_provider._http = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(lambda request: httpx.Response(401)),
    )
    with pytest.raises(ProviderError) as error:
        setup_provider.check_model()
    assert error.value.code == "AI_PROVIDER_AUTH_FAILED"
    assert not error.value.retryable


def test_openrouter_preflight_skips_unavailable_primary(setup_provider):
    def endpoints(request):
        return httpx.Response(404 if "provider/model" in request.url.path else 200, json={})

    setup_provider._http.close()
    setup_provider._http = httpx.Client(
        base_url="https://openrouter.ai/api/v1", transport=httpx.MockTransport(endpoints)
    )
    setup_provider.check_model()

    setup_provider._http.close()
    setup_provider._http = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
    )
    with pytest.raises(ProviderError) as error:
        setup_provider.check_model()
    assert error.value.code == "AI_PROVIDER_UNAVAILABLE"
