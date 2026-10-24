# Integration handoff

Canonical contract: `../../markdowns/hackathon/openapi/API.doc.md`. Generated backend contract: `../contracts/openapi.json`. All paths below use `/api/v1`. Requests use JSON except multipart uploads; bearer tokens carry server-verified roles. Unknown mutation fields are rejected. Errors use `{"error":{"code":"…","message":"…","details":null}}` (details may be an object).

## Endpoints

Roles: **all** = expert, reviewer, apprentice; **editors** = expert, reviewer. Every authenticated endpoint can return 401/403; malformed input returns 422 `VALIDATION_ERROR`. Examples refer to `../contracts/api-examples/`. Where no captured request exists, the example column gives a request shape; response schemas are in OpenAPI.

| Method and path | Purpose | Role | Request → response | Example | Other errors | Flag |
|---|---|---|---|---|---|---|
| GET /health | DB and feature health | public | — → HealthOut | GET /api/v1/health | 503 degraded HealthOut | — |
| POST /auth/demo-login | Demo bearer token | public | DemoLoginRequest → DemoLoginOut | `{"demo_user":"reviewer"}` | FEATURE_DISABLED | ENABLE_DEMO_AUTH |
| GET /tasks | Visible tasks | all | — → TaskListOut | GET /api/v1/tasks | — | — |
| POST /tasks | Create real-source task | editors | TaskCreate → TaskOut (201) | `{"title":"Inspection","equipment":"Bench"}` | — | — |
| GET /tasks/{task_id} | Task metadata | all | — → TaskOut | GET /api/v1/tasks/task_001 | TASK_NOT_FOUND | — |
| GET /tasks/{task_id}/draft | Editable draft and gaps | editors | — → DraftOut | 02-read-draft.json | DRAFT_NOT_FOUND | — |
| PATCH /tasks/{task_id}/draft | Field corrections | editors | DraftPatch → DraftPatchOut | `{"expected_revision":1,"changes":[{"knowledge_unit_id":"ku_001","fields":{"cue":null}}]}` | REVISION_CONFLICT, KNOWLEDGE_UNIT_NOT_FOUND | — |
| POST /clarifications/{clarification_id}/respond | Expert answer and evidence | editors | ClarificationRespond → ClarificationRespondOut | 04-answer-clarification.json | CLARIFICATION_NOT_FOUND, INVALID_STATE_TRANSITION, INVALID_KNOWLEDGE_UPDATE, REVISION_CONFLICT | — |
| GET /evidence/{evidence_id} | Resolve source | all | — → EvidenceItemOut | 05-read-evidence.json | EVIDENCE_NOT_FOUND | — |
| POST /tasks/{task_id}/publish | Approve snapshot | reviewer | PublishRequest → PublishOut (201; retry 200) | 07-publish.json | TASK_NOT_FOUND, DRAFT_NOT_FOUND, REVISION_CONFLICT, PUBLICATION_BLOCKED | — |
| GET /tasks/{task_id}/release | Active release | all | — → ReleaseOut | 08-read-release.json | NO_ACTIVE_RELEASE | — |
| GET /releases/{release_id} | Specific immutable release | all | — → ReleaseOut | GET /api/v1/releases/release_001 | RELEASE_NOT_FOUND | — |
| GET /releases/{release_id}/training-pack | Simulation pack | all | — → TrainingPack | 09-training-pack.json | RELEASE_NOT_FOUND, INTERNAL_ERROR, FEATURE_DISABLED | ENABLE_TRAINING_PACK_EXPORT |
| POST /tasks/{task_id}/ask | Grounded explanation | all | AskRequest → AskOut | 10-ask-grounded.json; 12-ask-unsupported-spec.json | NO_ACTIVE_RELEASE, AI_PROVIDER_UNAVAILABLE, FEATURE_DISABLED | ENABLE_GROUNDED_QA |
| POST /demo/reset | Replace fixture task only | reviewer | DemoResetRequest → DemoResetOut | 01-reset-fresh.json | CONFIRMATION_REQUIRED, RESET_SCOPE_UNAVAILABLE, FEATURE_DISABLED | DEMO_MODE and ENABLE_DEMO_RESET |
| POST /tasks/{task_id}/media | Upload validated MP4 | editors | multipart `file` → MediaOut (201) | See media workflow | TASK_NOT_FOUND, INVALID_MEDIA, MEDIA_TOO_LARGE, MEDIA_TOO_LONG, FFPROBE_UNAVAILABLE | ENABLE_MEDIA_UPLOAD |
| GET /media/{media_id} | Metadata and signed playback URL | all; apprentice release visibility | — → MediaOut (200) | GET /api/v1/media/media_001 | MEDIA_NOT_FOUND | ENABLE_MEDIA_STREAMING |
| GET /media/{media_id}/stream | Private playback | bearer or media-scoped playback token; same visibility | — → bytes (200/206) | `Range: bytes=0-1023` | MEDIA_NOT_FOUND, 416 unsatisfiable range | ENABLE_MEDIA_STREAMING |
| POST /tasks/{task_id}/process | Queue extraction | editors | ProcessRequest → JobOut (202) | See media workflow | MEDIA_NOT_FOUND, MEDIA_HAS_NO_AUDIO, FIXTURE_NOT_AVAILABLE, AI_PROVIDER_UNAVAILABLE, DRAFT_ALREADY_EXISTS, PROCESSING_ALREADY_RUNNING | ENABLE_MEDIA_PROCESSING |
| GET /jobs/{job_id} | Poll extraction | editors | — → JobOut (200) | GET /api/v1/jobs/job_001 | PROCESSING_JOB_NOT_FOUND | ENABLE_MEDIA_PROCESSING |

