# Takumi Knowledge Engine

## Setup
From `takumi-backend/`, Python 3.11+ and uv:
```sh
uv sync
```

## Configuration
```sh
cp .env.example .env
```
Keep `.env` private. Defaults need no API key. Set `DEMO_SIGNING_SECRET` for tokens that survive restarts; empty generates a process-local key. Production requires all demo switches false and a future production identity integration.

## Start
```sh
uv run uvicorn app.main:app --reload --port 8000 --no-access-log
```

## Database
Startup creates SQLite tables, upgrades schema v1/v2 additively to v3 and installs the immutable-release UPDATE trigger. A new database automatically seeds `approved_baseline`, with `release_001` active. Existing `task_001` is never overwritten. Unsupported schema versions fail startup; back up before changing the database. Services flush; routers, lifespan, scripts and worker own transactions.

## Demo
```sh
uv run python scripts/seed_demo.py --state approved_baseline
uv run python scripts/demo_flow.py --base-url http://localhost:8000
```
The flow requires a running server (see Start). It logs 16 successful steps, resets only `task_001`, submits an expert answer, publishes and proves the answer is cited. All mechanical example content is illustrative, not a validated procedure.

## Reset
```sh
uv run python scripts/reset_demo.py --state fresh --yes
```
This replaces only fixture task `task_001` and its related records; user-created tasks survive. It refuses production/non-demo deployments. API reset requires reviewer auth and `confirm: "RESET_DEMO_DATA"`. Choose `fresh` before a live expert demonstration; choose `approved_baseline` for an immediately usable apprentice pack. Attempts belong to the scenario engine and cannot be reset here.

## API
Interactive docs: `/docs`. Generated schema: `contracts/openapi.json`. Teammate guide: [INTEGRATION_HANDOFF.md](docs/INTEGRATION_HANDOFF.md). Regenerate checked-in examples and schemas:
```sh
uv run python scripts/export_contracts.py
```
The canonical source is `../markdowns/hackathon/openapi/API.doc.md`, not the conflicting generated specs there.

