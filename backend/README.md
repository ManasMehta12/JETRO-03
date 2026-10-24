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
| AI_PROVIDER | fixture | fixture or gemini; Q&A/gaps remain deterministic in both |
| ENABLE_MEDIA_UPLOAD, ENABLE_MEDIA_STREAMING | false | Validated uploads and private ranged playback (C4) |
| ENABLE_LIVE_EXTRACTION, ENABLE_MEDIA_PROCESSING, ENABLE_PROCESSING_WORKER | false | Gemini extraction, durable jobs and separate worker (C5) |
| ENABLE_LIVE_GAP_GENERATION, ENABLE_LIVE_QA, ENABLE_MULTILINGUAL, ENABLE_EMBEDDINGS, ENABLE_ADVANCED_RETRIEVAL, LOG_MODEL_INPUTS | false | Reserved Checkpoint 6 |

Reserved capabilities fail at startup when enabled. Disabled optional endpoints return HTTP 501 `FEATURE_DISABLED`. Core lifecycle and authentication have no off switch. `.env.example` lists every setting.

## Limitations
See [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Media and Gemini extraction code ship here, but successful live Gemini extraction is unverified. No production identity, frontend or scenario/viva engine ships here. Q&A abstains on absent specifications.
