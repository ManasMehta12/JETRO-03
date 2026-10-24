# Takumi Knowledge Engine

## Setup
From `backend/`, Python 3.11+ and uv:
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
Start server and worker in separate terminals from `backend/`, sharing `DATABASE_URL`, `MEDIA_STORAGE_DIR` and configuration:
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

## Verification status
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
| AI_PROVIDER | fixture | fixture, gemini or ollama; Q&A/gaps remain deterministic |
| ENABLE_MEDIA_UPLOAD, ENABLE_MEDIA_STREAMING | false | Validated uploads and private ranged playback (C4) |
| ENABLE_LIVE_EXTRACTION, ENABLE_MEDIA_PROCESSING, ENABLE_PROCESSING_WORKER | false | Gemini or Ollama extraction, durable jobs and separate worker (C5) |
| ENABLE_LIVE_GAP_GENERATION, ENABLE_LIVE_QA, ENABLE_MULTILINGUAL, ENABLE_EMBEDDINGS, ENABLE_ADVANCED_RETRIEVAL, LOG_MODEL_INPUTS | false | Reserved Checkpoint 6 |

Reserved capabilities fail at startup when enabled. Disabled optional endpoints return HTTP 501 `FEATURE_DISABLED`. Core lifecycle and authentication have no off switch. `.env.example` lists every setting.

## Limitations
See [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Media and Gemini extraction code ship here, but successful live Gemini extraction is unverified. No production identity, frontend or scenario/viva engine ships here. Q&A abstains on absent specifications.

## Expert Studio demo workflow

The current integrated demo is documented in the [root README](../README.md#one-button-diagnosis-demo) and [remediation runbook](../audits/2026-10-25-demo-remediation.md). `/studio` diagnoses source notes with three bounded AI roles, proposes source-extractive patches, evaluates them, and waits for human approval before applying/publishing. Missing keys show an unconfigured live state. Illustrative rehearsal requires explicit selection and `mode: rehearsal` in the request. A live failure never falls back to fixtures.

In `DEMO_MODE=true`, both Studio and legacy publication endpoints require a fresh passing evidence evaluation and explicit human publication. No separate admin grant is required. Outside demo mode, the revision/content-specific authorization remains required. Demo identities are not production account management.

AI analysis records and stages live in `studio_analysis_runs`; schema 6 is an additive migration. Provider calls run outside database transactions. Approving selected proposals checks the draft revision, creates attributed evidence, applies patches, evaluates and publishes atomically. Unanswered prompts require explicit deferral or a recorded response. Existing clarification responses can carry `knowledge_update` to apply a selected field.

Full fixture reset now also clears learner enrollments, manual completions and diagnosis runs. It is destructive and must be explicitly requested; it is not part of preflight. Learner-only reset uses `/api/v1/learning/reset` and leaves published course content in place. A new publication starts a fresh learning context; historical learner reports across releases remain future work.