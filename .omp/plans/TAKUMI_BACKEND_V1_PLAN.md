# Takumi V1 Backend & Knowledge Engine — Execution Plan

## Context

The repo `/home/ares/Documents/WORK/hackathon/JETRO-3` contains only planning docs. There is no code, no `backend/` and no `pyproject.toml`. Build the Takumi V1 backend described in the master prompt. A copy of that prompt is saved at `markdowns/globals/takumi_v1_backend_prompt.md` (Step 0). Deliver Checkpoints 0–3 and stop there. That covers the FastAPI app, typed flags, SQLite persistence, demo auth, tasks, drafts, deterministic gap detection, clarifications, evidence, immutable releases, grounded Q&A, the training-pack export, seed/reset, contracts, tests and docs. Also run `/init`, which creates the root `AGENTS.md`. Use subagents for implementation, following the waves below.

Sources (canonical order):
1. `markdowns/hackathon/openapi/API.doc.md`. This is the canonical API contract: routes, fields, error envelope `{"error":{code,message,details}}` and roles `expert|reviewer|apprentice`.
2. The master prompt (Step 0 copy). It defines scope, flags, data model, tests and docs.
3. `markdowns/globals/Takumi_Final_Concept_and_Three_Person_Technical_Plan.docx`. This gives product rules: label illustrative content, never invent torque/tolerance/tactile claims, and abstain on absent specs. It specifies Postgres/Redis, but the V1 prompt overrides that with SQLite and no Redis.
4. `markdowns/hackathon/openapi/*.openapi.json` + `build_openapi.py`. These conflict with API.doc.md: `/studio/*` routes, a flat error object and `learner` roles. **Ignore them for implementation and never edit them.** List the conflicts in the handoff doc only.

Ownership boundary: do NOT implement scenario, attempt, viva or report routes (`/tasks/{id}/scenarios`, `/scenarios/*`, `/attempts/*`). Those belong to the simulation/viva developers. Gemini is **interface only**, per the user's choice. No `google-genai` dependency, and `AI_PROVIDER=gemini` is rejected at startup.

Environment (verified): Python 3.11.17, uv 0.13.5, ffprobe present (unused in V1).

## Approach

### Subagent execution model
- **Step 0 and the final Step 8 (`/init` + final verification):** the orchestrator runs these inline.
- **Wave 1 (Steps 1–2):** one `task` subagent, "Bootstrap". It owns every shared contract file. Run it alone, because everything else depends on it.
- **Wave 2 (Steps 3–4, parallel):** two `task` subagents with disjoint files.
  - "KnowledgeLoop" owns Step 3.
  - "ReleaseQA" owns Step 4.
  - Neither edits `app/main.py`, `app/models/*`, `app/core/*`, `app/config.py` or `app/database.py`. If one needs a shared-schema change, it messages the orchestrator, who applies it.
- **Wave 3 (Steps 5–7):** one `task` subagent, "Integration". It handles baseline seed, reset, scripts, contracts, docs and the integration test.
- Each subagent prompt MUST include: the path of this plan file, the step numbers it owns, and its file list. It must also include the instruction "run only your own tests (`uv run pytest tests/<yours>`) at the end; no repo-wide formatters mid-flight".
- After each wave, the orchestrator runs `cd backend && uv run pytest -q && uv run ruff check .` before starting the next wave.
- **Git (user decision):** all work happens on branch `himanish`. The orchestrator commits after each checkpoint passes, using conventional commits with no AI/agent mention in messages or trailers. Commits:
  1. after Wave 1 → `feat(backend): bootstrap FastAPI app, config, auth, fixture seed (CP0)`
  2. after Wave 2, Step 3 files → `feat(backend): knowledge drafts, clarifications, evidence (CP1)`
  3. Step 4 files → `feat(backend): immutable releases, training pack, grounded Q&A (CP2)`
  4. after Wave 3 → `feat(backend): demo reset, contracts, integration docs (CP3)`
  5. after Step 8 → `docs: add AGENTS.md`
  - Stage explicit paths only (`git add backend markdowns/globals/takumi_v1_backend_prompt.md AGENTS.md`). Never stage the user's untracked `markdowns/hackathon/openapi/API.doc.md`.
  - Do not push.

### Step 0 — Preserve the prompt (orchestrator)
First run `git switch -c himanish`, or `git switch himanish` if it already exists. The repo is currently on `main` @ `8c21655`. Then copy `/home/ares/.omp/agent/sessions/-Documents-WORK-hackathon-JETRO-3/2026-10-24T15-43-27-481Z_01a16e94-caf9-75b8-96b5-9a8741ac9eed/local/paste-1.md` to `markdowns/globals/takumi_v1_backend_prompt.md` with `cp`. Subagents read doc requirements there: §21 handoff, §23 README, §27 checkpoint report format.

### Step 1 — Bootstrap: project, config, DB, errors, auth, health (Wave 1, CP0)

Files: `backend/pyproject.toml`, `backend/IMPLEMENTATION_PLAN.md`, `backend/app/{__init__,main,config,database}.py`, `backend/app/core/{errors,security,logging}.py`, `backend/app/models/{entities,schemas}.py`, `backend/app/api/*.py` (all router modules), `backend/tests/conftest.py`, `backend/tests/test_config.py`.

1. **Project setup.** Run `cd backend && uv init --bare --python 3.11` if `uv init --bare` exists; otherwise write `pyproject.toml` by hand with `name="takumi-backend"`, `version="0.1.0"`, `requires-python=">=3.11"`. Then run:
   - `uv add fastapi "uvicorn[standard]" pydantic-settings sqlalchemy`
   - `uv add --dev pytest httpx ruff`
   - Never hand-edit `uv.lock`.
   - Add `[tool.uv] package = false`.
   - Add `[tool.pytest.ini_options] testpaths=["tests"] pythonpath=["."]`.
   - Add `[tool.ruff] line-length=100, target-version="py311"`, with `[tool.ruff.lint] select=["E","F","I","B","UP"]`.
   - Add `backend/.gitignore` with `data/`, `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`.
2. **`IMPLEMENTATION_PLAN.md`.** Keep it to 60 lines max. Use 4 headings:
   - Stack
   - Key decisions: no core-lifecycle flags; publish = approval; derived release status; Gemini interface only; `FEATURE_DISABLED` = 501; HMAC demo tokens; baseline auto-seed
   - Checkpoints 0–3 exit criteria
   - Contract deviations: copy the Step 7 compatibility notes
3. **`app/config.py`.**
   - Define `class Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` and `get_settings()` using `lru_cache`.
   - Fields and defaults:
     - `app_name="Takumi Knowledge Engine"`
     - `app_env: Literal["development","test","production"]="development"`
     - `database_url="sqlite:///./data/takumi.db"`
     - `demo_mode=True`, `enable_demo_auth=True`, `enable_demo_seed=True`, `enable_demo_reset=True`
     - `demo_seed_state: Literal["fresh","approved_baseline"]`. Wave 1 sets the default to `"fresh"`. Wave 3 changes the default to `"approved_baseline"` (user decision) once baseline seeding works, so every commit starts cleanly.
     - `enable_grounded_qa=True`, `enable_training_pack_export=True`
     - `demo_signing_secret: SecretStr|None=None`, `demo_token_ttl_minutes: int = Field(480, ge=1, le=1440)`
     - `ai_provider: Literal["fixture","gemini"]="fixture"`
     - `enable_live_extraction=False`, `enable_live_gap_generation=False`, `enable_live_qa=False`
     - `gemini_api_key: SecretStr|None=None`, `gemini_model: str|None=None`
     - `enable_media_upload=False`, `enable_media_processing=False`, `enable_media_streaming=False`
     - `max_upload_mb=100`, `max_video_duration_seconds=240`
     - `enable_processing_worker=False`, `processing_max_retries=2`
     - `enable_multilingual=False`, `enable_embeddings=False`, `enable_advanced_retrieval=False`
     - `log_level="INFO"`, `log_model_inputs=False`
     - `cors_origins="http://localhost:3000"`, plus property `cors_origin_list` that splits on commas and strips
     - `max_request_body_kb=1024`
   - Deliberately omitted: `ENABLE_TASK_API`, `ENABLE_KNOWLEDGE_EDITING`, `ENABLE_EXPERT_CLARIFICATION`, `ENABLE_KNOWLEDGE_PUBLICATION`, `ENABLE_EVIDENCE_API` and `ENABLE_AUTH_ENFORCEMENT`. The core lifecycle and auth are never optional. Record this in IMPLEMENTATION_PLAN.
   - Add a `@model_validator(mode="after")` that raises `ValueError` with these exact message patterns:
     - Reserved capabilities: `"<ENV_NAME> is reserved for Checkpoint <N> and not implemented in V1"`. Use a dict:
       - Checkpoint 5: `AI_PROVIDER=gemini`, `ENABLE_LIVE_EXTRACTION`, `ENABLE_MEDIA_PROCESSING`, `ENABLE_PROCESSING_WORKER`, `LOG_MODEL_INPUTS`
       - Checkpoint 4: `ENABLE_MEDIA_UPLOAD`, `ENABLE_MEDIA_STREAMING`
       - Checkpoint 6: `ENABLE_LIVE_GAP_GENERATION`, `ENABLE_LIVE_QA`, `ENABLE_MULTILINGUAL`, `ENABLE_EMBEDDINGS`, `ENABLE_ADVANCED_RETRIEVAL`
     - When `app_env=="production"` and any of `demo_mode`, `enable_demo_auth`, `enable_demo_reset`, `enable_demo_seed` is true: `"<ENV_NAME> must be false when APP_ENV=production"`.
     - When `demo_mode` is false and any `enable_demo_*` flag is true: `"<ENV_NAME> requires DEMO_MODE=true"`.
