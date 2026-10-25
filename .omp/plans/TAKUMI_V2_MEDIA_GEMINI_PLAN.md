# Takumi V2 — Real media and Gemini extraction (C4 + C5)

## Context
Implement the V2 master prompt (session file `local://paste-2.md`; copy it to `markdowns/globals/takumi_v2_backend_prompt.md` in Step 0) on top of the finished V1 backend in `backend/`. The repo is `/home/ares/Documents/WORK/hackathon/JETRO-3`, branch `himanish`.

End state:
- An expert uploads a real MP4. It is validated with ffprobe, stored privately, and streamed with byte ranges through a short-lived signed URL.
- A durable SQLite job, run by a separate worker process, sends the recording to Gemini via the Files API and gets structured JSON back.
- The extraction is validated and persisted atomically as a V1 draft with video evidence and deterministic clarifications.
- That draft then flows through the unchanged V1 clarify → publish → training-pack → ask path.
- The V1 fixture flow (`scripts/demo_flow.py`, 16 steps) stays green with no credentials.

Implementation uses subagents in waves (see Execution).

User decisions (fixed):

| Topic | Decision |
|---|---|
| Existing draft | Processing a task that already has a draft → 409 `DRAFT_ALREADY_EXISTS`. Workflow: create a task, upload, process. |
| Playback | Signed URL, valid 10 min, scoped to one media id: `GET /media/{id}` returns `playback_url`. The bearer header also works on `/stream`. |
| Apprentice media access | Only when the media is cited in any release snapshot of its task (mirrors V1 evidence visibility). |
| Upload formats | MP4 container only (reject QuickTime `qt` brand); video codec `h264` or `av1`. |
| Invalid model timestamps | Keep the step as a knowledge unit with **no** evidence and add a job warning. Never clamp. Publishing stays blocked until the expert fixes it via PATCH. |
| Schema-invalid model output | Retry once automatically (reusing the uploaded provider file), then fail `AI_RESPONSE_INVALID`. |
| Optional flags | `ENABLE_MEDIA_CLEANUP` and `ENABLE_EXTRACTION_DEBUG_LOGS`: not built. Gemini provider files are always deleted after success; raw model output is never logged. |
| Task detail | Unchanged. The frontend tracks `media_id` and `job_id` from the upload and process responses (documented deviation). |
| Gemini model | `GEMINI_MODEL` is required, with no default. No key is available, so the live path stays **unverified**: mocked tests plus an opt-in live test that is reported as skipped. |
| Evaluator | Gemini (the AI judge) reviews the code, and the platform provides AI access. Docs must label verified vs unverified honestly, and the upload→Gemini→draft path must be easy to find. |
| Git | One commit per checkpoint, then push `origin himanish` after all gates pass. |

## Ground rules (every subagent gets these)
- **Never edit or stage:**
  - `markdowns/hackathon/openapi/API.doc.md` (the canonical contract, untracked user file)
  - `markdowns/hackathon/openapi/*.openapi.json`
  - `build_openapi.py`
  - anything under `markdowns/` except the new prompt copy
- **Architecture:**
  - Routers in `app/api/` stay thin; logic lives in `app/services/`.
  - Services only `flush()`; routers, scripts and the worker own transactions.
  - Errors are raised as `AppError(code, message, status, details)` (`app/core/errors.py`).
  - All flags live in `app/config.py`.
- **SQLite transactions:**
  - Every transaction runs `BEGIN IMMEDIATE` (`app/database.py` begin event), and session autobegin also takes the write lock.
  - Never run ffprobe, file copies or any Gemini call while a session has an open transaction.
  - Wrap DB work in a `with session.begin():` block that ends before the slow step.
- **Tests:**
  - `tests/conftest.py`: `make_client(**overrides)`, the `client` fixture and `auth(client, role)`.
  - Tests use a temp DB with `demo_seed_state="fresh"`.
  - Use `client.app.state.sessionmaker()` for direct DB access.
- **Dependencies:** add only with `uv add` and never hand-edit `uv.lock`. Subagents do not run the full suite, ruff or the formatter mid-flight. They run only their own new test files; the orchestrator runs the gates.
- **Unchanged contracts:**
  - Existing response models: `DraftOut`, `EvidenceItemOut`, `ReleaseOut`, `TrainingPack`, `PublishOut`, `AskOut`.
  - The 16-step `scripts/demo_flow.py` and `contracts/api-examples/`.

## Approach

### Step 0 — Setup (orchestrator)
1. Copy the session file `local://paste-2.md` to `markdowns/globals/takumi_v2_backend_prompt.md`.
2. In `backend/`, record the baseline with `uv run pytest -q` (expect 88 passed).
3. Run `uv add python-multipart google-genai`. Record the installed `google-genai` version (`uv pip show google-genai`); subagents verify SDK methods against it.

### Step 1 — Configuration (Wave 1, MediaC4 agent; all config for C4 and C5 lands here)
Edit `app/config.py` `Settings`:
- **Add:**
  - `media_storage_dir: Path = Path("./data/media")`
  - `processing_poll_interval_seconds: float = Field(2.0, gt=0)`
  - `processing_job_lease_seconds: int = Field(180, ge=30)`
  - `processing_provider_timeout_seconds: int = Field(120, ge=10)`
- **Add bounds:**
  - `max_upload_mb` `ge=1`
  - `max_video_duration_seconds` `ge=1`
  - `processing_max_retries` `ge=0, le=5`
- **In `validate_capabilities`:**
  - Remove the reserved-flag rejections for `enable_media_upload`, `enable_media_streaming`, `ai_provider == "gemini"`, `enable_live_extraction`, `enable_media_processing` and `enable_processing_worker`.
  - Move `log_model_inputs` into the Checkpoint 6 reserved list.
  - Change the reserved message template from "…not implemented in V1" to `f"{name} is reserved for Checkpoint {checkpoint} and not implemented yet"`.
- **New `ValueError`s** (exact messages):
  - `ai_provider == "gemini"` with an empty or missing `gemini_api_key` or `gemini_model` → `"AI_PROVIDER=gemini requires GEMINI_API_KEY and GEMINI_MODEL"`
  - `enable_live_extraction` without (`ai_provider == "gemini"` and `enable_media_processing`) → `"ENABLE_LIVE_EXTRACTION requires AI_PROVIDER=gemini and ENABLE_MEDIA_PROCESSING=true"`
  - `enable_media_processing` without `enable_media_upload` → `"ENABLE_MEDIA_PROCESSING requires ENABLE_MEDIA_UPLOAD=true"`
  - `enable_processing_worker` without `enable_media_processing` → `"ENABLE_PROCESSING_WORKER requires ENABLE_MEDIA_PROCESSING=true"`
  - `processing_job_lease_seconds <= processing_provider_timeout_seconds` → `"PROCESSING_JOB_LEASE_SECONDS must exceed PROCESSING_PROVIDER_TIMEOUT_SECONDS"`