## Tests
```sh
uv run pytest tests/test_demo.py tests/test_integration.py
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
Tests isolate databases. The integration test runs the full flow twice.

## Media (C4)
Install `ffprobe` on PATH (`ffmpeg` is also needed for generated-video tests). Set `ENABLE_MEDIA_UPLOAD=true` and `ENABLE_MEDIA_STREAMING=true`.
Experts/reviewers upload multipart field `file` to `POST /api/v1/tasks/{task_id}/media`.
Only MP4 containers with h264/av1 video are accepted; defaults limit uploads to 100 MiB and 240 seconds.
Files stay under `MEDIA_STORAGE_DIR=./data/media`, not a public static directory.
`GET /api/v1/media/{media_id}` returns metadata and a reusable 10-minute signed playback URL.
Streaming supports byte ranges. Apprentices see media only when a release snapshot cites it.
Run the server with `--no-access-log`: default access logs would record playback URL tokens.

## Live extraction (C5)
Set these values in the private `.env` used by both server and worker:
```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=<video-capable-model-available-to-your-key>
ENABLE_MEDIA_UPLOAD=true
ENABLE_MEDIA_STREAMING=true
ENABLE_MEDIA_PROCESSING=true
ENABLE_LIVE_EXTRACTION=true
ENABLE_PROCESSING_WORKER=true
```
No model is selected by default. Model availability and successful live extraction remain unverified.
Start server and worker in separate terminals from `takumi-backend/`, sharing `DATABASE_URL`, `MEDIA_STORAGE_DIR` and configuration:
```sh
uv run uvicorn app.main:app --port 8000 --no-access-log
uv run python scripts/run_worker.py
uv run python scripts/video_flow.py --video demo.mp4
```
The script creates a new task, uploads, checks a range, submits a job, polls and prints extracted units with evidence intervals.
`POST /process` returns 202 immediately; the worker builds an unreviewed draft, never a release.
Continue through the existing clarify → publish → training-pack → ask flow.
Existing drafts reject new processing with 409 `DRAFT_ALREADY_EXISTS`; use a new task.
`--mode demo` cannot analyze uploads and returns 422 `FIXTURE_NOT_AVAILABLE`; use `scripts/demo_flow.py` for the seeded fixture.
Without live configuration, processing returns 503 `AI_PROVIDER_UNAVAILABLE`; uploaded media remains available.

Code path: `app/api/media.py` → `app/services/media_service.py` → `app/services/processing_service.py` → `app/services/processing_worker.py` → `app/ai/gemini_provider.py` / `app/ai/prompts/video_extraction_v1.py` → `app/services/extraction_service.py`.

### Local models (Ollama + whisper.cpp)

Run AI on a separate MacBook Air M2 on the LAN; the backend host needs only `uv`, `ffmpeg` and `ffprobe`, not local AI software. In both backend server and worker environments, replace the Gemini settings with:
```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://192.168.1.42:11434
OLLAMA_MODEL=qwen2.5:7b
WHISPER_BASE_URL=http://192.168.1.42:8080
ENABLE_MEDIA_UPLOAD=true
ENABLE_MEDIA_STREAMING=true
ENABLE_MEDIA_PROCESSING=true
ENABLE_LIVE_EXTRACTION=true
ENABLE_PROCESSING_WORKER=true
PROCESSING_PROVIDER_TIMEOUT_SECONDS=300
PROCESSING_JOB_LEASE_SECONDS=360
```
Replace the example IP with the Mac's LAN address. All three Ollama settings are required; missing values fail startup with `AI_PROVIDER=ollama requires OLLAMA_BASE_URL, OLLAMA_MODEL and WHISPER_BASE_URL`.

On the Mac (quit any Ollama menu-bar app first so port 11434 is free):
```sh
brew install ollama whisper.cpp
curl -fL https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en-q5_1.bin -o ggml-small.en-q5_1.bin
```
Keep these running in separate Mac terminals; `ollama pull` needs the server already up:
```sh
OLLAMA_HOST=0.0.0.0:11434 ollama serve                  # terminal 1
ollama pull qwen2.5:7b                                   # terminal 2, once serve is up
whisper-server --model ./ggml-small.en-q5_1.bin --host 0.0.0.0 --port 8080 --language en --threads 4   # terminal 3
caffeinate -dimsu                                        # terminal 4
```
Then use the server, worker and `video_flow.py` commands above on the backend host.

The backend extracts 16 kHz mono WAV with ffmpeg, sends it to whisper-server `/inference`, then sends the transcript to Ollama `/api/chat` with JSON-schema output. The text-only model reads narration only: visual-only knowledge is not captured. Steps use `source_modality="spoken"`; detected language is whisper's language name (for example, `english`). Q&A/gaps remain deterministic.

Recordings without an audio track return 422 `MEDIA_HAS_NO_AUDIO` at processing; a non-speech-only transcript fails the job with non-retryable `NO_SPEECH_DETECTED`. For an 8 GB Mac under memory pressure, try `ggml-base.en-q5_1.bin`, then `OLLAMA_MODEL=qwen2.5:3b`. For Japanese, download `ggml-small-q5_1.bin` instead and use `--language auto`.

**Use trusted demo Wi-Fi only.** Audio and transcripts travel over plain HTTP; upstream whisper-server warns against untrusted networks. **The live Mac run is unverified:** real whisper.cpp transcription, Qwen quality/speed, Mac RAM, LAN reachability and Windows/other demo-host OS behavior remain unverified. Linux tests and a stub-service smoke passed; stubs are not real models. See [V2_CHECKPOINTS.md](docs/V2_CHECKPOINTS.md#ollama-transcript-provider).

### OpenRouter extraction + local whisper.cpp

This option keeps the existing local whisper.cpp transcription stage and sends only the timestamped transcript to OpenRouter for extraction. Configure the backend server and worker with:
```dotenv
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=xingchen-agi/xing4.0-29b-a4b:free,nvidia/nemotron-3.5-super-vl:free,openrouter/free
WHISPER_BASE_URL=http://192.168.1.42:8080
ENABLE_MEDIA_UPLOAD=true
ENABLE_MEDIA_STREAMING=true
ENABLE_MEDIA_PROCESSING=true
ENABLE_LIVE_EXTRACTION=true
ENABLE_PROCESSING_WORKER=true
PROCESSING_PROVIDER_TIMEOUT_SECONDS=300
PROCESSING_JOB_LEASE_SECONDS=360
```
When whisper-server runs on the same Mac as this backend, use `WHISPER_BASE_URL=http://127.0.0.1:<whisper port>` (for example `http://127.0.0.1:12017`). If the Technical Viva API in `backend/` already uses port 8000, start this server with `--port 8001` and pass `--base-url http://localhost:8001` to `scripts/video_flow.py`.

The existing WhisperServer.app on the Mac is also supported. It listens on IPv6 loopback, so use `WHISPER_BASE_URL=http://[::1]:12017` for a backend on that Mac. The backend tries whisper.cpp's `/inference` first and, on HTTP 404, uses `/v1/audio/transcriptions` with `response_format=verbose_json` and segment timestamps. WhisperServer.app uses its selected default model; no second model server is needed. Check this variant with:
```sh
curl --noproxy '*' -g 'http://[::1]:12017/v1/models'
curl --noproxy '*' -g 'http://[::1]:12017/v1/audio/transcriptions' \
  -F file=@/tmp/p.wav -F response_format=verbose_json \
  -F 'timestamp_granularities[]=segment'
```