4. **`app/database.py`.**
   - `class Base(DeclarativeBase)`.
   - `SCHEMA_VERSION = 1`.
   - `def new_id(prefix: str) -> str` returns `f"{prefix}_{uuid4().hex[:12]}"`.
   - `def utcnow() -> datetime` returns a timezone-aware UTC datetime.
   - `def build_engine(settings)`. For sqlite URLs: create the parent dir of the file path (`mkdir(parents=True, exist_ok=True)`), set `connect_args={"check_same_thread": False}`, and add a `connect` event that runs `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000` and `PRAGMA journal_mode=WAL`.
   - `def init_db(engine)`:
     - Run `Base.metadata.create_all`.
     - Create the trigger `CREATE TRIGGER IF NOT EXISTS releases_immutable BEFORE UPDATE ON releases BEGIN SELECT RAISE(ABORT, 'releases are immutable'); END;`.
     - Read or insert `app_meta(key="schema_version")`. If the stored value != `SCHEMA_VERSION`, raise `RuntimeError("Database schema version <x> != expected 1; back up and delete the database file, then restart")`. Never drop data.
   - `def get_db(request)` yields a session from `request.app.state.sessionmaker`, created with `expire_on_commit=False`.
5. **`app/models/entities.py`.** SQLAlchemy 2.x `Mapped` models. All timestamps are `DateTime(timezone=True)`.
   - `AppMeta(key pk, value)`.
   - `Task`:
     - `id` pk str, `title`, `equipment`, `description` nullable, `language`, `source_label`, `owner_id`, `status`, `created_at`, `updated_at`.
     - `active_release_id` nullable str with **no FK**, because a FK would be circular. The service validates it.
   - `Draft`: `id` pk, `task_id` FK unique, `revision` int, `status`, `knowledge_units` JSON, `created_at`, `updated_at`.
   - `DraftRevision`: `id` autoinc, `draft_id` FK, `revision`, `knowledge_units` JSON, `actor_id`, `reason`, `created_at`. Add `UniqueConstraint(draft_id, revision)`.
   - `Evidence`: `id` pk, `task_id` FK, `type`, `author_id`, `author_label`, `content` Text nullable, `media_id` nullable (no FK; no media table in V1), `start_ms`, `end_ms` nullable, `source_label`, `created_at`.
   - `Clarification`: `id` pk, `task_id` FK, `draft_id` FK, `knowledge_unit_id`, `question`, `gap_type`, `priority` int, `status`, `answer` Text nullable, `evidence_id` FK nullable, `answered_by` nullable, `created_at`, `answered_at` nullable.
   - `Release`:
     - `id` pk, `task_id` FK, `version`, `source_draft_revision`, `content_hash`, `approved_by`, `approval_note`, `approved_at`.
     - `task_snapshot` JSON, `knowledge_snapshot` JSON, `evidence_snapshot` JSON.
     - Add `UniqueConstraint(task_id, version)` and `UniqueConstraint(task_id, source_draft_revision)`.
     - **No status column.** Status is derived: `"active"` if `task.active_release_id == id`, else `"superseded"`. Rows are never updated.
   - No ProcessingJob or Media tables in V1. Document the ProcessingJob contract in `docs/KNOWN_LIMITATIONS.md` instead.
6. **`app/models/schemas.py`.** Pydantic v2 API models. Every request model uses `ConfigDict(extra="forbid")`. Literals:
   - `KUField = Literal["action","cue","interpretation","decision","exception"]`
   - `ReviewStatus = Literal["draft","reviewed","approved"]`
   - `EvidenceType = Literal["video_segment","expert_response","reviewer_correction"]`
   - `SourceLabel = Literal["real","illustrative"]`
   - `Disposition = Literal["answered","premise_rejected","unobservable","deferred"]`
   - `ClarificationStatus = Literal["pending","answered","premise_rejected","unobservable","deferred"]`
   - `GapType = Literal["missing_reasoning","changed_condition","beginner_mistake"]`
   - `QAStatus = Literal["answered","needs_context","insufficient_evidence"]`

   Models:
   - `KnowledgeUnit`: id, action (str), cue, interpretation, decision, exception (each `str|None`), `evidence_ids: list[str]`, `field_evidence: dict[KUField, list[str]]`, `review_status`.
   - `EvidenceItemOut`: id, task_id, type, author (= author_label), author_id, content, media_id, start_ms, end_ms, source_label, created_at.
   - `ClarificationOut`: id, knowledge_unit_id, question, status, gap_type, priority, answer, evidence_id, answered_at.
   - `TaskCreate`: title 1–200, equipment 1–200, `description: str|None` max 2000, `language: str="en"` with pattern `^[a-z]{2}$`.
   - `TaskOut`: id, title, equipment, description, language, status, active_release_id, source_label, created_at, updated_at.
   - `TaskListOut{items}`.
   - `DraftOut`: draft_id, task_id, revision, status, knowledge_units, clarifications.
   - `KnowledgeFieldsPatch`:
     - action `str|None` min_length 1, but explicit null is rejected for action.
     - cue, interpretation, decision, exception: `str|None`, where null means "mark unknown".
     - Validator: `model_fields_set` must be non-empty; strings are stripped and must be non-empty.
   - `DraftChange{knowledge_unit_id, fields: KnowledgeFieldsPatch}`.
   - `DraftPatch{expected_revision: int>=1, changes: list[DraftChange] 1..50}`.
   - `DraftPatchOut{draft_id, revision, status, updated_knowledge_unit_ids, correction_evidence_ids}`.
   - `KnowledgeUpdate{knowledge_unit_id, fields}`. Its fields model has only content fields, all non-null when present.
   - `ClarificationRespond{expected_draft_revision:int>=1, disposition, answer: str|None (max 5000), knowledge_update: KnowledgeUpdate|None}`.
   - `ClarificationRespondOut{clarification_id, status, evidence_id: str|None, knowledge_unit_id, draft_revision}`.
   - `PublishRequest{expected_revision:int>=1, approval_note: str 1..1000}`.
   - `PublishOut{release_id, task_id, version, status, approved_by, content_hash}`.
   - `ReleaseOut{id, task_id, version, status, approved_by, approved_at, approval_note, content_hash, knowledge_units, evidence_items}`.
   - `TrainingPackKU`: the KnowledgeUnit fields minus review_status.
   - `TrainingPackEvidence{id,type,author,content,source_label,media_id,start_ms,end_ms}`.
   - `TrainingPack`: `schema_version: Literal["1.0"]`, task_id, release_id, version, title, equipment, language, source_label, approved_by, approved_at, content_hash, knowledge_units, evidence_items.
   - `AskRequest{question: str 1..1000, language="en"}`.
   - `Claim{text, knowledge_unit_id, field: KUField, evidence_ids}`.
   - `AskOut{status, release_id, claims, missing_information, review_required: bool}`.
   - `DemoLoginRequest{demo_user: Literal["expert","reviewer","apprentice"]}`.
   - `DemoLoginOut{access_token, token_type: Literal["bearer"], expires_at, user{id, role, display_name}}`.
   - `DemoResetRequest{scope: Literal["attempts","full_demo"], confirm: str|None, state: Literal["fresh","approved_baseline"]="fresh"}`.
   - `DemoResetOut{success: bool, scope, state}`.
   - `HealthOut{status, database, app_env, demo_mode, ai_provider, schema_version, features: dict[str,bool]}`.
   - `ErrorBody{code, message, details}` and `ErrorEnvelope{error}`.