Disabled media/processing flags return 501 `FEATURE_DISABLED`. PATCH/PUT/DELETE on release resources return 405 `METHOD_NOT_ALLOWED`; see 14-reject-release-edit.json. Body-size middleware can return 413 for any request.

## Authentication

```sh
curl -X POST http://localhost:8000/api/v1/auth/demo-login \
  -H 'Content-Type: application/json' -d '{"demo_user":"reviewer"}'
curl http://localhost:8000/api/v1/tasks/task_001/release \
  -H 'Authorization: Bearer <access_token>'
```

The curl snippets show request shapes, not extra executed checks. Use returned `access_token` and `expires_at`; token type is bearer. Identities: `expert_001`, `reviewer_001`, `apprentice_001`, with display names Demo Expert/Reviewer/Apprentice. Never send X-Role as authorization. Keep tokens out of logs. Unless an explicit secret is set, restart invalidates tokens.

## Studio workflow

1. List/get tasks or create a task. Creation alone does not extract knowledge or create a draft; use the media workflow below for new recordings.
2. Read seeded draft and pending clarifications. Draft fields include revision, evidence IDs and per-field evidence.
3. PATCH content with `expected_revision`, or respond with `expected_draft_revision`. Null clears an optional content field to unknown; action cannot be null. Revision conflicts require a fresh read.
4. Clarification disposition is answered, premise_rejected, unobservable or deferred. An answered response requires text; only answered responses may update knowledge. Rejected/deferred dispositions preserve draft content and revision.
5. Reviewer publishes current revision. Publishing approves every unit; there is no separate per-unit approval endpoint. Publication blocks unsupported populated fields or cross-task/missing evidence, but allows null unknown fields.
6. Read release/evidence. Apprentices never read drafts; unpublished tasks and evidence are hidden from them. Apprentice evidence must appear in a release snapshot for that task.

Baseline startup already contains `release_001`. Before a live expert demo, reviewer sends:
```json
{"scope":"full_demo","confirm":"RESET_DEMO_DATA","state":"fresh"}
```
to `POST /api/v1/demo/reset`. This deletes and recreates only task_001 and its records, in one transaction. User tasks survive. `approved_baseline` uses the actual clarification and publication services; its ev_002 source stays illustrative. A manually entered demonstration answer is recorded as real user input even when the text is labelled illustrative.

## Media and extraction workflow (C4/C5)

**Successful live Gemini extraction remains unverified (no key available).** Media streaming and mocked extraction tests are verified; see [V2_CHECKPOINTS.md](V2_CHECKPOINTS.md).