- **`tests/conftest.py` `settings_factory` defaults:** add `media_storage_dir=tmp_path / "media"`.
- **`tests/test_config.py`:**
  - Replace the `{"ai_provider": "gemini"}` "reserved for Checkpoint 5" case with the five new messages.
  - Add one case showing that `ai_provider="gemini", gemini_api_key="k", gemini_model="m"` constructs successfully.

### Step 2 — Schema v2 with an additive migration (Wave 1)
- `app/database.py`:
  - Set `SCHEMA_VERSION = 2`.
  - In `init_db`, an existing stored version that is a decimal with `1 <= int(version) < SCHEMA_VERSION` is upgraded: `UPDATE app_meta SET value=str(SCHEMA_VERSION)`. Comment: `# every upgrade since v1 only adds tables, which create_all already created`.
  - Any other mismatch raises `RuntimeError(f"Database schema version {version} != expected {SCHEMA_VERSION}; back up and delete the database file, then restart")`.
- `app/models/entities.py` — add `MediaAsset` (`media_assets`). `Mapped` style follows `Evidence`:
  - `id` str PK
  - `task_id` FK `tasks.id`
  - `owner_id` str
  - `original_filename` str
  - `storage_key` str unique
  - `mime_type` str
  - `container` str
  - `size_bytes` int
  - `sha256` str
  - `duration_ms` int
  - `video_codec` str
  - `audio_codec` str | None
  - `width` int
  - `height` int
  - `status` str (always `"uploaded"`)
  - `created_at` (default `utcnow`)
- `tests/test_seed.py`: add a test that opens a DB stamped `"1"`, restarts, and sees version `"2"` with `media_assets` present. The existing `"99"` rejection test stays.

### Step 3 — Signed playback tokens (Wave 1)
`app/core/security.py`:
- **Factor out:**
  - `_sign(data: dict, key: str) -> str` (the payload/signature code from `issue_token`)
  - `_verify(token: str, key: str) -> dict` (split, `compare_digest`, decode, `exp` check from `get_current_user`)
  - Both existing functions call these; their behaviour is unchanged.
- **`get_current_user`:** additionally raise `ValueError` when `"scope" in data`, so playback tokens can't be used as bearer tokens.
- **Add:**
  - `PLAYBACK_TOKEN_TTL = timedelta(minutes=10)`
  - `issue_playback_token(media_id: str, user: CurrentUser, key: str) -> tuple[str, datetime]` with payload `{"sub", "role", "scope": "playback", "media_id", "exp"}`
  - `verify_playback_token(token: str, media_id: str, key: str) -> CurrentUser`. It requires `scope == "playback"`, a matching `media_id` and a known identity; any failure → `AppError("UNAUTHENTICATED", "Valid playback token required.", 401)`.

### Step 4 — Upload pipeline (Wave 1)
**Middleware, `app/core/logging.py` `request_logging`:**
- For `POST` requests whose path matches `^/api/v1/tasks/[^/]+/media$`:
  - limit = `settings.max_upload_mb * 1024 * 1024 + 1024 * 1024` (multipart overhead)
  - error = `AppError("MEDIA_TOO_LARGE", "Upload exceeds the configured limit.", 413, {"max_upload_mb": …})`
- All other requests keep the existing limit and code.
- Log the path only (already true).

**CORS, `app/main.py`:**
- Add `"Range"` to `allow_headers`.
- Add `expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"]`.

**New `app/services/media_service.py`:**
- **Constants:**
  - `CHUNK = 1024 * 1024`
  - `FFPROBE_TIMEOUT = 30`
  - `ALLOWED_VIDEO_CODECS = {"h264", "av1"}`
- **`probe(path: Path) -> dict`:**
  - Command: `subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_entries", "format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height", str(path)], capture_output=True, timeout=FFPROBE_TIMEOUT, shell=False, check=False)`
  - `FileNotFoundError` → `AppError("FFPROBE_UNAVAILABLE", "Media inspection tool is not installed on the server.", 503)`
  - `TimeoutExpired`, non-zero exit, stdout > 1_000_000 bytes, or unparsable JSON → `INVALID_MEDIA` 422.
  - Returns `{container: "mp4", duration_ms, video_codec, audio_codec | None, width, height}`.
- **MP4 rule:** `"mp4"` in `format_name.split(",")` and `major_brand.strip().lower() != "qt"` → `container = "mp4"`, `mime_type = "video/mp4"`.
- **Rejections (each `INVALID_MEDIA` 422 with `details.reason`):**
  - container not MP4 → `"unsupported_container"`
  - no video stream → `"no_video_stream"`
  - codec not allowed → `"unsupported_codec"`, plus `details.codec`
  - duration missing or ≤ 0 → `"no_duration"`
  - empty file → `"empty_file"`
- **Too long:** duration > `max_video_duration_seconds * 1000` → `AppError("MEDIA_TOO_LONG", …, 422, {"duration_ms", "max_seconds"})`.
- **`receive_upload(settings, upload: UploadFile) -> ReceivedMedia`** (dataclass: `temp_path`, `original_filename`, `size_bytes`, `sha256`, plus the probe fields):
  - Create `settings.media_storage_dir / ".tmp"` (same filesystem as the final dir) and write a `NamedTemporaryFile(dir=…, delete=False, suffix=".upload")`.
  - Copy `upload.file.read(CHUNK)` chunks, updating `hashlib.sha256` and the byte count. More than `max_upload_mb` MiB → `MEDIA_TOO_LARGE` 413.
  - Then `probe`.
  - On any exception, unlink the temp file, then re-raise.
  - `original_filename = Path(upload.filename or "upload.mp4").name[:255]`; it is display-only and never used in paths.
- **`save_media(session, settings, task_id, user, received) -> MediaAsset`:**
  - `media_id = new_id("media")`, `storage_key = f"{task_id}/{media_id}.mp4"`.
  - Resolve `final = (settings.media_storage_dir / storage_key).resolve()` and assert it stays inside `settings.media_storage_dir.resolve()`.
  - Add the row and `flush()`, then `mkdir` the parent and `os.replace(temp_path, final)`.
- **`discard(settings, received, storage_key: str | None)`:** unlinks the temp file and the final file if present (missing is OK).
- **`remove_stored_files(settings, storage_keys: list[str]) -> None`:** best-effort unlink, ignoring missing files.
- **`get_visible_media(session, media_id, user) -> MediaAsset`:**
  - Missing → `AppError("MEDIA_NOT_FOUND", "Media not found.", 404)`.
  - Apprentice: allowed only if some `Release` with `task_id == media.task_id` has an `evidence_snapshot` item with `media_id == media.id`; otherwise the same 404.
- **`media_path(settings, media) -> Path`:** the resolved path. A missing file → `AppError("MEDIA_NOT_FOUND", "Media source file is unavailable.", 404)`.
- **`media_out(media, settings, key, user) -> MediaOut`:** fills `playback_url = f"/api/v1/media/{media.id}/stream?token={token}"` and `playback_expires_at` from `issue_playback_token`.