7. **`app/core/errors.py`.**
   - `class AppError(Exception)` with `__init__(self, code: str, message: str, status_code: int, details: dict|None=None)`.
   - Handlers registered by `register_error_handlers(app)`:
     - `AppError` maps to the envelope.
     - `RequestValidationError` maps to 422 `VALIDATION_ERROR`, with `details={"errors":[{"loc","msg","type"}]}` (no input echo).
     - `StarletteHTTPException` maps to the envelope, with code `{401:"UNAUTHENTICATED",403:"FORBIDDEN",404:"NOT_FOUND",405:"METHOD_NOT_ALLOWED",413:"PAYLOAD_TOO_LARGE"}`, falling back to `"HTTP_ERROR"`.
     - Bare `Exception` maps to 500 `INTERNAL_ERROR` with message `"Internal server error."`, and logs the stack server-side.
   - The complete V1 code set and HTTP statuses (stable; document all in the handoff):

     | Code | HTTP |
     |---|---|
     | `TASK_NOT_FOUND` | 404 |
     | `DRAFT_NOT_FOUND` | 404 |
     | `CLARIFICATION_NOT_FOUND` | 404 |
     | `RELEASE_NOT_FOUND` | 404 |
     | `EVIDENCE_NOT_FOUND` | 404 |
     | `NO_ACTIVE_RELEASE` | 404 |
     | `KNOWLEDGE_UNIT_NOT_FOUND` | 422 |
     | `INVALID_KNOWLEDGE_UPDATE` | 422 |
     | `INVALID_EVIDENCE` | 422 |
     | `CONFIRMATION_REQUIRED` | 422 |
     | `FIXTURE_NOT_AVAILABLE` | 422 |
     | `VALIDATION_ERROR` | 422 |
     | `REVISION_CONFLICT` | 409 |
     | `INVALID_STATE_TRANSITION` | 409 |
     | `PUBLICATION_BLOCKED` | 409 |
     | `UNAUTHENTICATED` | 401 |
     | `FORBIDDEN` | 403 |
     | `FEATURE_DISABLED` | 501 |
     | `RESET_SCOPE_UNAVAILABLE` | 400 |
     | `PAYLOAD_TOO_LARGE` | 413 |
     | `AI_PROVIDER_UNAVAILABLE` | 503 |
     | `METHOD_NOT_ALLOWED` | 405 |
     | `NOT_FOUND` | 404 |
     | `INTERNAL_ERROR` | 500 |
   - Helper `feature_disabled(flag_env: str, checkpoint: int|None=None)` returns `AppError("FEATURE_DISABLED", f"{flag_env} is disabled in this deployment.", 501, {"flag": flag_env, "checkpoint": checkpoint})`. 501 is a user decision; document it as an addition to the API.doc.md status table.
8. **`app/core/security.py`.**
   - `DEMO_USERS` dict (the single place for demo identities):
     - `{"expert": ("expert_001","expert","Demo Expert"), "reviewer": ("reviewer_001","reviewer","Demo Reviewer"), "apprentice": ("apprentice_001","apprentice","Demo Apprentice")}`.
   - `@dataclass(frozen=True) class CurrentUser(id, role, display_name)`.
   - Token format: `b64url(json({"sub","role","iat","exp"}))+"."+b64url(hmac_sha256(key, payload_b64))`. Use stdlib `hmac`, `hashlib` and `base64` only; no JWT dependency.
   - The signing key comes from `settings.demo_signing_secret`, or else from a process-lifetime `secrets.token_urlsafe(32)` held in `app.state.signing_key`, set in `create_app`. Tokens therefore expire on restart unless a secret is set; document this.
   - `issue_token(user_key, settings, key) -> (token, expires_at)`.
   - `get_current_user`:
     - Uses `HTTPBearer(auto_error=False)`.
     - Verification uses `hmac.compare_digest`, checks `exp`, and requires `sub`/`role` to match a `DEMO_USERS` entry.
     - Any failure raises `AppError("UNAUTHENTICATED","Valid bearer token required.",401)`.
     - Never read role headers.
   - `require_roles(*roles)` is a dependency factory that raises `FORBIDDEN` (403).
9. **`app/core/logging.py`.**
   - `configure_logging(level)` sets up a stdlib logging line format.
   - Add an HTTP middleware that takes `X-Request-ID` from the request or generates a uuid4 hex. It logs `request_id method path status duration_ms`, never headers or bodies, and sets the response header `X-Request-ID`.
   - Add a body-size middleware: `Content-Length` > `max_request_body_kb*1024` raises 413 `PAYLOAD_TOO_LARGE`.
10. **`app/main.py`.**
    - `def create_app(settings: Settings|None=None) -> FastAPI`. It stores settings, engine, sessionmaker and signing key on `app.state`, and overrides the `get_settings` dependency to return `app.state.settings`.
    - `lifespan` runs `init_db`. If `demo_mode and enable_demo_seed`, it opens a session, calls `seed_service.seed_demo(session, settings.demo_seed_state)` and commits. Step 2.8 wires this.
    - Middlewares: CORS (`cors_origin_list`, methods `*`, headers `Authorization, Content-Type, X-Request-ID`) and the logging/body-size middlewares.
    - Error handlers.
    - Include every router with `prefix="/api/v1"`: `health, auth, tasks, drafts, clarifications, releases, evidence, qa, media, demo`.
    - Module-level `app = create_app()`.
11. **Routers created in Wave 1.**
    - `app/api/health.py`: `GET /health` (no auth). Runs `SELECT 1`. Returns `HealthOut` with `status:"ok"` and `database:"ok"`; if the DB fails, it returns 503 with `status:"degraded"` and `database:"unavailable"`. `features` lists every boolean `enable_*` setting. It never includes secrets.
    - `app/api/auth.py`: `POST /auth/demo-login`. If `!enable_demo_auth`, it raises `feature_disabled("ENABLE_DEMO_AUTH")`.
    - `app/api/media.py`: reserved routes `POST /tasks/{task_id}/media`, `POST /tasks/{task_id}/process`, `GET /jobs/{job_id}` and `GET /media/{media_id}/stream`. Each requires an authenticated user, then raises `feature_disabled(<flag>, checkpoint)`. Flags: upload → `ENABLE_MEDIA_UPLOAD`,4; process → `ENABLE_MEDIA_PROCESSING`,5; jobs → `ENABLE_MEDIA_PROCESSING`,5; stream → `ENABLE_MEDIA_STREAMING`,4.
    - The remaining modules (`tasks, drafts, clarifications, releases, evidence, qa, demo`) each contain only `router = APIRouter(tags=[...])`. Wave 2/3 fill them.
12. **Tests.**
    - `tests/conftest.py`:
      - Fixture `settings_factory(**overrides)` returns `Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/test.db", app_env="test", demo_signing_secret="test-secret", **overrides)`.
      - Fixture `make_client(**overrides)` builds `TestClient(create_app(settings))` and enters it as a context manager so the lifespan runs.
      - Fixture `client` = `make_client()`.
      - Helper `auth(client, role) -> {"Authorization": f"Bearer {token}"}` via demo-login.
    - `tests/test_config.py` (group A):
      - Defaults have `ai_provider=="fixture"`, all live/media flags false, and work without `GEMINI_API_KEY`.
      - `Settings(_env_file=None, ai_provider="gemini")` raises a ValidationError whose message contains `reserved for Checkpoint 5`.
      - `enable_live_qa=True` raises.
      - `app_env="production"` with the defaults raises `must be false when APP_ENV=production`.
      - `demo_mode=False` with the other defaults raises `requires DEMO_MODE=true`.
      - `GET /api/v1/health` → 200, and the body contains neither `secret` nor `gemini_api_key`.
      - `enable_demo_auth=False` → login 501 `FEATURE_DISABLED`.
      - `POST /api/v1/tasks/task_001/media` with an expert token → 501 `FEATURE_DISABLED`, `details.flag=="ENABLE_MEDIA_UPLOAD"`.
      - `POST /api/v1/tasks/task_001/media` without a token → 401 `UNAUTHENTICATED`.
      - A tampered token → 401.
      - An expired token → 401 (`demo_token_ttl_minutes` cannot be 0, so build the token via `issue_token` with a monkeypatched clock).

