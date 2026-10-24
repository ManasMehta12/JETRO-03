# Integration handoff

Canonical contract: `../../markdowns/hackathon/openapi/API.doc.md`. Generated backend contract: `../contracts/openapi.json`. All paths below use `/api/v1`. Requests use JSON; bearer tokens carry server-verified roles. Unknown mutation fields are rejected. Errors use `{"error":{"code":"…","message":"…","details":null}}` (details may be an object).

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
| POST /tasks/{task_id}/media | Reserved upload | all | reserved → ErrorEnvelope | POST /api/v1/tasks/task_001/media | FEATURE_DISABLED (501) | ENABLE_MEDIA_UPLOAD (CP4) |
| POST /tasks/{task_id}/process | Reserved extraction | all | reserved → ErrorEnvelope | POST /api/v1/tasks/task_001/process | FEATURE_DISABLED (501) | ENABLE_MEDIA_PROCESSING (CP5) |
| GET /jobs/{job_id} | Reserved job status | all | reserved → ErrorEnvelope | GET /api/v1/jobs/job_001 | FEATURE_DISABLED (501) | ENABLE_MEDIA_PROCESSING (CP5) |
| GET /media/{media_id}/stream | Reserved media stream | all | reserved → ErrorEnvelope | GET /api/v1/media/media_001/stream | FEATURE_DISABLED (501) | ENABLE_MEDIA_STREAMING (CP4) |

Media routes are deliberate authenticated errors, not working media services. PATCH/PUT/DELETE on release resources return 405 `METHOD_NOT_ALLOWED`; see 14-reject-release-edit.json. Body-size middleware can return 413 for any request.

## Authentication

```sh
curl -X POST http://localhost:8000/api/v1/auth/demo-login \
  -H 'Content-Type: application/json' -d '{"demo_user":"reviewer"}'
curl http://localhost:8000/api/v1/tasks/task_001/release \
  -H 'Authorization: Bearer <access_token>'
```

The curl snippets show request shapes, not extra executed checks. Use returned `access_token` and `expires_at`; token type is bearer. Identities: `expert_001`, `reviewer_001`, `apprentice_001`, with display names Demo Expert/Reviewer/Apprentice. Never send X-Role as authorization. Keep tokens out of logs. Unless an explicit secret is set, restart invalidates tokens.

## Studio workflow

1. List/get tasks or create a task. Creation alone does not extract knowledge or create a draft in V1.
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

## Compatibility notes versus API.doc.md

- Additive revision, provenance, source-label and identifier fields support versioning and source resolution.
- Release `status` is derived, not mutable stored state.
- Retrying publication of the unchanged current revision returns 200 and the same release, not a second 201 release.
- `/demo/reset` adds `state`; `attempts` returns 400 because the scenario engine owns learner attempts.
- Adds `GET /releases/{id}` and `GET /releases/{id}/training-pack`.
- Media/process/jobs/stream return 501 `FEATURE_DISABLED`. HTTP 501 is an addition to the canonical status table.
- No per-unit review step: publish = approval for all units. Draft `review_status` stays `draft`; only release snapshots are `approved`.
- New server databases auto-seed `approved_baseline` (`release_001`). Reset to `fresh` with the confirmed request above before a live expert demo.
- Scenario/attempt/viva/report routes are not served here. Teammates may mount routers in `app/main.py` and reuse `get_current_user`/`require_roles`.
- Ignore conflicting `markdowns/hackathon/openapi/*.openapi.json`: `/studio/*` prefixes, flat errors, `learner` role and `Idempotency-Key` convention do not govern this backend. API.doc.md wins. Generated source files were not edited.
- `GET /tasks/{id}` omits media/processing fields until Checkpoint 4; later additions must remain additive.

## Contract examples

The export has 16 numbered acceptance-step files. Steps 03, 11, 13 and 15 assert the preceding response and therefore repeat its request/response; step 16 captures the final fresh draft after reset. Login shape appears above; exported `access_token` values are always replaced with `<token>`. OpenAPI and four model JSON schemas are generated from running code, not hand-maintained.