`OPENROUTER_MODEL` is a comma-separated fallback list sent as OpenRouter's `models` array: when a model errors (downtime, rate limit), OpenRouter tries the next one. Requests set `provider.require_parameters=true`, so they route only to providers that honor the strict JSON schema. The default list uses free models that advertise structured outputs; keep it `:free`-only (plus `openrouter/free`) to avoid charges. Free models are rate-limited (about 50 requests/day without purchased credits). Output still validates against the application schema; invalid output fails as retryable `AI_RESPONSE_INVALID`. The job's `model_id` records the model that actually answered. OpenRouter receives the transcript, not the original video/audio; transcription stays on the trusted LAN. A synthetic live smoke passed as described below; extraction quality on real expert recordings remains unverified.

## Verification status
Mac smoke (2026-10-25): a generated, narrated 13.1-second MP4 passed real upload, HTTP 206 playback, local WhisperServer.app transcription and live OpenRouter extraction into an unreviewed draft with four timestamp-linked knowledge units. The first Nemotron request did not complete after more than seven minutes; it was manually interrupted, the worker reclaimed the expired lease, and prioritizing the Xing4 free fallback completed the same job using its cached transcript.

That run exposed the difference between HTTPX per-chunk read timeouts and a total deadline. OpenRouter chat calls now also have a wall-clock deadline set by `PROCESSING_PROVIDER_TIMEOUT_SECONDS`, covering connection through the complete response body. Expiry cancels the request, closes the client and returns retryable `PROCESSING_TIMEOUT`; the worker applies its existing retry budget. OpenRouter model fallback still depends on upstream errors; a local timeout does not rotate the model list. Total job time can include transcription, extraction and retries.

This is a synthetic integration check, not validation of real demonstration quality. A follow-up live smoke with the total deadline enabled and Xing4 first completed in 12 seconds and produced three timestamp-linked action units. Current Takumi checks: 213 passed, one opt-in Gemini test skipped; ruff check and format passed.

C4 gates: 113 tests passed; real-server upload and range smoke passed.
C5 gates: 192 tests passed, 1 opt-in live test skipped; ruff check/format clean.
Processing, retries, recovery and V1 integration use mocked provider tests.
**Live Gemini extraction is unverified: no API key is available.** An invalid-key preflight failed safely; it is not proof of provider availability.
Opt in with a real key, model and recording:
```sh
TAKUMI_LIVE_GEMINI=1 GEMINI_API_KEY=… GEMINI_MODEL=… TAKUMI_LIVE_VIDEO=/path/to.mp4 uv run pytest tests/test_gemini_live.py
```
See [V2_CHECKPOINTS.md](docs/V2_CHECKPOINTS.md) for observed checkpoint evidence and final verification status.

## Feature flags
| Setting | Default | Behavior |
|---|---|---|
| DEMO_MODE, ENABLE_DEMO_AUTH, ENABLE_DEMO_SEED, ENABLE_DEMO_RESET | true | Development login, startup seed, reviewer reset |
| DEMO_SEED_STATE | approved_baseline | Initial release_001 |
| ENABLE_GROUNDED_QA | true | Answers only from release snapshots |
| ENABLE_TRAINING_PACK_EXPORT | true | Immutable release export |
| AI_PROVIDER | fixture | fixture, gemini, ollama or openrouter; Q&A/gaps remain deterministic |
| ENABLE_MEDIA_UPLOAD, ENABLE_MEDIA_STREAMING | false | Validated uploads and private ranged playback (C4) |
| ENABLE_LIVE_EXTRACTION, ENABLE_MEDIA_PROCESSING, ENABLE_PROCESSING_WORKER | false | Gemini, Ollama or OpenRouter extraction, durable jobs and separate worker (C5) |
| ENABLE_LIVE_GAP_GENERATION, ENABLE_LIVE_QA, ENABLE_MULTILINGUAL, ENABLE_EMBEDDINGS, ENABLE_ADVANCED_RETRIEVAL, LOG_MODEL_INPUTS | false | Reserved Checkpoint 6 |

Reserved capabilities fail at startup when enabled. Disabled optional endpoints return HTTP 501 `FEATURE_DISABLED`. Core lifecycle and authentication have no off switch. `.env.example` lists every setting.

## Limitations
See [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Media and Gemini extraction code ship here, but successful live Gemini extraction is unverified. No production identity, frontend or scenario/viva engine ships here. Q&A abstains on absent specifications.