**Schema, `app/models/schemas.py` `MediaOut`:**
- Fields: `media_id`, `task_id`, `filename`, `status`, `duration_ms`, `mime_type`, `size_bytes`, `sha256`, `video_codec`, `audio_codec: str | None`, `has_audio: bool`, `width`, `height`, `created_at`, `playback_url: str`, `playback_expires_at: datetime`.

**Routes, `app/api/media.py`:**
- Remove the router-level `dependencies=[Depends(get_current_user)]` and add auth per route. Keep the process and job stubs until Wave 2, with `require_roles("expert", "reviewer")`.
- **`POST /tasks/{task_id}/media` — 201, `MediaOut`, roles expert/reviewer:**
  1. Raise `feature_disabled("ENABLE_MEDIA_UPLOAD", 4)` if the flag is off.
  2. Check the task: `with session.begin(): task_service.get_task(session, task_id, user)`.
  3. `received = media_service.receive_upload(settings, file)`, with `file: UploadFile = File(...)`.
  4. In `try: with session.begin(): media = save_media(...)` / `except BaseException: media_service.discard(settings, received, storage_key_if_assigned); raise`.
  5. Return `media_out`.
- **`GET /media/{media_id}` — 200, `MediaOut`:**
  - Any authenticated user, subject to `get_visible_media`.
  - Gated by `ENABLE_MEDIA_STREAMING` → `feature_disabled("ENABLE_MEDIA_STREAMING", 4)`.
- **`GET /media/{media_id}/stream`:**
  - Same flag. Parameters: `token: str | None = Query(None)` and the bearer credentials (`Depends(bearer)`).
  - User: from `verify_playback_token` if `token` is given, else `get_current_user(request, credentials)`.
  - Inside `with session.begin():` run `get_visible_media`, then `media_path`; the transaction ends before the response.
  - Return `FileResponse(path, media_type=media.mime_type)`. Starlette handles `Range` (206, `Accept-Ranges`, `Content-Range`, 416); never parse ranges manually.

**Evidence, `app/services/evidence_service.py`:**
- Extract `interval_problem(start, end, duration_ms: int | None) -> str | None`, using the existing messages (`"Invalid video evidence interval."`, `"Video evidence interval exceeds media duration."`).
- Change the signature to `validate_evidence_items(items, task_id, media_duration_ms: int | None = None, media_id: str | None = None)`.
- A non-null item `media_id` is accepted only when it equals the `media_id` argument. Otherwise keep the existing V1 message `"Media references are not available in V1."`, so the fixture and existing tests are unchanged.

**Reset:**
- `seed_service.reset_demo` deletes `MediaAsset` rows for `FIXTURE_TASK_ID` before deleting `Task`. Before deleting, it collects their `storage_key`s and returns them (return type becomes `list[str]`).
- `api/demo.py` and `scripts/reset_demo.py` call `media_service.remove_stored_files(settings, keys)` after the transaction commits.
- `tests/test_demo.py` callers ignore the return value.

**C4 tests, new `tests/test_media.py`:**
- **Session fixture `sample_videos(tmp_path_factory)`:**
  - Skip the module if `shutil.which("ffmpeg")` or `which("ffprobe")` is None.
  - `ok.mp4`: `ffmpeg -v error -f lavfi -i testsrc=duration=3:size=320x240:rate=10 -f lavfi -i sine=duration=3 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest`
  - `silent.mp4`: no audio.
  - `fake.mp4`: text bytes.
- **Client:** `make_client(enable_media_upload=True, enable_media_streaming=True)`.
- **Cases:**

  | # | Case | Expect |
  |---|---|---|
  | C4.1 | Valid upload | 201; row exists; file at `media_storage_dir/task_001/<id>.mp4`; `sha256` equals `hashlib` of the source; `2900 <= duration_ms <= 3100`; `has_audio` true; silent → `has_audio` false |
  | C4.2 | `fake.mp4` | 422 `INVALID_MEDIA`; no row; `.tmp` dir empty |
  | C4.3a | `max_upload_mb=1` with a >1 MiB file (`ffmpeg` with `testsrc` at higher bitrate, or `os.urandom` bytes) | 413 `MEDIA_TOO_LARGE`; `.tmp` empty |
  | C4.3b | Declared `Content-Length` over the limit | Middleware 413 |
  | C4.4 | `max_video_duration_seconds=1` | 422 `MEDIA_TOO_LONG` |
  | C4.5 | Auth | Expert 201, reviewer 201, apprentice 403, no token 401, unknown task 404 `TASK_NOT_FOUND`, flag off 501 `FEATURE_DISABLED` |
  | C4.6 | Streaming | Full GET 200 with the exact size; `Range: bytes=0-1023` → 206 with `Content-Range: bytes 0-1023/<size>` and `Accept-Ranges: bytes`; `Range: bytes=999999999-` → 416; unknown id 404 `MEDIA_NOT_FOUND`; no auth 401; playback token for another media id 401; bearer `playback_url` token works without a header; playback token as bearer on `/api/v1/tasks` → 401; apprentice 404 until an evidence row citing the media is published in a release, then 200 (insert `Evidence` + publish via service, or a direct `Release` row) |
  | C4.7 | Evidence | Insert `Evidence(type="video_segment", media_id=…, start_ms=500, end_ms=1500)`. `validate_evidence_items` passes with `media_id` + duration and fails with `end_ms > duration`. `GET /evidence/{id}` returns `media_id` and the interval. |
  | C4.8 | Persistence | Second `make_client` on the same DB path: `GET /media/{id}` 200 and stream 200 |

### Step 5 — Commit C4 (orchestrator)
1. Gates from `backend/`: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`.
2. Smoke: run `uvicorn` with `ENABLE_MEDIA_UPLOAD=true ENABLE_MEDIA_STREAMING=true` and do upload, GET, range and 416 via Python `urllib` in `eval` (`curl` is blocked by a hook).
3. Commit `feat(backend): media upload, ffprobe validation and range streaming (C4)`.

### Step 6 — Shared C5 contract code (orchestrator writes before Wave 2)
**Append to `app/ai/schemas.py`:**
```python
class ExtractedStep(BaseModel):
    start_ms: int
    end_ms: int
    action: str
    cue: str | None = None
    interpretation: str | None = None
    decision: str | None = None
    exception: str | None = None
    source_modality: Literal["visual", "spoken", "visual_and_spoken"]
    evidence_description: str | None = None

class VideoExtractionResult(BaseModel):
    task_summary: str
    detected_language: str | None = None
    steps: list[ExtractedStep] = Field(default_factory=list)
    processing_warnings: list[str] = Field(default_factory=list)

class ProviderFile(BaseModel):
    name: str
    uri: str
    mime_type: str
    state: str  # PROCESSING | ACTIVE | FAILED
    expires_at: datetime | None = None

class VideoExtraction(BaseModel):
    result: VideoExtractionResult
    usage: dict[str, Any] | None = None
    model_id: str
    prompt_version: str
