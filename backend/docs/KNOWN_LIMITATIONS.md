# Known limitations

- `app/fixtures/shaft_bearing_v1.json` is illustrative hackathon content, not a validated mechanical procedure. Do not infer torque, tolerances, tactile claims or safe operating specifications from it.
- Gemini video extraction, private media upload/streaming, durable `MediaAsset`/`ProcessingJob` tables and a separate worker are implemented. Successful live Gemini extraction is **unverified**: no real API key was available. Mocked tests do not establish model availability or extraction quality.
- Run a single worker for this hackathon deployment. Durable leases recover interrupted jobs; this is not a validated multi-worker deployment.
- Uploads accept only MP4 containers with h264/av1 video; QuickTime is rejected. Inspection checks ffprobe metadata, not a full video decode. `ffprobe` must be installed; generated-video tests also need `ffmpeg` and skip without either tool.
- Gemini timestamps are approximate and are not checked against video frames. Invalid intervals retain draft units without evidence and produce warnings; publication requires supported expert corrections. AI output is always unreviewed.
- Signed playback tokens can be reused for 10 minutes so seeking can make repeated range requests. They are scoped to one media ID, not single-use. Keep query tokens out of logs (`uvicorn --no-access-log`).
- Chunked uploads without `Content-Length` are size-bounded only after multipart spooling. Declared lengths have an earlier middleware bound; temporary disk capacity remains an operational concern.
- Processing requires a new task without a draft. `mode=demo` cannot analyze uploaded recordings; use the seeded V1 fixture flow instead.
- Provider file deletion after success is best-effort; deletion errors do not fail completed jobs. Failed jobs retain provider file references and local media. No automatic media cleanup or raw extraction debug logging is implemented.
- Live Q&A, live gaps, multilingual support, embeddings and advanced retrieval remain reserved; their flags and `LOG_MODEL_INPUTS` must stay false.
- Demo HMAC tokens are not production identity. Without a non-empty `DEMO_SIGNING_SECRET`, the signing key lives only in process memory and restart invalidates tokens. Multiple processes need the same explicit secret. Production demo flags must all be false; production identity remains outside V1.
- Q&A and gap detection stay deterministic even with `AI_PROVIDER=gemini`. Q&A is English-only keyword matching over approved snapshots, returns source-linked claims and abstains when requested facts are absent. It is not semantic retrieval.
- SQLite supports a single writer. Every transaction starts with `BEGIN IMMEDIATE`, so requests are serialized (waiting up to the 5 s busy timeout); this keeps concurrent draft edits at 409 `REVISION_CONFLICT` and concurrent publishes idempotent, at the cost of read concurrency. Schema v1/v2 upgrades add tables and advance to v3; unsupported schema versions fail startup rather than dropping data. Back up databases before upgrades.
- No `validate_required_knowledge` endpoint exists. Simulation clients check required IDs against `training-pack.knowledge_units[].id`.
- Scenario, attempt, viva and report routes belong to teammates. Reset `scope: "attempts"` returns 400 `RESET_SCOPE_UNAVAILABLE`.
- Exported API examples contain real run IDs and timestamps, so regeneration changes those values. Auth tokens are redacted. Some of the 16 acceptance steps assert the preceding response rather than sending a new request; their example files repeat that request/response.
- Current FastAPI/Starlette emits a TestClient deprecation warning for httpx. Tests still pass; dependency modernization is outside this checkpoint.