Exit (CP0):
- `cd backend && uv run uvicorn app.main:app --port 8000` starts.
- `curl -s localhost:8000/api/v1/health` returns `"status":"ok"`.
- `curl -s localhost:8000/openapi.json` is valid JSON.
- `uv run pytest -q` passes.

### Step 2 — Fixture, AI interface, gap detection, fresh seed (Wave 1, CP1 prerequisite)

Files: `app/fixtures/shaft_bearing_v1.json`, `app/ai/{__init__,base,schemas,fixture_provider}.py`, `app/services/{gap_detection,seed_service}.py`, `tests/test_seed.py`.

1. **`app/fixtures/shaft_bearing_v1.json`.** This is the single location for illustrative content. Exact content:
   - Top-level: `fixture_id:"shaft_bearing_v1"`, `fixture_version:1`, `source_label:"illustrative"`, `disclaimer:"Illustrative training content for the hackathon demonstration; not a validated mechanical procedure."`.
   - `task`: `{"id":"task_001","title":"Shaft and Bearing Inspection","equipment":"Unpowered Shaft-and-Bearing Bench Assembly","description":"Illustrative inspection training for an unpowered shaft-and-bearing bench assembly.","language":"en","source_label":"illustrative","owner_id":"expert_001"}`.
   - `draft`: `{"id":"draft_001","knowledge_units":[...]}` with three units:
     - `ku_001`: action "Inspect the bearing housing"; all other fields null; `evidence_ids:["ev_001"]`; `field_evidence:{"action":["ev_001"]}`; `review_status:"draft"`.
     - `ku_002`: action "Rotate the shaft slowly by hand through one full turn"; cue "Illustrative: a visible wobble at the shaft end during rotation"; interpretation "Illustrative: possible misalignment between the shaft and the bearing"; decision "Illustrative: stop and check bearing seating before continuing the inspection"; exception null; `evidence_ids:["ev_003"]`; field_evidence maps action/cue/interpretation/decision → `["ev_003"]`; `review_status:"draft"`.
     - `ku_003`: action "Check that the base mounting fasteners are present"; other fields null; `evidence_ids:["ev_004"]`; `field_evidence:{"action":["ev_004"]}`; `review_status:"draft"`.
     - In drafts, `review_status` is always `"draft"`. Only release snapshots carry `"approved"`, set by publish. `"reviewed"` stays in the `ReviewStatus` literal for API.doc.md compatibility but V1 never sets it.
   - `evidence_items` (all `source_label:"illustrative"`, `author_id:"expert_001"`):
     - `ev_001`: video_segment, author_label "Illustrative Demonstration", content "Illustrative description of a demonstration segment: the expert inspects the bearing housing.", media_id null, start_ms 25000, end_ms 41000.
     - `ev_003`: expert_response, author_label "Illustrative Example Expert", content "Illustrative example: if the shaft end wobbles while turning it by hand, I stop and check how the bearing is seated before going further."
     - `ev_004`: video_segment, author_label "Illustrative Demonstration", content "Illustrative description of a demonstration segment: the expert checks the base mounting fasteners.", media_id null, start_ms 52000, end_ms 60000.
     - `ev_002` is intentionally absent; it is reserved for the baseline example answer.
   - `example_expert_responses`, used only by Wave 3 baseline:
     ```
     [{"clarification_id":"clar_001","evidence_id":"ev_002","author_label":"Illustrative Example Expert","disposition":"answered",
       "answer":"Illustrative example: I look at the housing first for grease leaking at the seal or discoloration. Leaking grease suggests the seal or bearing may be damaged, so I do not rotate the shaft until a supervisor has checked it.",
       "knowledge_update":{"knowledge_unit_id":"ku_001","fields":{"cue":"Illustrative: grease leaking at the housing seal or discoloration on the housing","interpretation":"Illustrative: possible seal or bearing damage","decision":"Illustrative: do not rotate the shaft; escalate to a supervisor before continuing"}}}]
     ```
   - `baseline_release`: `{"release_id":"release_001","approval_note":"Illustrative baseline release seeded for demonstration."}`.
2. **`app/ai/schemas.py`** (Pydantic):
   - `TaskContext{task_id,title,equipment,language}`.
   - `MediaReference{fixture_id: str|None, media_id: str|None}`.
   - `Provenance{provider, model_id: str|None, prompt_version: str|None, fixture_id: str|None}`.
   - `ExtractionResult{knowledge_units: list[KnowledgeUnit], evidence_items: list[ExtractedEvidence], provenance}`. `ExtractedEvidence` mirrors the fixture evidence fields.
   - `ClarificationCandidate{knowledge_unit_id, gap_type, priority:int, question}`.
   - `ApprovedContext{release_id, knowledge_units: list[KnowledgeUnit], evidence_ids: set[str]}`.
   - `QAProviderResult{status: QAStatus, claims: list[Claim], missing_information: list[str], provenance}`.
3. **`app/ai/base.py`.**
   - `class KnowledgeAIProvider(Protocol)` with:
     - `extract_knowledge(media: MediaReference, task: TaskContext) -> ExtractionResult`
     - `generate_clarifications(knowledge_units: list[KnowledgeUnit], task: TaskContext) -> list[ClarificationCandidate]`
     - `answer_question(question: str, language: str, context: ApprovedContext) -> QAProviderResult`
   - `def get_ai_provider(settings) -> KnowledgeAIProvider` returns `FixtureAIProvider()` when `ai_provider=="fixture"`. Otherwise it raises `AppError("AI_PROVIDER_UNAVAILABLE", "Configured AI provider is not available in V1.", 503)`; this is unreachable because config rejects gemini, but it stays as the explicit boundary.
   - FastAPI dependency `ai_provider(settings=Depends(get_settings))`.
4. **`app/ai/fixture_provider.py`** `FixtureAIProvider`:
   - `extract_knowledge` loads the JSON via `importlib.resources`/`Path(__file__).parent.parent/"fixtures"` when `media.fixture_id=="shaft_bearing_v1"`. It validates the result through `ExtractionResult` plus `evidence_service.validate_evidence_items` (Step 3; in Wave 1 put `validate_evidence_items` in `app/services/evidence_service.py` now, so KnowledgeLoop extends that file). Any other input raises `AppError("FIXTURE_NOT_AVAILABLE","Only the shaft_bearing_v1 fixture can be processed in fixture mode.",422)`. Provenance is `{"provider":"fixture","fixture_id":"shaft_bearing_v1"}`.
   - `generate_clarifications` returns `gap_detection.detect_gaps(units)`.
   - `answer_question` returns `qa_matching.deterministic_answer(...)`. Step 4 owns `qa_matching.py`; in Wave 1 import it lazily inside the method so Wave 1 does not need the module.
5. **`validate_evidence_items(items, task_id, media_duration_ms: int|None=None)`** in `app/services/evidence_service.py`. It raises `AppError("INVALID_EVIDENCE", ..., 422, {"evidence_id":...})` when:
   - an id is duplicated;
   - type/source_label are not allowed;
   - a `video_segment` lacks start/end, or does not satisfy `0 <= start_ms < end_ms`, or `end_ms > media_duration_ms` when the duration is known;
   - a `media_id` is non-null while no media table exists in V1, which means fixture evidence must keep media_id null.
6. **`app/services/gap_detection.py`.** Pure function, deterministic. The weights are the only place for gap priority constants:
   ```
   DECISION_IMPORTANCE = 3; MISSING_REASONING_WEIGHT = {"interpretation": 3, "decision": 3, "cue": 1}
   CHANGED_CONDITION_WEIGHT = 2; NOVICE_CONFUSION_WEIGHT = 2; MAX_QUESTIONS = 3
   TYPE_ORDER = ["missing_reasoning", "changed_condition", "beginner_mistake"]
   ```
   - Candidates per KU:
     - `missing_reasoning` if interpretation or decision is null; priority = `DECISION_IMPORTANCE + sum(weights of null cue/interpretation/decision)`.
     - `changed_condition` if decision is non-null and exception is null; priority = `DECISION_IMPORTANCE + CHANGED_CONDITION_WEIGHT`.
     - `beginner_mistake` if exception is null; priority = `NOVICE_CONFUSION_WEIGHT`.
   - Sort by `(-priority, ku index in draft, TYPE_ORDER index)`. Greedily select, skipping a type already selected, and stop at `MAX_QUESTIONS`.
   - Templates, with `{action}` = the KU action with its first letter lower-cased:
     - missing_reasoning: `"What observation prompts you to {action} at this point, and what does it tell you?"`
     - changed_condition: `"After you {action}, what observation would make you change your next decision?"`
     - beginner_mistake: `"What mistake could a beginner make when they {action}, and how would you recognize it?"`
   - Neutral fallbacks, used when action is empty: `"What observation prompts this step, and what does it tell you?"`, `"What observation would make you change your next decision at this step?"`, `"What mistake could a beginner make at this step, and how would you recognize it?"`.
   - Expected output on the fixture, which also serves as a unit test: `[(ku_001, missing_reasoning, 10), (ku_002, changed_condition, 5), (ku_001, beginner_mistake, 2)]`.