```

**Append to `app/ai/base.py`:**
```python
class ProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.code, self.message, self.retryable, self.retry_after_seconds = code, message, retryable, retry_after_seconds

class VideoExtractor(Protocol):
    provider: str
    model_id: str
    def check_model(self) -> None: ...
    def upload_file(self, path: Path, mime_type: str, display_name: str) -> ProviderFile: ...
    def wait_until_active(self, name: str, on_poll: Callable[[], None]) -> ProviderFile: ...
    def extract_video(self, file: ProviderFile, task: TaskContext, duration_ms: int, has_audio: bool) -> VideoExtraction: ...
    def delete_file(self, name: str) -> None: ...

def get_video_extractor(settings) -> VideoExtractor:
    from app.ai.gemini_provider import GeminiAIProvider
    return GeminiAIProvider(settings)
```

**Change `get_ai_provider`:**
- Return `FixtureAIProvider()` for both `"fixture"` and `"gemini"`.
- Comment: `# Q&A and gap detection stay deterministic in V2; Gemini is used only for worker video extraction.`
- This keeps `/ask` working when `AI_PROVIDER=gemini`.

**Stub to get the tree importable:** `app/ai/gemini_provider.py` containing only `class GeminiAIProvider: def __init__(self, settings): self.settings = settings`. GeminiAdapter replaces it.

### Step 7 — Gemini adapter (Wave 2, GeminiAdapter agent; parallel with Step 8)
**New `app/ai/prompts/__init__.py` and `app/ai/prompts/video_extraction_v1.py`:**
- `PROMPT_VERSION = "video_extraction_v1"`.
- `build_prompt(task: TaskContext, duration_ms: int, has_audio: bool) -> str` contains:
  - the V2 prompt §10 instruction text verbatim
  - the task context as JSON (`task_title`, `equipment`, `expected_language`)
  - `"Timestamps are integer milliseconds from the start of the recording. The recording lasts {duration_ms} ms; every interval must satisfy 0 <= start_ms < end_ms <= {duration_ms}."`
  - the granularity guidance: "Prefer a small number (about 3–10) of meaningful actions or decision points; never invent steps to reach a count."
  - when `has_audio` is false: `"This recording has no audio track. Do not report spoken content; use source_modality \"visual\"."`

**`app/ai/gemini_provider.py`, class `GeminiAIProvider`:**
- **`__init__(settings)`:**
  - `self.provider = "gemini"`, `self.model_id = settings.gemini_model`.
  - `self._client = genai.Client(api_key=settings.gemini_api_key.get_secret_value(), http_options=types.HttpOptions(timeout=settings.processing_provider_timeout_seconds * 1000))`
  - Also store the poll interval and the provider timeout seconds.
- **`check_model()`:** `self._client.models.get(model=self.model_id)`. If the returned model has non-empty `supported_actions` without `"generateContent"`, raise `ProviderError("AI_PROVIDER_UNAVAILABLE", "Configured model does not support generateContent.", False)`. Normalize errors.
- **`upload_file`:** `self._client.files.upload(file=path, config=types.UploadFileConfig(mime_type=mime_type, display_name=display_name))` → `ProviderFile` from `name`, `uri`, `mime_type`, `state.name` (or `str(state)`), `expiration_time`.
- **`wait_until_active(name, on_poll)`:**
  - Loop `files.get(name=name)` until `state == FileState.ACTIVE`, calling `on_poll()` and `time.sleep(poll_interval)` each iteration.
  - `FAILED` → `ProviderError("AI_FILE_PROCESSING_FAILED", …, False)`.
  - Total time over `processing_provider_timeout_seconds` → `ProviderError("PROCESSING_TIMEOUT", …, True)`.
  - `ClientError` code 404 → `ProviderError("AI_FILE_EXPIRED", …, True)`.
- **`extract_video`:**
  - Call `models.generate_content(model=self.model_id, contents=[types.Part.from_uri(file_uri=file.uri, mime_type=file.mime_type), build_prompt(...)], config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=VideoExtractionResult, temperature=0))`.
  - Parse with `VideoExtractionResult.model_validate_json(response.text or "")`. On `ValidationError`, `ValueError` or empty text → `ProviderError("AI_RESPONSE_INVALID", "Model output did not match the extraction schema.", True)`. The worker enforces the retry-once rule.
  - `usage = response.usage_metadata.model_dump(exclude_none=True, mode="json") if response.usage_metadata else None`.
  - If the installed SDK rejects the pydantic `response_schema` (it raises before any network call, verified with a fake client in tests), use `response_json_schema=VideoExtractionResult.model_json_schema()` instead.
- **`delete_file(name)`:** `files.delete(name=name)`; errors are normalized and the caller treats them as best-effort.
- **Error normalization, one private function `_normalize(exc) -> ProviderError`** used by every method:

  | Exception | Code | Retryable | Message / extra |
  |---|---|---|---|
  | `errors.ClientError` 429 | `AI_PROVIDER_RATE_LIMITED` | True | `retry_after_seconds` parsed from a `retryDelay` like `"30s"` in `exc.details` when present, else None |
  | `ClientError` 401/403 | `AI_PROVIDER_AUTH_FAILED` | False | |
  | `ClientError` 404 | `AI_FILE_EXPIRED` | True | |
  | Other `ClientError` | `PROCESSING_FAILED` | False | |
  | `errors.ServerError` | `AI_PROVIDER_UNAVAILABLE` | True | |
  | `httpx.TimeoutException` | `PROCESSING_TIMEOUT` | True | |
  | `httpx.TransportError` | `AI_PROVIDER_UNAVAILABLE` | True | |

  Messages are fixed, safe strings that never contain the key, the file path or the raw response.
- **No logging** of prompts, responses or the key.

**Tests:**
- **`tests/test_gemini_provider.py`:** monkeypatch `GeminiAIProvider._client` with a fake object exposing `files.upload/get/delete` and `models.get/generate_content`. Cover:
  - PROCESSING→ACTIVE polling calls `on_poll`
  - FAILED state
  - poll timeout (tiny timeout)
  - 404 → `AI_FILE_EXPIRED`
  - valid JSON parsed
  - malformed JSON, missing `action`, empty text and wrong top-level shape → `AI_RESPONSE_INVALID`
  - 429 with `retryDelay` → retryable with seconds
  - 401 → non-retryable `AI_PROVIDER_AUTH_FAILED`
  - `build_prompt` contains the duration and the no-audio sentence
  - `str(ProviderError)` never contains the API key
- **`tests/test_gemini_live.py` (C5.2):**
  - `pytest.mark.skipif` unless `TAKUMI_LIVE_GEMINI=1` and `GEMINI_API_KEY`, `GEMINI_MODEL` and `TAKUMI_LIVE_VIDEO` (path to a real MP4) are all set.
  - App settings: `ai_provider="gemini"`, `enable_media_upload=True`, `enable_media_processing=True`, `enable_live_extraction=True`, `enable_processing_worker=True`, key and model from env.
  - Flow: create a task, upload, process live, call `processing_worker.run_once` until the job is terminal, then assert `completed`, a non-null `draft_id`, `provider_file_name` recorded, and ≥1 knowledge unit from `GET /draft`.

