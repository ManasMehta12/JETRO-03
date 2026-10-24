import json
import threading
import time
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


def test_openrouter_structured_extraction(setup_provider, tmp_path, monkeypatch):
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

    clients = []

    def chat_client():
        client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": "Bearer test-key"},
            transport=httpx.MockTransport(chat),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(provider, "_chat_client", chat_client)
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
    assert clients[0].is_closed


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


@pytest.mark.parametrize("delay", ["headers", "body"])
def test_chat_deadline_cancels_slow_response(setup_provider, tmp_path, delay, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps(
                {"choices": [{"message": {"content": '{"task_summary":"Test","steps":[]}'}}]}
            ).encode()
            try:
                if delay == "headers":
                    time.sleep(0.6)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if delay == "body":
                    for _ in range(30):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.02)
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    provider = setup_provider
    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps({"language": "en", "segments": []}))
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
        thread.start()
        provider._http.close()
        provider._http = httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", timeout=5, trust_env=False
        )
        provider._timeout = 0.15
        clients = []
        create_client = provider._chat_client

        def chat_client():
            client = create_client()
            clients.append(client)
            return client

        monkeypatch.setattr(provider, "_chat_client", chat_client)
        try:
            started = time.monotonic()
            with pytest.raises(ProviderError) as error:
                provider.extract_video(
                    ProviderFile(
                        name=transcript.name,
                        uri=transcript.name,
                        mime_type="application/json",
                        state="ACTIVE",
                    ),
                    TaskContext(task_id="task", title="Test", equipment="Bench", language="en"),
                    3000,
                    True,
                )
            assert time.monotonic() - started < 1
            assert error.value.code == "PROCESSING_TIMEOUT"
            assert error.value.retryable
            assert clients[0].is_closed
        finally:
            provider._http.close()
            server.shutdown()
            thread.join(timeout=1)