7. **`app/services/seed_service.py`.**
   - `FIXTURE_TASK_ID = "task_001"`.
   - `seed_demo(session, state: Literal["fresh","approved_baseline"]="fresh", provider=None) -> bool`:
     - If `session.get(Task, "task_001")` exists, return False and touch nothing, so genuine edits are never overwritten.
     - Otherwise, in the caller's transaction:
       - `provider.extract_knowledge(MediaReference(fixture_id="shaft_bearing_v1"), ...)`.
       - Insert the Task (`status:"draft"`).
       - Insert the Evidence rows. Their author_id comes from the fixture, `created_at=utcnow()`.
       - Insert Draft `draft_001` at revision 1, plus `DraftRevision(rev=1, reason="seed", actor_id="system")`.
       - Call `provider.generate_clarifications`, then insert the Clarifications with ids `clar_001..clar_00N` in selection order, `status:"pending"`.
       - `session.flush()` and return True. The caller commits.
     - In Wave 1 only `"fresh"` is implemented. `"approved_baseline"` raises `NotImplementedError` until Wave 3 replaces it; Wave 3 MUST remove that raise.
   - **Transaction rule (all waves):** services never call `commit()`. They mutate, then `session.flush()`. Routers, the lifespan and scripts own `commit()`/`rollback()`; use the pattern `with session.begin():` or an explicit commit in the router. This lets Wave 3 compose services into one baseline transaction. Include this rule verbatim in every subagent prompt.
   - `tests/test_seed.py`: seeding twice gives 1 task, 3 evidence rows and 3 clarifications with the exact ids, questions and priorities from item 6. Also test `detect_gaps` on a unit with all fields populated → `[]`.
8. Wire `seed_demo(session, settings.demo_seed_state)` into the `create_app` lifespan, guarded by `demo_mode and enable_demo_seed`. `tests/conftest.py` `settings_factory` passes `demo_seed_state="fresh"` explicitly, so the tests stay fresh after Wave 3 flips the default.

### Step 3 — Knowledge loop: tasks, drafts, clarifications, evidence (Wave 2 "KnowledgeLoop", CP1)

Files: `app/api/{tasks,drafts,clarifications,evidence}.py`, `app/services/{task_service,knowledge_service,clarification_service,evidence_service}.py`, `tests/test_{tasks,drafts,clarifications,evidence}.py`.

1. **Tasks** (`task_service.py`, `api/tasks.py`):
   - `GET /tasks`, any role → `TaskListOut`. Apprentices only see tasks with a non-null `active_release_id`.
   - `POST /tasks`, expert|reviewer → 201 `TaskOut`, with `status:"created"`, `source_label:"real"` and `owner_id` = current user. It makes no AI call.
   - `GET /tasks/{task_id}` → `TaskOut`. A missing task gives 404 `TASK_NOT_FOUND`. An apprentice asking for a task without an active release also gets 404 `TASK_NOT_FOUND`, so no existence leak.
2. **Draft read/patch** (`knowledge_service.py`, `api/drafts.py`).
   - Roles: expert|reviewer. Apprentice → 403 `FORBIDDEN`.
   - `GET /tasks/{id}/draft` → `DraftOut`, with clarifications ordered by id. No draft → 404 `DRAFT_NOT_FOUND` (for example, a task created via the API).
   - Shared helper `apply_field_updates(unit: dict, fields: dict[str, str|None], evidence_id: str|None) -> dict` returns a new dict and never mutates in place. For each content field whose value differs from the current one:
     - set the value;
     - if the value is non-null, append `evidence_id` to `field_evidence[field]`, deduped and order-kept;
     - if the value is null, delete the `field_evidence[field]` key, because unknown has no support;
     - set `evidence_ids` = ordered union of the old ids and `evidence_id`;
     - set `review_status="draft"`.
   - Shared helper `bump_draft(session, draft, expected_revision, new_units, actor_id, reason)`:
     - Executes `update(Draft).where(Draft.id==draft.id, Draft.revision==expected_revision).values(revision=expected_revision+1, knowledge_units=new_units, updated_at=utcnow())`.
     - `rowcount==0` raises `AppError("REVISION_CONFLICT","Draft revision does not match.",409,{"expected":expected_revision,"actual":<current>})`.
     - Inserts a `DraftRevision(revision=expected_revision+1, ...)`.
   - `PATCH /tasks/{id}/draft` → `DraftPatchOut`, as one transaction:
     - Check the revision first: mismatch → 409.
     - An unknown `knowledge_unit_id` gives 422 `KNOWLEDGE_UNIT_NOT_FOUND`, with `details.knowledge_unit_id`. A duplicate id in `changes` gives 422 `VALIDATION_ERROR`. Nothing is applied in either case.
     - For each change whose content values actually differ, create one `Evidence(type="reviewer_correction", author_id=user.id, author_label=user.display_name, source_label="real", content="\n".join(f"{field}: {value}" or f"{field}: (cleared; marked unknown)"))`, then `apply_field_updates` with that id.
     - There is no review_status editing (user decision: publish = approval). `review_status` in `fields` → 422 via `extra="forbid"`.
     - Always bump the revision.
     - `updated_knowledge_unit_ids` = the ids in changes. `correction_evidence_ids` = the new evidence ids.
3. **Clarifications** (`clarification_service.py`, `api/clarifications.py`): `POST /clarifications/{clarification_id}/respond`, expert|reviewer. One transaction, in this order:
   1. Missing clarification → 404 `CLARIFICATION_NOT_FOUND`.
   2. If status != `pending` → 409 `INVALID_STATE_TRANSITION`.
   3. Validation, each giving 422 `INVALID_KNOWLEDGE_UPDATE` with no writes:
      - `disposition=="answered"` requires a non-blank `answer`.
      - `knowledge_update` is only allowed when answered, and its `knowledge_unit_id` must equal the clarification's.
      - `knowledge_update.fields` must be non-empty.
   4. Revision mismatch → 409 `REVISION_CONFLICT`.
   5. If `answer` is non-blank, create `Evidence(type="expert_response", author_id=user.id, author_label=user.display_name, source_label="real", content=answer)`. The service takes an optional `evidence_id`/`author_label`/`source_label` override, used only by the Wave 3 baseline seed.
   6. If answered: `apply_field_updates` (fields from `knowledge_update`, or none) and append the evidence id to `evidence_ids`, even without field updates. Then `bump_draft(reason="clarification")`.
   7. If not answered: the KU is unchanged and the revision is unchanged. Still validate `expected_draft_revision` equals current.
   8. Update the clarification with a conditional `update(...).where(id, status=="pending")`; rowcount 0 → 409 `INVALID_STATE_TRANSITION`. Store `status=disposition`, `answer`, `evidence_id`, `answered_by`, `answered_at`.
   9. Response `ClarificationRespondOut`. `draft_revision` is the post-op revision.
   - Log `clarification answered task_id=… clarification_id=… evidence_id=…`.
4. **Evidence** (`evidence_service.py`, `api/evidence.py`): `GET /evidence/{evidence_id}`, any role.
   - Expert/reviewer: any evidence.
   - Apprentice: only if the id appears in `evidence_snapshot` of any Release with the same task_id. Otherwise 404 `EVIDENCE_NOT_FOUND`, which does not leak existence.
   - Returns `EvidenceItemOut`.