### Step 8 — Processing jobs, worker and draft persistence (Wave 2, Pipeline agent)
**Entity, `app/models/entities.py` `ProcessingJob` (`processing_jobs`), `UniqueConstraint("task_id", "media_id", "mode", "request_id")`:**
- Identity and ownership:
  - `id` str PK
  - `task_id` FK tasks
  - `media_id` FK `media_assets.id`
  - `mode` str
  - `request_id` str
  - `requested_by` str
- State:
  - `status` str
  - `stage` str
  - `attempt_count` int, default 0
  - `next_attempt_at` dt | None
  - `lease_owner` str | None
  - `lease_expires_at` dt | None
- Provider and input:
  - `provider` str
  - `model_id` str
  - `prompt_version` str
  - `input_sha256` str
  - `provider_file_name` / `provider_file_uri` / `provider_file_state` str | None
  - `provider_uploaded_at` / `provider_expires_at` dt | None
- Results:
  - `extraction` JSON | None (validated `VideoExtractionResult` dump, the checkpoint)
  - `usage` JSON | None
  - `warnings` JSON list, default `[]`
  - `error_code` / `error_message` str | None
  - `result_draft_id` str | None
- Timestamps: `created_at`, `updated_at`, `started_at` / `completed_at` dt | None.

**Bump `SCHEMA_VERSION = 3`.** The Step 2 upgrade rule covers 1→3 and 2→3.

**Schemas, `app/models/schemas.py`:**
- `ProcessRequest(RequestModel)`: `media_id: str = Field(min_length=1, max_length=100)`, `mode: Literal["live", "demo"]`, `request_id: str = Field(min_length=1, max_length=100)` (use the existing request base that sets `extra="forbid"`).
- `JobError(code: str, message: str)`.
- `JobOut`: `job_id`, `task_id`, `media_id`, `mode`, `status: Literal["queued", "running", "completed", "failed"]`, `stage: Literal["uploaded", "preparing_media", "extracting", "detecting_gaps", "ready_for_review"]`, `progress_label`, `attempt_count`, `draft_id: str | None`, `error: JobError | None`, `warnings: list[str]`, `provider`, `model_id`, `prompt_version`, `created_at`, `updated_at`.
- `PROGRESS_LABELS`:

  | Stage | Label |
  |---|---|
  | `uploaded` | `"Queued"` |
  | `preparing_media` | `"Uploading recording to AI provider"` |
  | `extracting` | `"Extracting technical steps"` |
  | `detecting_gaps` | `"Detecting knowledge gaps"` |
  | `ready_for_review` | `"Draft extracted"` |

  Status `failed` always gets the label `"Processing failed"`.

**New `app/services/processing_service.py`:**
- **`create_job(session, settings, task_id, req, user) -> ProcessingJob`**, run in this order:
  1. `get_task` → 404 `TASK_NOT_FOUND`.
  2. The media must exist with `media.task_id == task_id`, else `AppError("MEDIA_NOT_FOUND", …, 404)`.
  3. Existing job with the same (task, media, mode, request_id) → return it (idempotent, even if terminal).
  4. `mode == "demo"` → `AppError("FIXTURE_NOT_AVAILABLE", "Demo mode cannot analyze uploaded recordings; use the seeded task_001 demo.", 422)`.
  5. Live mode not configured (`ai_provider != "gemini"` or not `enable_live_extraction`) → `AppError("AI_PROVIDER_UNAVAILABLE", "Live extraction is not configured.", 503, {"required": ["AI_PROVIDER=gemini", "ENABLE_LIVE_EXTRACTION=true", "GEMINI_API_KEY", "GEMINI_MODEL"]})`. The media is untouched.
  6. A `Draft` exists for the task → `AppError("DRAFT_ALREADY_EXISTS", "This task already has a draft; create a new task for a new recording.", 409, {"task_id": …})`.
  7. Another job for the task with status `queued` or `running` → `AppError("PROCESSING_ALREADY_RUNNING", …, 409, {"job_id": …})`.
  8. Insert with `id=new_id("job")`, `status="queued"`, `stage="uploaded"`, `provider="gemini"`, `model_id=settings.gemini_model`, `prompt_version=PROMPT_VERSION`, `input_sha256=media.sha256`, `requested_by=user.id`, then `flush()`.
- **`get_job(session, job_id) -> ProcessingJob`:** missing → `AppError("PROCESSING_JOB_NOT_FOUND", "Processing job not found.", 404)`.
- **`job_out(job) -> JobOut`.**

**Routes, `app/api/media.py`:**
- `POST /tasks/{task_id}/process` (expert/reviewer, `feature_disabled("ENABLE_MEDIA_PROCESSING", 5)` when off): `with session.begin(): create_job` → `JSONResponse(status_code=202, content=job_out(...).model_dump(mode="json"))`. Declare `status_code=202` and `response_model=JobOut` on the route. It never waits for extraction.
- `GET /jobs/{job_id}` (expert/reviewer, same flag) → `JobOut`.

**New `app/services/extraction_service.py`:**
- **`build_draft_content(result: VideoExtractionResult, media: MediaAsset, author_label: str) -> tuple[list[dict], list[dict], list[str]]`**, returning units, evidence rows and warnings. For step `i` (1-based):
  - Strip text fields; blank becomes `None`.
  - Blank action → warning `f"step {i}: empty action dropped"` and skip the step.
  - `problem = interval_problem(start, end, media.duration_ms)`:
    - If `problem` is set → warning `f"INVALID_EVIDENCE_INTERVAL step {i} ({start}-{end} ms): {problem}"`, and the unit gets **no** evidence (`evidence_ids=[]`, `field_evidence={}`).
    - Otherwise reuse the evidence id already created for an identical `(start, end)`. Else create the row: `id=new_id("ev")`, `type="video_segment"`, `author_id="ai_extraction"`, `author_label=author_label`, `content=f"[AI-extracted, unreviewed; source: {modality}] {evidence_description or action}"`, `media_id`, `start_ms`, `end_ms`, `source_label="real"`.
  - If `media.audio_codec is None` and modality ≠ `"visual"` → warning `f"step {i}: reports spoken content but the recording has no audio track"`.
  - Unit:
    - `KnowledgeUnit(id=new_id("ku"), action, cue, interpretation, decision, exception, evidence_ids=[ev] or [], field_evidence={f: [ev] for each non-null field incl. action} or {}, review_status="draft")`, validated with `KnowledgeUnit.model_validate` and then dumped (C5.8).
  - Append each `result.processing_warnings` entry as `f"model: {w}"`.
  - No units → raise `ProviderError("AI_RESPONSE_INVALID", "Extraction contained no usable steps.", True)`.
  - Finally call `validate_evidence_items(evidence_rows, task_id, media.duration_ms, media.id)` as a backstop.
