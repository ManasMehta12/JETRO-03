import json
from contextlib import ExitStack

import httpx
import pytest

from app.ai.base import ProviderError
from app.ai.ollama_provider import OllamaVideoExtractor
from app.ai.schemas import TaskContext, VideoExtractionResult


def whisper_handler(request):
    assert request.method == "POST"
    assert request.url.path == "/inference"
    body = request.read()
    assert b'name="file"' in body
    assert b"audio/wav" in body
    assert b"verbose_json" in body
    return httpx.Response(
        200,
        json={
            "language": "english",
            "segments": [
                {"text": " Check the bearing housing", "start": 0.0, "end": 1.5},
                {"text": " [BLANK_AUDIO]", "start": 1.5, "end": 3.0},
            ],
        },
    )


def ollama_handler(request):
    assert request.method == "POST"
    assert request.url.path == "/api/chat"
    body = json.loads(request.content)
    assert body["format"] == VideoExtractionResult.model_json_schema()
    assert body["options"] == {"temperature": 0, "num_ctx": 8192}
    assert body["stream"] is False
    assert body["model"] == "qwen2.5:7b"
    assert "[0-1500] Check the bearing housing" in body["messages"][0]["content"]
    return httpx.Response(
        200,
        json={
            "message": {
                "content": json.dumps(
                    {
                        "task_summary": "Inspect bearing",
                        "detected_language": "en",
                        "steps": [
                            {
                                "start_ms": 0,
                                "end_ms": 1500,
                                "action": "Check the bearing housing",
                                "source_modality": "visual",
                            }
                        ],
                    }
                )
            },
            "eval_count": 42,
            "prompt_eval_count": 300,
        },
    )


@pytest.fixture
def provider_factory(settings_factory):
    with ExitStack() as clients:

        def factory(ollama=ollama_handler, whisper=whisper_handler):
            provider = OllamaVideoExtractor(
                settings_factory(
                    ai_provider="ollama",
                    ollama_base_url="http://ollama.test",
                    ollama_model="qwen2.5:7b",
                    whisper_base_url="http://whisper.test",
                )
            )
            provider._http.close()
            provider._stt.close()
            provider._http = clients.enter_context(
                httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(ollama))
            )
            provider._stt = clients.enter_context(
                httpx.Client(base_url="http://whisper.test", transport=httpx.MockTransport(whisper))
            )
            return provider

        yield factory


@pytest.fixture
def task():
    return TaskContext(
        task_id="task_test", title="Bearing inspection", equipment="Bench", language="en"
    )


def test_transcription_caches_filtered_segments(provider_factory, sample_videos, tmp_path):
    provider = provider_factory()
    uploaded = provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "media_test")
    assert uploaded.name == "transcripts/media_test.json"
    transcript = json.loads((tmp_path / "media" / uploaded.name).read_text())
    assert transcript == {
        "language": "english",
        "segments": [{"start_ms": 0, "end_ms": 1500, "text": "Check the bearing housing"}],
    }


def test_transcription_supports_whisperserver_app(provider_factory, sample_videos, tmp_path):
    paths = []

    def whisper(request):
        paths.append(request.url.path)
        assert request.method == "POST"
        if request.url.path == "/inference":
            return httpx.Response(404)
        assert request.url.path == "/v1/audio/transcriptions"
        assert b'name="file"' in request.content
        assert b'name="timestamp_granularities[]"' in request.content
        assert b"verbose_json" in request.content
        return httpx.Response(
            200,
            json={"segments": [{"start": 0.01, "end": 1.51, "text": " Inspect housing "}]},
        )

    provider = provider_factory(whisper=whisper)
    uploaded = provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "app_test")
    assert paths == ["/inference", "/v1/audio/transcriptions"]
    assert json.loads((tmp_path / "media" / uploaded.name).read_text()) == {
        "language": None,
        "segments": [{"start_ms": 10, "end_ms": 1510, "text": "Inspect housing"}],
    }