5. **Tests.**
   - `test_tasks.py` (group B):
     - create → get → list persists.
     - Unknown id → 404 `TASK_NOT_FOUND`.
     - Apprentice POST → 403.
     - No token → 401.
     - Apprentice GET `task_001` in the fresh state → 404.
   - `test_drafts.py` (group C):
     - Seeded draft has revision 1, 3 units and 3 clarifications.
     - Patch action → revision 2, a `reviewer_correction` evidence exists, and `field_evidence.action` contains it.
     - Stale revision → 409 with `details.actual`.
     - Unknown KU → 422 and the revision is unchanged.
     - `{"evidence_ids":[...]}` in fields → 422.
     - `{"review_status":"approved"}` in fields → 422.
     - Apprentice GET draft → 403.
   - `test_clarifications.py` (group D):
     - Answer `clar_001` with update fields → evidence created (`type` `expert_response`, author `Demo Expert`, `source_label` `real`); ku_001 cue/interpretation/decision set; `field_evidence` lists the new id; revision 2; the clarification shows `answered`.
     - `premise_rejected` with answer → evidence exists, ku_001 unchanged, revision unchanged, status preserved.
     - Second respond → 409.
     - Atomicity: monkeypatch `knowledge_service.bump_draft` to raise `RuntimeError`, then call via `client` with `raise_server_exceptions=False` → 500. Afterwards the evidence count is unchanged, the clarification is still `pending` and the revision is unchanged.
   - `test_evidence.py` (group F):
     - `ev_001` resolves with `source_label` `illustrative`.
     - Apprentice → 404 before any publication.
     - `validate_evidence_items` rejects `start_ms>=end_ms`, `end_ms>duration`, and duplicate ids.
     - Reviewer `GET /evidence/ev_001` returns `task_id=="task_001"`. The cross-task rejection test lives in Step 4 (publication).

Exit (CP1): a new expert explanation POSTed to `/clarifications/clar_001/respond` creates a persisted evidence row and updates ku_001. Covered by `test_clarifications.py`.

### Step 4 — Publication, releases, training pack, grounded Q&A (Wave 2 "ReleaseQA", CP2 + export)

Files: `app/api/{releases,qa}.py`, `app/services/{publication_service,qa_service,qa_matching}.py`, `tests/test_{publication,training_pack,qa}.py`.

ReleaseQA must not wait for KnowledgeLoop. The fresh seeded draft is already publishable, because every non-null field has evidence. Tests needing ku_001 reasoning use a test-file helper `answer_ku_001(app)`. It opens `app.state.sessionmaker()`, inserts an `Evidence(id="ev_test_answer", type="expert_response", task_id="task_001", source_label="real", author_id="expert_001", author_label="Demo Expert", content=...)`, sets ku_001 cue/interpretation/decision with `field_evidence` → `["ev_test_answer"]`, bumps the draft revision by 1, and commits. It does not touch the PATCH endpoint.