- **`persist_extraction(session, job, media, units, evidence_rows, warnings) -> str`** returns the draft id. It is one transaction, owned by the worker. Steps:
  1. `Draft` exists for the task → raise `ProviderError("DRAFT_ALREADY_EXISTS", "A draft was created for this task while processing.", False)`.
  2. Insert the `Evidence` rows (`task_id`, `created_at`).
  3. Insert `Draft(id=new_id("draft"), revision=1, status="draft")` and `DraftRevision(revision=1, actor_id=job.requested_by, reason="extraction")`.
  4. Add clarifications: for each `detect_gaps(units)` candidate add `Clarification(id=new_id("clar"), task_id, draft_id, **candidate.model_dump(), status="pending", created_at=utcnow())`. This copies the 9-line pattern in `seed_service.seed_demo` lines 61–73; it isn't refactored because the seed must keep the fixed `clar_00N` ids.
  5. Set `task.status = "draft"`, `updated_at`.
  6. `flush()`.
  - The job completion update happens in the same transaction (Step 8 worker). Release rows are never touched.

**New `app/services/processing_worker.py`:**
- **`claim_next_job(sessionmaker, settings, worker_id) -> str | None`**, in one short transaction:
  - First, any `running` job with `lease_expires_at < now` and `attempt_count > processing_max_retries` → `failed`, `PROCESSING_TIMEOUT`, `"Processing lease expired too many times."`.
  - Then select the oldest (`created_at`) job where (`status == "queued"` and (`next_attempt_at` is null or ≤ now)) or (`status == "running"` and `lease_expires_at < now`).
  - Set `status="running"`, `lease_owner=worker_id`, `lease_expires_at=now+lease`, `attempt_count += 1`, `started_at` if null, `updated_at`. Return the id.
  - `BEGIN IMMEDIATE` makes select+update atomic.
- **`_update(sessionmaker, job_id, worker_id, **values) -> None`:** in its own short transaction, `UPDATE processing_jobs SET ..., updated_at=now, lease_expires_at=now+lease WHERE id=:id AND lease_owner=:worker AND status='running'`. Rowcount 0 → raise `LeaseLost` (module exception). This covers the job deleted by a reset or reclaimed elsewhere.
- **`run_once(sessionmaker, settings, extractor: VideoExtractor, worker_id: str) -> str | None`:**
  1. Claim. None → return None.
  2. Load a job snapshot and its media, then close the session.
  3. Resolve the path with `media_service.media_path` (missing → non-retryable `MEDIA_NOT_FOUND`).
  4. If `job.extraction` is null:
     - `_update(stage="preparing_media")`.
     - If `provider_file_name` is set, try `wait_until_active(name, heartbeat)`. On `ProviderError` code `AI_FILE_EXPIRED`, clear the `provider_file_*` fields and fall through to a fresh upload.
     - Fresh upload: `upload_file(path, media.mime_type, media.id)`, then `_update` `provider_file_name`/`uri`/`state`/`uploaded_at=now`/`expires_at`, then `wait_until_active`, then `_update(provider_file_state="ACTIVE")`.
     - `_update(stage="extracting")`, then `extract_video(file, TaskContext(...from task), media.duration_ms, media.audio_codec is not None)`, then `_update(extraction=result.model_dump(mode="json"), usage=…, model_id=extraction.model_id)`.
  5. `_update(stage="detecting_gaps")`.
  6. `build_draft_content(result, media, f"AI extraction ({model_id}, unreviewed)")`. `result` is the in-memory `VideoExtractionResult` from step 4, or `VideoExtractionResult.model_validate(job.extraction)` when the checkpoint skipped extraction.
  7. In one transaction:
     - First, `draft_id = persist_extraction(...)`.
     - Then, in the same transaction, a lease-guarded `UPDATE` sets `status="completed"`, `stage="ready_for_review"`, `result_draft_id=draft_id`, `warnings`, `completed_at`, `lease_owner=None`, `error_code=None`, `error_message=None`. Rowcount 0 → raise `LeaseLost`, which rolls back the whole transaction including the draft.
     - On `IntegrityError`/`SQLAlchemyError` → `ProviderError("DRAFT_PERSISTENCE_FAILED", …, False)`.
  8. Best-effort `extractor.delete_file(provider_file_name)`. On success, run a plain `UPDATE processing_jobs SET provider_file_state='DELETED' WHERE id=:id` in its own short transaction (no lease guard, because the job is already `completed`). On a `ProviderError`, log `error_code` only and leave the state unchanged; the job stays completed.
  9. `heartbeat` = a closure calling `_update()` with no values, which extends the lease.
- **Failure handling** for `ProviderError e` (`AppError` is mapped to `ProviderError(e.code, e.message, False)`; any other `Exception` is logged with `logger.exception` and treated as `ProviderError("PROCESSING_FAILED", "Unexpected processing error.", False)`):
  - `e.code == "AI_RESPONSE_INVALID"` while the job's previous `error_code == "AI_RESPONSE_INVALID"` → not retryable (retry once).
  - If retryable and `attempt_count <= processing_max_retries`: `status="queued"`, `lease_owner=None`, `next_attempt_at = now + (e.retry_after_seconds or min(60, processing_poll_interval_seconds * 2 ** attempt_count))`, and set `error_code`/`error_message` (the last error, visible while queued).
  - Else `status="failed"` with the error fields set. The stage stays where it failed.
  - Use the guarded `UPDATE`; on `LeaseLost`, log and return.
  - Media, `extraction` and `provider_file_*` are never deleted on failure.
- **`LeaseLost`:** log `job_id` + `"lease lost"` and return the job id without writing.
- **Structured log, one `logger.info` per stage end and terminal state** (logger `takumi.worker`), formatted as `key=value` pairs:
  - `job_id`, `task_id`, `media_id`, `provider`, `model_id`, `prompt_version`, `input_sha256`
  - `stage`, `status`, `attempt_count`, `stage_duration_ms`, `total_duration_ms`, `error_code`
  - Never prompts, responses, keys, paths or tokens.
- **`run_forever(settings) -> int`:**
  1. Return 2 with `print(..., file=sys.stderr)` when `not settings.enable_processing_worker` (`"ENABLE_PROCESSING_WORKER is false"`) or `settings.ai_provider != "gemini"` (`"Worker requires AI_PROVIDER=gemini"`).
  2. `build_engine` + `init_db` + `sessionmaker(engine, expire_on_commit=False)`.
  3. `extractor = get_video_extractor(settings)`; `extractor.check_model()`. A `ProviderError` → print `code: message` and return 2.
  4. `worker_id = f"worker_{os.getpid()}_{uuid4().hex[:6]}"`.
  5. Loop `run_once`; sleep `processing_poll_interval_seconds` when it returns None. `KeyboardInterrupt` → return 0; the lease expires and the job is recovered.