1. Create a task (`POST /tasks`); retain `id`. A task with an existing draft cannot process a new recording.
2. Upload MP4 as multipart field `file`; retain `media_id`.
3. Read `GET /media/{media_id}` to obtain metadata and a signed playback URL.
4. Submit processing and retain `job_id`. Poll `GET /jobs/{job_id}` until `completed` or `failed`.
5. On completion, read `GET /tasks/{task_id}/draft`; continue the existing clarification/reviewer-publication workflow.

Task detail deliberately has no media/job fields. Track both IDs from responses.
Upload accepts MP4 (not QuickTime) with h264/av1 video, optional audio, up to the configured size/duration.
These examples show schema shapes, not captured live extraction results. Placeholder IDs, hashes, model names and timestamps are illustrative.

Multipart request: `POST /tasks/task_example/media`, field `file=@demo.mp4`.
`MediaOut` (201 upload; 200 metadata):
```json
{
  "media_id": "media_example",
  "task_id": "task_example",
  "filename": "demo.mp4",
  "status": "uploaded",
  "duration_ms": 5000,
  "mime_type": "video/mp4",
  "size_bytes": 66281,
  "sha256": "<64-character SHA-256>",
  "video_codec": "h264",
  "audio_codec": "aac",
  "has_audio": true,
  "width": 320,
  "height": 240,
  "created_at": "2026-10-24T00:00:00Z",
  "playback_url": "/api/v1/media/media_example/stream?token=<signed-token>",
  "playback_expires_at": "2026-10-24T00:10:00Z"
}
```

Process request (`POST /tasks/task_example/process`):
```json
{"media_id":"media_example","mode":"live","request_id":"frontend_unique_request_1"}
```
`JobOut` (202 process; 200 poll):
```json
{
  "job_id": "job_example",
  "task_id": "task_example",
  "media_id": "media_example",
  "mode": "live",
  "status": "queued",
  "stage": "uploaded",
  "progress_label": "Queued",
  "attempt_count": 0,
  "draft_id": null,
  "error": null,
  "warnings": [],
  "provider": "gemini",
  "model_id": "<configured GEMINI_MODEL>",
  "prompt_version": "video_extraction_v1",
  "created_at": "2026-10-24T00:00:00Z",
  "updated_at": "2026-10-24T00:00:00Z"
}
```
With Ollama, `provider` is `"ollama"`, `model_id` is the configured `OLLAMA_MODEL`, and `prompt_version` is `"transcript_extraction_v1"`. Only narration supports extraction; visual-only knowledge is not captured. Steps use `source_modality="spoken"` and detected language uses whisper's language name (for example, `english`).
With OpenRouter, `provider` is `"openrouter"`, `model_id` is the configured `OPENROUTER_MODEL`, and extraction uses the same transcript prompt and local whisper.cpp stage. Only the transcript is sent to OpenRouter; the recording itself stays on the backend/LAN.

States: `queued` → `running` → `completed`/`failed`; retryable failures return to `queued`.
Stages: `uploaded` → `preparing_media` → `extracting` → `detecting_gaps` → `ready_for_review`.
Display `progress_label`; `preparing_media` shows `Preparing recording for AI analysis`, and failed jobs always show `Processing failed`. Errors have `{code,message}` and may remain visible while a retry is queued.
On completion, `draft_id` is set; warnings may include invalid intervals. AI output is unreviewed, never auto-published.
Invalid intervals retain the unit without evidence and block publication until supported expert corrections.
Repeating the same task/media/mode/request_id returns the same job, including terminal jobs.
A different request while a task is queued/running returns 409; a task with a draft returns 409 `DRAFT_ALREADY_EXISTS`.
`mode=demo` rejects uploaded recordings with 422; it does not substitute fixture content.
Unconfigured live processing returns 503 with `details.required` listing `AI_PROVIDER=gemini`, `ENABLE_LIVE_EXTRACTION=true`, `GEMINI_API_KEY`, `GEMINI_MODEL`. Media is preserved.
That legacy required-settings list is unchanged for the alternatives. Ollama startup requires `OLLAMA_BASE_URL`, `OLLAMA_MODEL` and `WHISPER_BASE_URL`; OpenRouter requires `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` and `WHISPER_BASE_URL`, plus the shared live-extraction/media-processing flags.
With Ollama, recordings without an audio track return 422 `MEDIA_HAS_NO_AUDIO`: `Transcript-based extraction needs a recording with narration audio.` A transcript containing only non-speech markers fails the job with non-retryable `NO_SPEECH_DETECTED`.

