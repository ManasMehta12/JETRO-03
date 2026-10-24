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
uv run uvicorn app.main:app --reload --port 8000
```

## Database
Startup creates SQLite tables, checks schema version and installs the immutable-release UPDATE trigger. A new database automatically seeds `approved_baseline`, with `release_001` active. Existing `task_001` is never overwritten. Schema mismatch fails safely; back up the file before replacing it. Services flush; routers, lifespan and scripts own transactions.

## Demo
```sh
uv run python scripts/seed_demo.py --state approved_baseline
uv run python scripts/demo_flow.py --base-url http://localhost:8765
```
The flow requires a running server on its selected port. It logs 16 successful steps, resets only `task_001`, submits an expert answer, publishes and proves the answer is cited. The live smoke used port 8765 and an isolated temporary SQLite database. All mechanical example content is illustrative, not a validated procedure.

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

## Feature flags
| Setting | Default | Behavior |
|---|---|---|
| DEMO_MODE, ENABLE_DEMO_AUTH, ENABLE_DEMO_SEED, ENABLE_DEMO_RESET | true | Development login, startup seed, reviewer reset |
| DEMO_SEED_STATE | approved_baseline | Initial release_001 |
| ENABLE_GROUNDED_QA | true | Answers only from release snapshots |
| ENABLE_TRAINING_PACK_EXPORT | true | Immutable release export |
| AI_PROVIDER | fixture | Deterministic local provider; gemini rejected |
| ENABLE_MEDIA_UPLOAD, ENABLE_MEDIA_STREAMING | false | Reserved Checkpoint 4 |
| ENABLE_LIVE_EXTRACTION, ENABLE_MEDIA_PROCESSING, ENABLE_PROCESSING_WORKER, LOG_MODEL_INPUTS | false | Reserved Checkpoint 5 |
| ENABLE_LIVE_GAP_GENERATION, ENABLE_LIVE_QA, ENABLE_MULTILINGUAL, ENABLE_EMBEDDINGS, ENABLE_ADVANCED_RETRIEVAL | false | Reserved Checkpoint 6 |

Reserved capabilities fail at startup when enabled. Disabled optional endpoints return HTTP 501 `FEATURE_DISABLED`. Core lifecycle and authentication have no off switch. `.env.example` lists every setting.

## Limitations
See [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). No Gemini, media pipeline, production identity, frontend or scenario/viva engine ships here. Q&A abstains on absent specifications.