- **New `scripts/run_worker.py`:** `main()` → `sys.exit(run_forever(get_settings()))`, with `sys.path` setup copied from the other scripts.

**Reset:** `seed_service.reset_demo` also deletes `ProcessingJob` rows for `FIXTURE_TASK_ID` (before `MediaAsset`).

**Tests, new `tests/test_processing.py`** (`FakeExtractor` implements `VideoExtractor` with scripted results/exceptions and records calls):
- **App setup:** `make_client(ai_provider="gemini", gemini_api_key="test-key", gemini_model="fake-model", enable_media_upload=True, enable_media_streaming=True, enable_media_processing=True, enable_live_extraction=True, enable_processing_worker=True)`.
- **Uploads:** reuse the `sample_videos` fixture; move it from `tests/test_media.py` into `tests/conftest.py` so both files use it.
- **Task:** create a new task via `POST /tasks` (task_001 already has a draft).
- **Cases:**

  | # | Case | Expect |
  |---|---|---|
  | C5.1 | Valid process → `run_once` | 202 `{status: queued, stage: uploaded}`; job `completed`/`ready_for_review`; `draft_id` set; `GET /tasks/{id}/draft` has the units with `review_status == "draft"` and `field_evidence` → `video_segment` evidence with `media_id` and the interval; clarifications pending (≤3); fake `delete_file` called |
  | C5.3 | Malformed/missing/empty output via `extract_video` raising `AI_RESPONSE_INVALID` twice; invalid interval (`end_ms > duration`) | First `run_once` → queued with `error_code`; second → `failed` with no draft. Invalid interval → completed, the unit has empty `field_evidence`, the warning contains `INVALID_EVIDENCE_INTERVAL`, and `POST /publish` → 409 `PUBLICATION_BLOCKED` |
  | C5.4 | Timeout raising `PROCESSING_TIMEOUT` (retryable) | After each attempt: queued, `attempt_count` increments; after `processing_max_retries + 1` attempts → `failed`; the media file still exists; `draft_id` stays null |
  | C5.5 | One `AI_PROVIDER_UNAVAILABLE`, then success | Same `job_id` completes; exactly one `Draft` for the task; the second attempt does not re-upload when the first failed in `extract_video` (fake records 1 upload) |
  | C5.6 | Crash recovery | Claim a job, then set `lease_expires_at` in the past; a new `run_once` with another `worker_id` reclaims and completes it; the old worker's `_update` raises `LeaseLost` |
  | C5.7 | Duplicate request | Same `request_id` twice → same `job_id`, one row. A different `request_id` while queued → 409 `PROCESSING_ALREADY_RUNNING`. After completion, a new `request_id` → 409 `DRAFT_ALREADY_EXISTS` |
  | C5.9 | Full V1 integration | Fake steps reuse fixture wording so the deterministic matcher answers, e.g. action `"Inspect the bearing housing"` with `cue` set and `interpretation` null. Then: respond to the pending clarification for that unit with `knowledge_update` setting `interpretation` → publish (reviewer) → training pack contains the `expert_response` evidence → apprentice asks `"Why do you inspect the bearing housing?"` → `answered`, citing that evidence → asks a torque question → `insufficient_evidence`. If the matcher needs other wording, change the fake step text, not `qa_matching` |
  | C5.11 | Fixture regression | Default `client` with no Gemini settings: `run_flow(client)` from `scripts/demo_flow.py` passes. Process with `mode="live"` → 503 `AI_PROVIDER_UNAVAILABLE`; with `mode="demo"` → 422 `FIXTURE_NOT_AVAILABLE`. The media still streams |
  | — | Flags | Processing off → 501 on process and job routes; `GET /jobs/unknown` → 404 `PROCESSING_JOB_NOT_FOUND`; apprentice → 403 |

### Step 9 — Commit C5 (orchestrator)
1. Gates: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`.
2. Smoke (Verification §2).
3. Commit `feat(backend): Gemini video extraction, durable processing jobs and worker (C5)`.

### Step 10 — Scripts, contracts and docs (Wave 3, HandoffV2 agent)
- **New `scripts/video_flow.py`:**
  - Args: `--base-url` (default `http://localhost:8000`), `--video PATH` (required), `--mode live|demo` (default `live`), `--timeout 600`.
  - Uses `httpx` the same way as `demo_flow.main`.
  - Flow:
    1. Log in as expert and create a task (`title` from the file stem, `equipment "Demonstration bench"`, `language "en"`).
    2. Upload the file → print `media_id`.
    3. `GET /media/{id}` → print `duration_ms`.
    4. Range GET `bytes=0-1023` → assert 206.
    5. `POST /process` with `request_id=f"video_flow_{uuid4().hex[:8]}"`.
    6. Poll `GET /jobs/{id}` every 2 s, printing each new `stage`/`status` until terminal.
    7. On `completed`, `GET /tasks/{id}/draft` and print the unit count, then per unit: `id`, `action` and the evidence interval.
  - Exit 1 on `failed`, printing the job error.
  - Exit 1 on a non-2xx response, printing the error envelope (e.g. the 503 config error).
- **`scripts/export_contracts.py`:** add `MediaOut → contracts/schemas/media.json` and `JobOut → contracts/schemas/processing-job.json` next to the existing four schema exports, following their path convention. Leave the 16 examples unchanged.
- **`.env.example`:** add `MEDIA_STORAGE_DIR=./data/media`, `PROCESSING_POLL_INTERVAL_SECONDS=2`, `PROCESSING_JOB_LEASE_SECONDS=180`, `PROCESSING_PROVIDER_TIMEOUT_SECONDS=120`. Keep `GEMINI_API_KEY=` and `GEMINI_MODEL=` empty, with a comment: "required when AI_PROVIDER=gemini; must be a video-capable model available to your key (not verified by this repo)". Add a commented live-mode block showing the flag set.
- **`README.md`:** new sections:
  - "Media (C4)"
  - "Live extraction (C5)": flags, `uv run uvicorn app.main:app --port 8000 --no-access-log` (the access log would record playback tokens), `uv run python scripts/run_worker.py`, `uv run python scripts/video_flow.py --video demo.mp4`
  - "Verification status": mocked tests verified; live Gemini **unverified** (no key); the opt-in command `TAKUMI_LIVE_GEMINI=1 TAKUMI_LIVE_VIDEO=… uv run pytest tests/test_gemini_live.py`
  - Update the Feature flags and Limitations sections.
- **`docs/INTEGRATION_HANDOFF.md`:**
  - Endpoint table: upload, `GET /media/{id}`, stream, process, jobs, with roles and statuses.
  - Request/response examples from the schemas.
  - Playback instructions: `<video src={API_ORIGIN + playback_url}>`; refresh by re-fetching `GET /media/{id}` after `playback_expires_at`; seek with `video.currentTime = start_ms / 1000`.
  - Error table additions.
  - The backward-compatibility statement (no existing response field changed).
  - Deviations: task detail has no media/job fields; process returns `JobOut` (a superset); `DRAFT_ALREADY_EXISTS`; MP4 only; 416 body is plain text from Starlette.
  - Mark Gemini live as unverified.
