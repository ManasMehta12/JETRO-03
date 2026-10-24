# Known limitations

- `app/fixtures/shaft_bearing_v1.json` is illustrative hackathon content, not a validated mechanical procedure. Do not infer torque, tolerances, tactile claims or safe operating specifications from it.
- Gemini is interface only. No live extraction, live Q&A, media upload/streaming/processing, worker, embeddings or advanced retrieval is implemented. Reserved flags fail at startup; media endpoints return 501 `FEATURE_DISABLED` after authentication.
- No Media or ProcessingJob table exists. The reserved ProcessingJob contract is: `id`, `task_id`, `media_id`, `input_hash`, `status`, `stage`, `attempt_count`, `error`, `result_draft_id`, `created_at`, `updated_at`. Do not assume persistence or polling works before the processing checkpoint.
- Demo HMAC tokens are not production identity. Without a non-empty `DEMO_SIGNING_SECRET`, the signing key lives only in process memory and restart invalidates tokens. Multiple processes need the same explicit secret. Production demo flags must all be false; production identity remains outside V1.
- Q&A is deterministic English-only keyword matching. It uses only approved snapshots, returns source-linked claims and abstains when requested facts are absent. It is not semantic retrieval.
- SQLite supports a single writer. Every transaction starts with `BEGIN IMMEDIATE`, so requests are serialized (waiting up to the 5 s busy timeout); this keeps concurrent draft edits at 409 `REVISION_CONFLICT` and concurrent publishes idempotent, at the cost of read concurrency. It is not a multi-writer service. Schema changes require an explicit future migration; schema mismatches fail startup rather than dropping data.
- No `validate_required_knowledge` endpoint exists. Simulation clients check required IDs against `training-pack.knowledge_units[].id`.
- Scenario, attempt, viva and report routes belong to teammates. Reset `scope: "attempts"` returns 400 `RESET_SCOPE_UNAVAILABLE`.
- Exported API examples contain real run IDs and timestamps, so regeneration changes those values. Auth tokens are redacted. Some of the 16 acceptance steps assert the preceding response rather than sending a new request; their example files repeat that request/response.
- Current FastAPI/Starlette emits a TestClient deprecation warning for httpx. Tests still pass; dependency modernization is outside this checkpoint.