1. **Publish** (`publication_service.publish(session, task_id, req, user, release_id: str|None=None) -> (Release, created: bool)`; `api/releases.py` `POST /tasks/{task_id}/publish`). Role reviewer only, else 403 `FORBIDDEN`. One transaction:
   1. Missing task → 404; missing draft → 404.
   2. If a Release exists with `(task_id, source_draft_revision == req.expected_revision)` and the draft revision still equals it, return it with `created=False`. The router then returns **200**, not 201; this is the idempotent retry.
   3. Draft revision != expected → 409 `REVISION_CONFLICT`.
   4. Validate and collect issues `[{knowledge_unit_id, problem}]`, where problem is one of:
      - (No review-status check: the user decided publish = approval. The reviewer's publish call approves every unit.)
      - `"MISSING_ACTION"`.
      - `"UNSUPPORTED_FIELD:<field>"`: a non-null content field has an empty or missing `field_evidence`.
      - `"INVALID_EVIDENCE:<id>"`: the id is missing or its `Evidence.task_id != task_id`.
      - `"EMPTY_DRAFT"`.
      Any issue → 409 `PUBLICATION_BLOCKED`, `details={"issues":[...]}`.
   5. Snapshot:
      - KUs are copied with `review_status="approved"`. The draft is not modified.
      - Evidence snapshot = list of the `EvidenceItemOut` dicts for every referenced id, sorted by id.
      - `task_snapshot={title,equipment,language,source_label}`.
      - `content_hash = sha256(json.dumps({"knowledge_units":…,"evidence_items":…}, sort_keys=True, separators=(",",":")))`.
      - `version = (max version for task or 0)+1`.
      - `id = release_id or new_id("release")`.
   6. Insert the Release. Set `task.active_release_id`, `task.status="published"`, `task.updated_at`. On `IntegrityError` (concurrent duplicate), roll back and return the existing release for that `source_draft_revision` with `created=False`.
   7. Log `release published task_id release_id version`.
   - Response `PublishOut`, `status:"active"`.
2. **Release reads** (`api/releases.py`), any role:
   - `GET /tasks/{task_id}/release` → `ReleaseOut` of the active release. An unknown task or a task without one → 404 `NO_ACTIVE_RELEASE` (an apprentice gets the same).
   - `GET /releases/{release_id}` → `ReleaseOut`; 404 `RELEASE_NOT_FOUND`.
   - `status` is derived (`active|superseded`). There are no mutation routes, so PATCH/PUT/DELETE give FastAPI's 405 → `METHOD_NOT_ALLOWED` envelope.
3. **Training pack**: `GET /releases/{release_id}/training-pack`, any role.
   - `!enable_training_pack_export` → `feature_disabled("ENABLE_TRAINING_PACK_EXPORT")`.
   - Builds `TrainingPack` purely from the release snapshots (task_snapshot, knowledge_snapshot minus review_status, evidence_snapshot) with `schema_version:"1.0"`.
   - Before returning, assert every KU evidence id is in the evidence snapshot; otherwise raise 500 `INTERNAL_ERROR` and log. This is an invariant guard, not an expected path.
   - Scope note: `validate_required_knowledge` is NOT built. Simulation developers check their required KU ids against `knowledge_units[].id`, as documented in the handoff.
4. **`qa_matching.deterministic_answer(question, language, context: ApprovedContext) -> QAProviderResult`.** Pure and deterministic. Constants live at the top of the module:
   - `INSUFFICIENT_MSG = "The approved knowledge pack does not contain this information."`
   - `NEEDS_CONTEXT_MSG = "Specify which step or component of the task the question refers to."`
   - `LANGUAGE_MSG = "Only English (en) questions are supported in this version."`
   - `SPEC_TERMS = {"torque","tolerance","tolerances","clearance","specification","specifications","spec","specs","rating","rated","pressure","temperature","rpm","speed","preload","newton","newtons","nm","psi","mm","micron","microns","diameter","dimension","dimensions","lubricant","measurement","measurements","force"}`
   - `STOPWORDS = {"the","a","an","is","are","was","were","do","does","did","you","i","we","they","he","she","it","this","that","these","those","to","of","for","in","on","at","by","with","and","or","what","why","how","when","which","who","should","would","could","can","expert","experts","be","there","my","your","their","perform","performs","performed","step","first","then","next","into","from","about","its"}`
   - `INTENTS` is an ordered list of `(regex, fields)`; the first match wins and no match means all five fields:
     1. `r"\b(mistakes?|wrong|avoid|exception|unless|escalat\w*|beginners?|novices?)\b"` → `["exception"]`
     2. `r"\b(why|reason|purpose|because)\b"` → `["interpretation","cue","decision"]`
     3. `r"\b(look for|notice|signs?|cue|observ\w*|see)\b"` → `["cue"]`
     4. `r"\b(next|decide|decision)\b"` → `["decision"]`
     5. `r"\b(how|procedure|action)\b"` → `["action"]`
   - `normalize(q)`: lowercase, replace `[^a-z0-9 ]` with space, split. `stem(t)`: strip `ing` if len>5, else `ed` if len>4, else `s` if len>3 and not `ss`.
   - Algorithm:
     1. `language != "en"` → `needs_context`, `[LANGUAGE_MSG]`.
     2. Raw tokens ∩ SPEC_TERMS, where the term does not appear in the normalized text of any approved KU → `insufficient_evidence`, `[INSUFFICIENT_MSG]`.
     3. Detect the intent fields.
     4. Content tokens = stems of the tokens not in STOPWORDS. If empty → `needs_context`, `[NEEDS_CONTEXT_MSG]`.
     5. Score each KU = |content ∩ stems(all non-null KU field texts)|. Best = highest score, with ties going to the earlier KU. Score 0 → `insufficient_evidence`, `[INSUFFICIENT_MSG]`.
     6. Claims: for each intent field, in order, whose value is non-null and whose `field_evidence[field]` ids are all in `context.evidence_ids`, add `Claim(text=value, knowledge_unit_id, field, evidence_ids=field_evidence[field])`.
     7. No claims → `insufficient_evidence` with `[f"The approved knowledge for '{ku.action}' does not record the {' or '.join(intent fields)}."]`.
     8. Else `answered`.
   - Provenance: `provider:"fixture"`.
5. **`qa_service.ask(session, task_id, req, user, provider) -> AskOut`** and `api/qa.py` `POST /tasks/{task_id}/ask`, any role.
   - `!enable_grounded_qa` → `feature_disabled("ENABLE_GROUNDED_QA")`.
   - Resolve the active release server-side; none → 404 `NO_ACTIVE_RELEASE`.
   - Build `ApprovedContext` **only from the release snapshot**, then call `provider.answer_question`.
   - **Server validation, independent of the provider:** drop any claim whose `knowledge_unit_id` is not in the snapshot, or whose evidence ids are empty or not all in the snapshot evidence set. Log `qa claim rejected`.
   - If the provider said answered but every claim was dropped → `insufficient_evidence`, `[INSUFFICIENT_MSG]`.
   - `review_required=False`. `release_id` = the active release id.
   - Log `qa task_id release_id status`.
6. **Tests.**
   - `test_publication.py` (group E):
     - Expert → 403; apprentice → 403.
     - Unsupported field: directly set ku_003.cue = "x" in the draft without field_evidence, then bump the revision → 409 `PUBLICATION_BLOCKED`, `details.issues` contains `{"knowledge_unit_id":"ku_003","problem":"UNSUPPORTED_FIELD:cue"}`.
     - Fresh draft → 201, version 1, `GET /tasks/task_001/release` matches, content_hash is 64 hex chars, and every KU has `review_status=="approved"`.
     - Retry with the same body → 200 and the same release_id.
     - Stale revision → 409.
     - Mutate the draft (direct DB update and bump revision) → `GET /releases/{v1}` is byte-identical to before.
     - Second publish → version 2; the active pointer moves to v2; v1 `status=="superseded"`.
     - `PATCH /releases/{id}` → 405.
     - A direct ORM update on the Release row raises `sqlalchemy.exc.DatabaseError` (trigger).
     - Cross-task: a second task created in the DB whose draft references `ev_001` (from task_001) → `PUBLICATION_BLOCKED` with `INVALID_EVIDENCE:ev_001`.
   - `test_training_pack.py` (group H):
     - Export v1 → `schema_version` "1.0"; KU ids `ku_001..003`; no `review_status` key; every evidence id resolves within `evidence_items`.
     - After a draft-only edit to ku_003, the pack is unchanged.
     - Flag off → 501 `FEATURE_DISABLED`.
     - Unknown release → 404.
   - `test_qa.py` (group G): call `answer_ku_001(app)` first, then publish as reviewer, then:
     - `"Why do you inspect the bearing housing?"` → `answered`, claims on ku_001, all evidence ids in the release.
     - `"What is the torque specification for the housing bolts?"` → `insufficient_evidence` with `INSUFFICIENT_MSG`.
     - `"Why check the base mounting fasteners?"` → `insufficient_evidence` (reasoning not recorded).
     - `"Why?"` → `needs_context`.
     - Draft-only text: after publishing, set ku_003.interpretation in the draft only → the answer for ku_003 is still `insufficient_evidence`.
     - No release → 404 `NO_ACTIVE_RELEASE`.
     - Flag off → 501.
     - A provider stub returning a claim with a fake evidence id `ev_fake` (override the `ai_provider` dependency) → `insufficient_evidence`, no fabricated citation.
     - Unit-test `deterministic_answer` for `language="ja"` → `needs_context`.

Exit (CP2): `uv run pytest tests/test_publication.py tests/test_qa.py tests/test_training_pack.py` passes.

### Step 5 — Baseline seed, demo reset, scripts (Wave 3 "Integration")

Files: `app/services/seed_service.py` (extend), `app/api/demo.py`, `scripts/{seed_demo,reset_demo,demo_flow,export_contracts}.py`, `tests/test_demo.py`.

1. **Baseline state.** Replace the `NotImplementedError`. `seed_demo(..., "approved_baseline")` first seeds fresh (same transaction), then through the **real services**:
   1. `clarification_service.respond(clar_001, example payload, user=CurrentUser("expert_001","expert","Illustrative Example Expert"), evidence_id="ev_002", source_label="illustrative")`.
   2. `publication_service.publish(..., user=CurrentUser("reviewer_001","reviewer","Demo Reviewer"), release_id="release_001", approval_note=baseline note)`.
   - Then change the `demo_seed_state` default in `app/config.py` to `"approved_baseline"`. Update the Step 1.3 `.env.example` line to match.
   - Fresh-server expectation: `GET /api/v1/tasks/task_001/release` → `release_001` immediately.
2. **`reset_demo(session, state)`.** Delete, in FK-safe order, only rows whose `task_id=="task_001"`: DraftRevision (via the draft), Clarification, Release, Draft, Evidence, Task. Use Core `delete()` statements. The UPDATE trigger does not block DELETE. Then call `seed_demo(session, state)`. All of this happens in one transaction. User-created tasks are untouched.
3. **`POST /demo/reset`** (`api/demo.py`), reviewer only.
   - `!(demo_mode and enable_demo_reset)` → `feature_disabled("ENABLE_DEMO_RESET")`.
   - `scope=="attempts"` → 400 `RESET_SCOPE_UNAVAILABLE`, message `"Learner attempts are owned by the scenario engine; reset them through its reset interface."`.
   - `scope=="full_demo"` with `confirm != "RESET_DEMO_DATA"` → 422 `CONFIRMATION_REQUIRED`.
   - Otherwise `reset_demo`, then commit → 200 `{"success":true,"scope":"full_demo","state":...}`.
4. **Scripts.** Each adds `sys.path` insert of `backend/` and uses `get_settings()`, `build_engine`, `init_db`.
   - `scripts/seed_demo.py --state fresh|approved_baseline` prints `seeded` or `already present; nothing changed`.
   - `scripts/reset_demo.py --state … --yes` refuses without `--yes`. It also refuses when `app_env=="production"` or `!demo_mode`, exiting with code 2 and a message.
   - `scripts/demo_flow.py`:
     - Function `run_flow(client, record=None) -> None` executes the 16-step acceptance sequence below against any httpx-compatible client (a `TestClient` or an `httpx.Client(base_url=...)`). It asserts each status/field and calls `record(name, method, path, request_json, response_status, response_json)` when given.
     - CLI: `uv run python scripts/demo_flow.py --base-url http://localhost:8000` prints one line per step `OK <n> <name>` and exits non-zero on the first failure.
   - Sequence (paths under `/api/v1`):
     1. reviewer login; reset full_demo fresh
     2. expert login; `GET /tasks/task_001/draft` (ku_001 interpretation null)
     3. read `clar_001` from the draft
     4. `POST /clarifications/clar_001/respond` with a new typed explanation + fields
     5. assert `evidence_id`; `GET /evidence/{id}`
     6. re-read the draft → ku_001 `field_evidence.interpretation` contains the id
     7. reviewer publish with `expected_revision` = the current draft revision
     8. `GET /tasks/task_001/release`
     9. `GET /releases/{id}/training-pack`
     10. apprentice login; ask "Why do you inspect the bearing housing?"
     11. assert the claim cites the new evidence id
     12. ask "What is the torque specification for the housing bolts?"
     13. assert `insufficient_evidence`
     14. `PATCH /releases/{id}`
     15. assert 405
     16. reset again and assert the draft is back to revision 1
   - `scripts/export_contracts.py`:
     - Builds an app with `Settings(database_url=sqlite in a TemporaryDirectory, demo_signing_secret="contract-export")`.
     - Writes `contracts/openapi.json` (`app.openapi()`, indent 2).
     - Writes `contracts/{knowledge-unit,clarification,release,training-pack}.json` from `KnowledgeUnit`, `ClarificationOut`, `ReleaseOut`, `TrainingPack` `.model_json_schema()`.
     - Runs `run_flow` with a recorder writing `contracts/api-examples/NN-<name>.json` (`{"request":{method,path,body},"response":{status,body}}`). The `access_token` value is replaced by `"<token>"`.
5. **`tests/test_demo.py`:**
   - Reset as expert → 403.
   - Missing confirm → 422.
   - `attempts` → 400.
   - Flag off → 501.
   - Baseline reset → release_001 active, ku_001 has ev_002 on cue/interpretation/decision, `GET /evidence/ev_002` `source_label=="illustrative"`.
   - Ask about the bearing housing → answered citing ev_002.
   - A user-created task survives a reset.
   - Seeding baseline twice → still 1 release.

### Step 6 — Integration regression test (Wave 3)
- `tests/test_integration.py` (group I): `run_flow(client)` using the `client` fixture. This is the 16-step definition of done. It runs twice in the same test, which proves reset repeatability.

### Step 7 — Contracts and docs (Wave 3, after Steps 5–6 pass)
- Run `uv run python scripts/export_contracts.py` and commit the generated `contracts/` output.
- `backend/.env.example`: every Settings field with its default and a one-line comment. Reserved flags are marked `# reserved: Checkpoint N, must stay false in V1`. `DEMO_SIGNING_SECRET=` is empty, with a comment that it is generated per process when empty.
- `backend/README.md`: follow master prompt §23 headings. Only include commands executed during this run:
  - `uv sync`
  - `cp .env.example .env`
  - `uv run uvicorn app.main:app --reload --port 8000`
  - DB auto-init on startup
  - `uv run python scripts/seed_demo.py --state approved_baseline`
  - `uv run python scripts/reset_demo.py --state fresh --yes`
  - `/docs` + `contracts/openapi.json`
  - `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`
  - a flag table and a pointer to limitations
- `backend/docs/INTEGRATION_HANDOFF.md`: master prompt §21. It covers:
  - An endpoint table (method, path, role, request/response model name, example file in `contracts/api-examples/`, errors, flag).
  - Curl auth example.
  - The Studio workflow (task → draft → clarification → publish, which approves → release/evidence).
  - The simulation workflow (active_release_id → training-pack → check KU ids → `/evidence/{id}` → `/tasks/{id}/ask`).
  - The shared identifier lifetimes: fixture ids are stable; new ids are `<prefix>_<12 hex>`; release/KU/evidence ids are immutable within a release.
  - The error-code table from Step 1.7.
  - **Compatibility notes vs API.doc.md:**
    - additive fields
    - derived release `status`
    - publish retry 200
    - `/demo/reset` `state` field + `attempts` → 400
    - new `/releases/{id}` and `/releases/{id}/training-pack`
    - media/process/jobs/stream → 501 `FEATURE_DISABLED` (501 is added to the status table)
    - no per-unit review step: publishing approves all units; draft `review_status` is always `draft`
    - server auto-seeds `approved_baseline` (`release_001`) on a fresh DB. Run `POST /demo/reset {"scope":"full_demo","confirm":"RESET_DEMO_DATA","state":"fresh"}` before a live expert demo.
    - scenario/attempt/viva/report routes are not served by this backend (owned by teammates; they can mount their routers in `app/main.py` and reuse `get_current_user`/`require_roles`)
    - the conflicts with `markdowns/hackathon/openapi/*.openapi.json` (route prefixes `/studio`, flat error object, `learner` role, `Idempotency-Key` header): this backend follows API.doc.md
    - `GET /tasks/{id}` omits media/processing fields until Checkpoint 4 (additive later)
- `backend/docs/CHECKPOINTS.md`: one section per CP0–3 in the master prompt §27 format, filled with actually executed commands and results.
- `backend/docs/KNOWN_LIMITATIONS.md`:
  - illustrative fixture content
  - no Gemini/live AI, no media, no ProcessingJob table (include its reserved field contract from master prompt §6.7)
  - in-memory signing key when the secret is unset
  - English-only keyword Q&A
  - no production identity
  - SQLite single-writer
  - no `validate_required_knowledge` endpoint

### Step 8 — `/init` and final verification (orchestrator)
1. Create the root `AGENTS.md`. This is what `/init` produces in omp; it runs last so it documents real code. Contents, ≤80 lines:
   - Repo layout: `markdowns/globals` rules/concept, `markdowns/hackathon` specs, `backend/` knowledge engine.
   - The canonical contract path, plus the note not to edit the generated `*.openapi.json`.
   - The ownership boundary (no frontend/3D/scenario/viva code in `backend/`).
   - Verified commands (from `backend/`).
   - Architecture rules: thin routers, services `flush()` and routers commit, illustrative content only in `app/fixtures/`, flags only in `app/config.py`, the error envelope via `AppError`, releases immutable, Q&A only from release snapshots.
   - Testing conventions: `make_client` fixture, temp DB.
2. Run the full verification (below) and report in §27 format.

## Critical files & anchors
- `markdowns/hackathon/openapi/API.doc.md` §3–§8, §12: field names and route shapes to match exactly.
- `markdowns/globals/takumi_v1_backend_prompt.md` (Step 0 copy): §21/§23/§27 doc content requirements; §6.7 ProcessingJob contract.
- `backend/app/services/knowledge_service.py` `apply_field_updates`/`bump_draft`: the shared mutation path for both PATCH and clarification. Revision races are caught here.
- `backend/app/services/qa_service.py`: server-side citation validation. This is the grounding guarantee and must not live in the provider.
- `backend/app/database.py` `init_db`: release immutability trigger + schema version guard.

## Verification
Working dir `backend/`. No env vars or API keys are needed.
1. `uv sync && uv run ruff check . && uv run ruff format --check . && uv run pytest -q` → all pass. Groups A–I are present in `test_config/test_tasks/test_drafts/test_clarifications/test_publication/test_evidence/test_qa/test_training_pack/test_integration`, plus `test_seed`/`test_demo`.
2. Live smoke:
   - `rm -f data/takumi.db`, then start `uv run uvicorn app.main:app --port 8000` (background service).
   - `curl -s localhost:8000/api/v1/health` → `"status":"ok"`, `"ai_provider":"fixture"`.
   - Baseline auto-seed: get a token with `TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/demo-login -H 'Content-Type: application/json' -d '{"demo_user":"apprentice"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')`. Then `curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/tasks/task_001/release` → `"id":"release_001"`, and ku_001 cites `ev_002`.
   - `curl -s -X POST -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/tasks/task_001/media` → HTTP 501, `"code":"FEATURE_DISABLED"`.
   - `uv run python scripts/demo_flow.py --base-url http://localhost:8000` → 16 `OK` lines, exit 0.
   - In step 11, the claim on ku_001 must cite the evidence id created in step 5. That is the new-behavior proof: expert answer → release → grounded answer.
3. Seed idempotency: run `uv run python scripts/seed_demo.py --state fresh` twice against the existing DB → both runs print `already present; nothing changed`, because the baseline is already seeded and nothing is overwritten.
4. Fail-fast: `AI_PROVIDER=gemini uv run python -c "from app.config import Settings; Settings()"` → error containing `reserved for Checkpoint 5`. `APP_ENV=production uv run python -c "…"` → `must be false when APP_ENV=production`.
5. Contracts: `uv run python scripts/export_contracts.py` → `contracts/openapi.json` contains `/api/v1/releases/{release_id}/training-pack`, and `contracts/api-examples/` holds the 16 steps' files.
6. Stop the server.

## Assumptions & contingencies
- User decisions, already applied in the steps:
  - Gemini is interface only.
  - Publish = approval: no per-unit review step.
  - A fresh DB auto-seeds `approved_baseline`.
  - `FEATURE_DISABLED` returns 501.
  - Commits go per checkpoint on branch `himanish`, not pushed.
  - `/init` produces `AGENTS.md`.
  - If a teammate later needs live Q&A, that is Checkpoint 6 work and outside this run.
- Learner reset (`scope:"attempts"`) is not owned here. It returns 400 until the simulation developer provides an agreed reset interface.
- If `uv init --bare` is unavailable in uv 0.13.5, hand-write `pyproject.toml` as specified in Step 1.1 and continue with `uv add`.
- If `PRAGMA journal_mode=WAL` fails on the test filesystem, drop that pragma only and keep `foreign_keys` and `busy_timeout`.
- If FastAPI's 405 for `PATCH /releases/{id}` does not pass through the `StarletteHTTPException` handler as `METHOD_NOT_ALLOWED`, register the handler on `starlette.exceptions.HTTPException` (not `fastapi.HTTPException`). That is the base class covering both.
- If a Wave 2 agent needs a schema field not in Step 1.6, it messages the orchestrator, who adds it to `schemas.py`. Agents must not edit shared files themselves.
- If `git switch -c himanish` fails because of local changes in tracked files, stop and report. Never stash or discard user changes.