- **New `docs/V2_CHECKPOINTS.md`:** C4 and C5 reports in the V2 prompt §27 format, filled from actual gate and smoke output that the orchestrator passes in.
- **New `backend/V2_IMPLEMENTATION_PLAN.md`:** a condensed version of this plan: decisions, schema v3, job state machine, retry table.
- **`docs/KNOWN_LIMITATIONS.md`:**
  - Replace the "No Media or ProcessingJob table" line.
  - Add: single worker; MP4 h264/av1 only; Gemini timestamps are approximate and not validated against frames; no decode check beyond ffprobe metadata; the playback token is reusable for 10 min; chunked uploads without `Content-Length` are bounded only after spooling; live path unverified; Q&A and gaps are deterministic even with `AI_PROVIDER=gemini`.
- **`docs/CHECKPOINTS.md`:** one line pointing to `V2_CHECKPOINTS.md`.
- **Root `AGENTS.md`:**
  - Add the worker and video_flow commands, and `--no-access-log`.
  - Add rules: no Gemini calls inside DB transactions; worker writes go through the lease-guarded `_update`; AI output is always a draft and never published by code; processing a task with an existing draft is rejected.
  - Update the "Gemini reserved" line.

### Step 11 — Final (orchestrator)
1. Run the gates and the full Verification below.
2. Run `uv run python scripts/export_contracts.py`, then `git checkout -- contracts/api-examples` (example ids are random; only `openapi.json` and the schemas change).
3. Commit `docs(backend): V2 media and extraction handoff`.
4. Run `git push origin himanish`.
5. Report in V2 §27 format.

## Execution (subagents)
1. **Step 0:** the orchestrator.
2. **Wave 1:** one `task` agent, **MediaC4**, does Steps 1–4. The orchestrator then does Step 5.
3. **Step 6:** the orchestrator writes the shared contract code.
4. **Wave 2:** two parallel `task` agents.
   - **GeminiAdapter** (Step 7) owns `app/ai/gemini_provider.py`, `app/ai/prompts/`, `tests/test_gemini_provider.py` and `tests/test_gemini_live.py`.
   - **Pipeline** (Step 8) owns the entities, schemas, `processing_service`, `extraction_service`, `processing_worker`, `api/media.py`, `scripts/run_worker.py`, `seed_service`, `tests/test_processing.py` and the `conftest` move.
   - Neither edits the other's files or `app/ai/schemas.py` / `app/ai/base.py`. Contract change requests go to the orchestrator.
   - The orchestrator then does Step 9.
5. **Wave 3:** one `task` agent, **HandoffV2**, does Step 10. The orchestrator then does Step 11.
6. **Subagent context:** every agent gets the Ground rules, its step text verbatim and the user decisions table.

## Critical files & anchors
- `backend/app/config.py` `validate_capabilities` (lines ~48–78): reserved-flag lists and messages tested in `tests/test_config.py:20-31`.
- `backend/app/database.py` `init_db` (lines 53–75): version guard and hardcoded `expected 1` text.
- `backend/app/core/logging.py:19-27`: the global body limit that blocks 100 MB uploads.
- `backend/app/api/media.py`: four 501 stubs behind a router-level `get_current_user` dependency, which must move per-route for the token-based stream.
- `backend/app/services/evidence_service.py:24-46`: V1 media rejection that the fixture tests rely on.

## Verification
All commands run from `backend/`. Python HTTP checks use `eval` with `urllib`, because `curl` is hook-blocked.

1. **Gates:**
   - `uv run pytest -q`: 88 baseline plus new tests, all pass. Only `test_gemini_live.py` is skipped and reported as "live Gemini unverified".
   - `uv run ruff check .`
   - `uv run ruff format --check .`
2. **C4/C5 smoke against a real server:**
   - Generate `/tmp/takumi_demo.mp4` with the C4 ffmpeg command, 5 s.
   - Start `ENABLE_MEDIA_UPLOAD=true ENABLE_MEDIA_STREAMING=true ENABLE_MEDIA_PROCESSING=true DATABASE_URL=sqlite:////tmp/takumi_v2.db MEDIA_STORAGE_DIR=/tmp/takumi_media uv run uvicorn app.main:app --port 8000 --no-access-log`.
   - `uv run python scripts/video_flow.py --video /tmp/takumi_demo.mp4`:
     - expect the upload to print a `media_id` and duration of about 5000 ms, and the range check to pass;
     - then expect a 503 `AI_PROVIDER_UNAVAILABLE` printed with the `required` list and exit 1 (live is not configured);
     - `GET /media/{id}/stream` still returns 200 afterwards (media preserved).
   - Upload a text file renamed to `.mp4` → 422 `INVALID_MEDIA`.
3. **Worker preflight:**
   - `ENABLE_MEDIA_UPLOAD=true ENABLE_MEDIA_PROCESSING=true ENABLE_PROCESSING_WORKER=true AI_PROVIDER=gemini GEMINI_API_KEY=invalid GEMINI_MODEL=gemini-invalid uv run python scripts/run_worker.py` → exit 2, printing an `AI_PROVIDER_AUTH_FAILED` or `PROCESSING_FAILED`/`AI_FILE_EXPIRED`-style normalized code with no key echoed.
   - Without `ENABLE_PROCESSING_WORKER` → exit 2 `ENABLE_PROCESSING_WORKER is false`.
4. **Fixture regression:**
   - Default `.env` server: `uv run python scripts/demo_flow.py --base-url http://localhost:8000` → 16 OK.
   - `uv run python scripts/reset_demo.py --state fresh --yes` succeeds.
   - Existing `data/takumi.db` (schema v1) starts without error and reports `schema_version` 3 in `/api/v1/health`.
5. **Live Gemini:** not run (no key). Report it as unverified, with the exact opt-in command.

## Assumptions & contingencies
- **Playback token reuse:** the playback URL token can be replayed within 10 minutes, because video seeking needs repeated range requests. This is documented, not mitigated.
- **No `supported_actions`:** if the installed `google-genai` `Model` has no `supported_actions` attribute, `check_model` only checks that `models.get` succeeds.
- **`Part.from_uri` signature:** if `types.Part.from_uri` has a different signature in the installed SDK, pass the `File` object returned by `files.get` directly in `contents`. Verify with a fake client in tests.
- **416 response body:** if Starlette's `FileResponse` returns a 416 body that isn't JSON, keep it and document it; don't wrap it.
- **Unsatisfiable range status:** if Starlette returns 200 instead of 416 for an unsatisfiable range in the installed version (1.9.0), the test asserts the actual behaviour and the handoff documents it. Do not hand-roll range parsing.
- **Missing ffmpeg/ffprobe:** if `ffmpeg`/`ffprobe` is missing on another machine, the media and processing tests skip and upload returns 503 `FFPROBE_UNAVAILABLE`.