def test_transcription_does_not_fallback_on_server_error(provider_factory, sample_videos):
    paths = []

    def whisper(request):
        paths.append(request.url.path)
        return httpx.Response(503)

    provider = provider_factory(whisper=whisper)
    with pytest.raises(ProviderError) as error:
        provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "failed_test")
    assert paths == ["/inference"]
    assert error.value.code == "AI_PROVIDER_UNAVAILABLE"
    assert error.value.retryable


def test_upload_extract_delete_round_trip(provider_factory, sample_videos, task):
    provider = provider_factory()
    uploaded = provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "media_test")
    active = provider.wait_until_active(uploaded.name, lambda: None)
    extracted = provider.extract_video(active, task, 3000, True)
    assert extracted.result.steps[0].source_modality == "spoken"
    assert extracted.result.detected_language == "english"
    assert extracted.usage == {"eval_count": 42, "prompt_eval_count": 300}
    assert extracted.prompt_version == "transcript_extraction_v1"
    assert extracted.model_id == "qwen2.5:7b"
    provider.delete_file(active.name)
    with pytest.raises(ProviderError) as error:
        provider.wait_until_active(active.name, lambda: None)
    assert error.value.code == "AI_FILE_EXPIRED"
    assert error.value.retryable


def test_non_speech_markers_are_rejected(provider_factory, sample_videos):
    def markers(request):
        return httpx.Response(
            200,
            json={
                "segments": [
                    {"text": " [BLANK_AUDIO]", "start": 0, "end": 1.5},
                    {"text": "(music)", "start": 1.5, "end": 3},
                ]
            },
        )

    provider = provider_factory(whisper=markers)
    with pytest.raises(ProviderError) as error:
        provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "media_test")
    assert error.value.code == "NO_SPEECH_DETECTED"
    assert not error.value.retryable


def test_invalid_model_json_is_retryable(provider_factory, sample_videos, task):
    provider = provider_factory(
        ollama=lambda request: httpx.Response(200, json={"message": {"content": "not json"}})
    )
    uploaded = provider.upload_file(sample_videos / "ok.mp4", "video/mp4", "media_test")
    with pytest.raises(ProviderError) as error:
        provider.extract_video(uploaded, task, 3000, True)
    assert error.value.code == "AI_RESPONSE_INVALID"
    assert error.value.retryable


@pytest.mark.parametrize(
    "failure,code,retryable",
    [
        (404, "AI_PROVIDER_UNAVAILABLE", False),
        (500, "AI_PROVIDER_UNAVAILABLE", True),
        (httpx.ConnectError("x"), "AI_PROVIDER_UNAVAILABLE", True),
        (httpx.ReadTimeout("x"), "PROCESSING_TIMEOUT", True),
    ],
)
def test_normalized_errors(provider_factory, monkeypatch, failure, code, retryable):
    def fail(request):
        if isinstance(failure, Exception):
            raise failure
        return httpx.Response(failure)

    monkeypatch.setattr("app.ai.ollama_provider.shutil.which", lambda name: "/usr/bin/ffmpeg")
    provider = provider_factory(ollama=fail)
    with pytest.raises(ProviderError) as error:
        provider.check_model()
    assert (error.value.code, error.value.retryable) == (code, retryable)


def test_check_model_accepts_whisper_root_404(provider_factory, monkeypatch):
    def show(request):
        assert request.method == "POST"
        assert request.url.path == "/api/show"
        assert json.loads(request.content) == {"model": "qwen2.5:7b"}
        return httpx.Response(200)

    def root(request):
        assert request.method == "GET"
        assert request.url.path == "/"
        return httpx.Response(404)

    monkeypatch.setattr("app.ai.ollama_provider.shutil.which", lambda name: "/usr/bin/ffmpeg")
    provider_factory(ollama=show, whisper=root).check_model()