### Playback and evidence

Use `<video src={API_ORIGIN + playback_url} controls />`; no bearer header is needed for that URL.
Refresh by re-fetching `GET /media/{media_id}` after `playback_expires_at`.
Seek evidence with `video.currentTime = start_ms / 1000`.
Bearer auth also works on `/stream`; playback tokens cannot authenticate other API routes.
Tokens are reusable for 10 minutes, bound to one media ID. Never log them; start uvicorn with `--no-access-log`.
Apprentices receive 404 until the media appears in any release snapshot for that task; streaming rechecks visibility.
Range responses expose `Content-Range`, `Accept-Ranges`, `Content-Length` through CORS.
An unsatisfiable range returns Starlette's 416, not an error envelope. Its body is plain text/empty; observed smoke body was empty.
Resolve `knowledge_units[].evidence_ids` through `GET /evidence/{id}` for `media_id`, `start_ms`, `end_ms`.

### Code path for review

`app/api/media.py` handles upload/process/poll/stream routes.
`app/services/media_service.py` validates, stores and signs playback.
`app/services/processing_service.py` creates idempotent jobs.
`app/services/processing_worker.py` claims leases, calls Gemini, Ollama or OpenRouter outside transactions and atomically completes drafts.
`app/ai/gemini_provider.py` uses the Files API and structured generation.
`app/ai/prompts/video_extraction_v1.py` supplies the versioned prompt.
`app/ai/ollama_provider.py` extracts WAV with ffmpeg, transcribes through whisper-server and requests structured output from Ollama; `app/ai/prompts/transcript_extraction_v1.py` supplies its narration-only prompt.
`app/ai/openrouter_provider.py` reuses the local whisper.cpp transcript stage and requests strict JSON-schema output from OpenRouter.
`app/services/extraction_service.py` validates evidence and persists the draft/clarifications.
Q&A and gap detection stay deterministic with `AI_PROVIDER=gemini`, `ollama` or `openrouter`.

## Simulation workflow

Read `GET /tasks/{id}` for `active_release_id`, then fetch that release's training pack. Pin `release_id` for a scenario; check authored required IDs against `knowledge_units[].id` locally. Fetch `/evidence/{id}` for sources. Ask `/tasks/{id}/ask` for feedback explanations; the server resolves the current active release, so inspect returned `release_id` if a scenario is pinned to an older version. Q&A never reads unapproved draft text. Claims carry `knowledge_unit_id`, field and evidence IDs. `insufficient_evidence` is expected for missing specs; `needs_context` requests a more specific question. No SQLite queries are needed by clients.

## Identifiers and immutability

Fixture task/draft/KU/clarification/evidence/release IDs are stable across demo resets, but resets replace those records and invalidate old nonfixture release IDs for task_001. Other new IDs use `<prefix>_<12 hex>`. `task_id` identifies the lifecycle; `draft_id` identifies mutable versioned work; `clarification_id` identifies a gap response; `knowledge_unit_id` identifies a unit; `evidence_id` identifies provenance; `release_id` identifies an immutable snapshot. Release KU/evidence IDs and snapshots remain stable after later draft edits. Release status alone is derived from the task's current active pointer, so an older release becomes superseded. Preserve field names, provenance and approved-release immutability when integrating.

## Stable error codes

