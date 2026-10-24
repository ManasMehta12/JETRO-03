import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from app.ai.base import ProviderError
from app.ai.ollama_provider import OllamaVideoExtractor
from app.ai.openrouter_provider import OpenRouterVideoExtractor


@pytest.fixture(params=[OllamaVideoExtractor, OpenRouterVideoExtractor])
def provider(request, settings_factory):
    extractor = request.param(
        settings_factory(
            ai_provider="openrouter" if request.param is OpenRouterVideoExtractor else "ollama",
            ollama_base_url="http://ollama.test",
            ollama_model="test-model",
            openrouter_api_key="test-key",
            openrouter_model="test/model",
            whisper_base_url="http://127.0.0.1",
        )
    )
    try:
        yield extractor
    finally:
        extractor._http.close()
        extractor._stt.close()


@pytest.mark.parametrize("delay", ["headers", "body", "fallback", "conversion"])
def test_transcription_has_one_deadline(provider, delay, monkeypatch):
    paths, wavs, clients = [], [], []
    provider._timeout = 0.4

    def convert(command, **kwargs):
        assert 0 < kwargs["timeout"] <= provider._timeout
        wav = Path(command[-1])
        wavs.append(wav)
        if delay == "conversion":
            time.sleep(0.25)
        wav.write_bytes(b"test audio")

    monkeypatch.setattr("app.ai.ollama_provider.subprocess.run", convert)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            paths.append(self.path)
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps(
                {"segments": [{"start": 0, "end": 1, "text": "Inspect housing"}]}
            ).encode()
            try:
                if delay in ("conversion", "fallback"):
                    time.sleep(0.25)
                elif delay == "headers":
                    time.sleep(0.8)
                if delay == "fallback" and self.path == "/inference":
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if delay == "body":
                    for _ in range(40):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.02)
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
        thread.start()
        provider._stt.close()
        provider._stt = httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", timeout=5, trust_env=False
        )

        def stt_client():
            client = httpx.AsyncClient(base_url=provider._stt.base_url, timeout=5, trust_env=False)
            clients.append(client)
            return client

        monkeypatch.setattr(provider, "_stt_client", stt_client, raising=False)
        try:
            started = time.monotonic()
            with pytest.raises(ProviderError) as error:
                provider.upload_file(Path("test.mp4"), "video/mp4", "deadline_test")
            assert time.monotonic() - started < 1.2
            assert (error.value.code, error.value.retryable) == ("PROCESSING_TIMEOUT", True)
            assert clients and all(client.is_closed for client in clients)
            assert paths == (
                ["/inference", "/v1/audio/transcriptions"]
                if delay == "fallback"
                else ["/inference"]
            )
            assert wavs and all(not wav.parent.exists() for wav in wavs)
            assert not (provider._dir / "transcripts/deadline_test.json").exists()
        finally:
            server.shutdown()
            thread.join(timeout=1)


@pytest.mark.parametrize("failure", ["timeout", "exhausted", "conversion_error"])
def test_conversion_failure_never_contacts_whisper(provider, failure, monkeypatch):
    wavs, paths = [], []
    provider._timeout = 0.01

    def convert(command, **kwargs):
        wavs.append(Path(command[-1]))
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "conversion_error":
            raise subprocess.CalledProcessError(1, command)
        time.sleep(0.02)
        wavs[-1].write_bytes(b"test audio")

    def whisper(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"segments": []})

    monkeypatch.setattr("app.ai.ollama_provider.subprocess.run", convert)
    provider._stt.close()
    provider._stt = httpx.Client(
        base_url="http://whisper.test", transport=httpx.MockTransport(whisper)
    )
    monkeypatch.setattr(
        provider,
        "_stt_client",
        lambda: httpx.AsyncClient(
            base_url="http://whisper.test", transport=httpx.MockTransport(whisper)
        ),
        raising=False,
    )
    with pytest.raises(ProviderError) as error:
        provider.upload_file(Path("test.mp4"), "video/mp4", "conversion_test")
    expected = (
        ("PROCESSING_FAILED", False)
        if failure == "conversion_error"
        else ("PROCESSING_TIMEOUT", True)
    )
    assert (error.value.code, error.value.retryable) == expected
    assert not paths
    assert wavs and all(not wav.parent.exists() for wav in wavs)
    assert not (provider._dir / "transcripts/conversion_test.json").exists()