| Code | HTTP |
|---|---|
| TASK_NOT_FOUND | 404 |
| DRAFT_NOT_FOUND | 404 |
| CLARIFICATION_NOT_FOUND | 404 |
| RELEASE_NOT_FOUND | 404 |
| EVIDENCE_NOT_FOUND | 404 |
| NO_ACTIVE_RELEASE | 404 |
| KNOWLEDGE_UNIT_NOT_FOUND | 422 |
| INVALID_KNOWLEDGE_UPDATE | 422 |
| INVALID_EVIDENCE | 422 |
| CONFIRMATION_REQUIRED | 422 |
| FIXTURE_NOT_AVAILABLE | 422 |
| VALIDATION_ERROR | 422 |
| REVISION_CONFLICT | 409 |
| INVALID_STATE_TRANSITION | 409 |
| PUBLICATION_BLOCKED | 409 |
| UNAUTHENTICATED | 401 |
| FORBIDDEN | 403 |
| FEATURE_DISABLED | 501 |
| RESET_SCOPE_UNAVAILABLE | 400 |
| PAYLOAD_TOO_LARGE | 413 |
| AI_PROVIDER_UNAVAILABLE | 503 |
| METHOD_NOT_ALLOWED | 405 |
| NOT_FOUND | 404 |
| INTERNAL_ERROR | 500 |
| MEDIA_NOT_FOUND | 404 |
| PROCESSING_JOB_NOT_FOUND | 404 |
| INVALID_MEDIA, MEDIA_TOO_LONG | 422 |
| MEDIA_HAS_NO_AUDIO | 422 (Ollama process request) |
| MEDIA_TOO_LARGE | 413 |
| FFPROBE_UNAVAILABLE | 503 |
| DRAFT_ALREADY_EXISTS, PROCESSING_ALREADY_RUNNING | 409 |

Worker failures appear in `JobOut.error` within a 200 polling response, not as polling HTTP failures:
`AI_PROVIDER_RATE_LIMITED`, `AI_PROVIDER_AUTH_FAILED`, `AI_FILE_EXPIRED`, `AI_PROVIDER_UNAVAILABLE`,
`AI_FILE_PROCESSING_FAILED`, `PROCESSING_TIMEOUT`, `AI_RESPONSE_INVALID`, `PROCESSING_FAILED`,
`DRAFT_PERSISTENCE_FAILED`, `DRAFT_ALREADY_EXISTS`, `MEDIA_NOT_FOUND`, `NO_SPEECH_DETECTED` (non-retryable).

## Compatibility notes versus API.doc.md

- Additive revision, provenance, source-label and identifier fields support versioning and source resolution.
- Release `status` is derived, not mutable stored state.
- Retrying publication of the unchanged current revision returns 200 and the same release, not a second 201 release.
- `/demo/reset` adds `state`; `attempts` returns 400 because the scenario engine owns learner attempts.
- Adds `GET /releases/{id}` and `GET /releases/{id}/training-pack`.
- C4/C5 implement media/process/jobs/stream behind disabled-by-default flags. `GET /media/{id}` is additive; processing returns the full `JobOut` superset with status/stage/progress, provenance, warnings and timestamps.
- No per-unit review step: publish = approval for all units. Draft `review_status` stays `draft`; only release snapshots are `approved`.
- New server databases auto-seed `approved_baseline` (`release_001`). Reset to `fresh` with the confirmed request above before a live expert demo.
- Scenario/attempt/viva/report routes are not served here. Teammates may mount routers in `app/main.py` and reuse `get_current_user`/`require_roles`.
- Ignore conflicting `markdowns/hackathon/openapi/*.openapi.json`: `/studio/*` prefixes, flat errors, `learner` role and `Idempotency-Key` convention do not govern this backend. API.doc.md wins. Generated source files were not edited.
- `GET /tasks/{id}` still omits media/processing fields; frontend retains IDs from upload/process responses.
- Existing `DraftOut`, `EvidenceItemOut`, `ReleaseOut`, `TrainingPack`, `PublishOut` and `AskOut` response fields are unchanged.
- Processing rejects existing drafts; MP4-only validation and Starlette's non-JSON 416 are intentional deviations.

## Contract examples

The export keeps the 16 numbered acceptance-step files unchanged in behavior. Steps 03, 11, 13 and 15 assert the preceding response and therefore repeat its request/response; step 16 captures the final fresh draft after reset. Login shape appears above; exported `access_token` values are always replaced with `<token>`. OpenAPI and six model JSON schemas are generated from running code, not hand-maintained. All schemas live at `contracts/*.json`, including the new `contracts/media.json` and `contracts/processing-job.json`.
