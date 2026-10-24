# V2 checkpoint reports

Observed checkpoint evidence is recorded below. Implementation is not proof of successful live provider integration.

## Checkpoint C4

- Implemented features: private MP4 upload, ffprobe validation, SHA-256 metadata, media persistence, 10-minute signed playback URLs, bearer playback, release-scoped apprentice visibility and byte-range streaming.
- Commit: `0672220` — `feat(backend): media upload, ffprobe validation and range streaming (C4)`.
- Verified endpoints: upload 201; metadata GET 200; signed playback GET without bearer header 200.
- Upload validation results: generated 5-second h264+aac MP4 returned `duration_ms=5000`, `has_audio=true`, `size_bytes=66281`. Text renamed `fake.mp4` returned 422 `INVALID_MEDIA`.
- Streaming test results: full GET returned 66281 bytes; `Range: bytes=0-1023` returned 206, `Content-Range: bytes 0-1023/66281`, `Accept-Ranges: bytes`, 1024 bytes. Unsatisfiable `bytes=999999999-` returned 416 with an empty body.
- Known limitations: MP4 h264/av1 only; ffprobe metadata validation is not a full decode; reusable playback token expires after 10 minutes; chunked uploads are bounded after spooling.

## Checkpoint C5

- Commit: `9bd6d58` — `feat(backend): Gemini video extraction, durable processing jobs and worker (C5)`.
- Gemini model actually used: **no model completed extraction**. `gemini-invalid` was used only for an intentionally invalid-key worker preflight.
- SDK and API methods: installed `google-genai 2.33.0`; code uses `models.get`, `files.upload`, `files.get`, `models.generate_content` with `Part.from_uri` and Pydantic `response_schema`, then `files.delete`. This describes implemented calls, not a successful live extraction.
- Provider availability: **unverified**. The invalid-key real network call failed with `PROCESSING_FAILED: AI provider request failed.`, exit 2, without echoing the key. It does not establish availability to a valid key/model.
- Processing stages implemented: `uploaded` → `preparing_media` → `extracting` → `detecting_gaps` → `ready_for_review`; statuses `queued`, `running`, `completed`, `failed`.
- Successful extraction evidence: mocked-provider tests cover draft/evidence/clarification persistence; **no successful live Gemini extraction evidence exists**. The opt-in live test was skipped because no key was available.
- Retry and recovery results: passing mocked-provider suite covers retry, provider-file reuse, invalid-output retry-once, timeout exhaustion and lease recovery. No live-provider retry/recovery claim is made.
- V1 integration results: passing suite includes fixture and mocked-extraction integration. Real-server fixture CLI/reset regression is reserved for final verification below.
- Real-server smoke: existing v2 database at `/tmp/takumi_v2.db` upgraded in place; health reported schema version 3. New task/upload returned 201. Live processing with fixture provider returned 503 `AI_PROVIDER_UNAVAILABLE`, with required configuration list `[AI_PROVIDER=gemini, ENABLE_LIVE_EXTRACTION=true, GEMINI_API_KEY, GEMINI_MODEL]`. Demo processing returned 422 `FIXTURE_NOT_AVAILABLE`. Playback remained 200 after failed processing. Unknown job returned 404 `PROCESSING_JOB_NOT_FOUND`.
- Worker without `ENABLE_PROCESSING_WORKER` returned exit 2 and `ENABLE_PROCESSING_WORKER is false`.

## Testing

- Baseline command: `uv run pytest -q` — 88 passed before V2.
- Dependencies: `python-multipart 0.0.32`, `google-genai 2.33.0`, installed through `uv add`.
- C4 commands: `uv run pytest -q` — 113 passed; `uv run ruff check .` and `uv run ruff format --check .` clean.
- C5 commands: `uv run pytest -q` — 192 passed, 1 skipped; `uv run ruff check .` and `uv run ruff format --check .` clean.
- Tests failed: none in those checkpoint gate results.
- Tests skipped: `tests/test_gemini_live.py`, opt-in, no key.
- Live integration status: media HTTP smoke verified; successful Gemini extraction **unverified**.
- Smoke server used `ENABLE_MEDIA_UPLOAD=true`, `ENABLE_MEDIA_STREAMING=true`, `DATABASE_URL=sqlite:////tmp/takumi_v2.db`, `MEDIA_STORAGE_DIR=/tmp/takumi_media`; generated video used ffmpeg.
- Opt-in live command (not executed successfully):
  ```sh
  TAKUMI_LIVE_GEMINI=1 GEMINI_API_KEY=… GEMINI_MODEL=… TAKUMI_LIVE_VIDEO=/path/to.mp4 uv run pytest tests/test_gemini_live.py
  ```

## API compatibility

- Existing lifecycle routes and response fields are preserved, including `DraftOut`, `EvidenceItemOut`, `ReleaseOut`, `TrainingPack`, `PublishOut`, `AskOut`.
- Media upload, stream, process and job routes now work behind their flags instead of reserved stubs. `GET /media/{id}` is additive.
- Processing returns 202 with full `JobOut`; no request waits for extraction. Task detail remains unchanged; frontend tracks returned media/job IDs.
- New schema exports: `contracts/media.json`, `contracts/processing-job.json`; existing four schema paths and 16 fixture examples remain unchanged in behavior.
- Documentation updated: README, integration handoff, limitations, this report, V2 implementation plan and root AGENTS.md. Historical V1 checkpoint reports link here.

## Feature flags

- Defaults enabled: demo capabilities, grounded fixture Q&A and training-pack export.
- Defaults disabled: media upload/streaming, media processing, live extraction and worker.
- Live configuration requires `AI_PROVIDER=gemini`, nonempty `GEMINI_API_KEY` and `GEMINI_MODEL`, `ENABLE_MEDIA_UPLOAD=true`, `ENABLE_MEDIA_PROCESSING=true`, `ENABLE_LIVE_EXTRACTION=true`, `ENABLE_PROCESSING_WORKER=true`; enable streaming for browser playback and `video_flow.py`.
- Server and worker share database/storage configuration. Lease (180 seconds by default) must exceed provider timeout (120 seconds).
- Live Q&A/gaps, multilingual, embeddings, advanced retrieval and model-input logging remain reserved and disabled. Q&A/gaps stay deterministic even when video extraction uses Gemini.

## Outstanding work

- Successful live Gemini extraction requires an available real key, a video-capable model and a real recording; this remains unverified.

## Final verification

All commands run from `backend/` after the docs/scripts wave.

- `uv run pytest -q` → 193 passed, 1 skipped (`tests/test_gemini_live.py`, opt-in; live Gemini unverified). Includes the post-review regression `test_unusable_output_is_not_checkpointed`: model output with no usable steps is no longer checkpointed, so the single retry re-asks the model.
- `uv run ruff check .` → no issues; `uv run ruff format --check .` → all files formatted.
- `uv run python scripts/export_contracts.py` → OpenAPI, six schemas (`contracts/media.json`, `contracts/processing-job.json` new) and 16 examples; examples reverted because ids are random.
- Fresh server with `ENABLE_MEDIA_UPLOAD/STREAMING/PROCESSING=true` and fixture provider, `uv run python scripts/video_flow.py --video /tmp/takumi_demo.mp4` (5 s h264+aac) printed `media_id=…`, `duration_ms=5000`, `range=206`, then `HTTP 503: … AI_PROVIDER_UNAVAILABLE … "required":["AI_PROVIDER=gemini","ENABLE_LIVE_EXTRACTION=true","GEMINI_API_KEY","GEMINI_MODEL"]`, exit 1 (expected: live not configured).
- After that 503, the playback URL still streamed 200 (66281 bytes): media preserved. A text file named `fake.mp4` → 422 `INVALID_MEDIA`.
- Default `.env` server on the existing schema-v1 `data/takumi.db`: started without error, `/api/v1/health` reported `schema_version` 3. `scripts/demo_flow.py` → `OK 1` … `OK 16`. `scripts/reset_demo.py --state fresh --yes` → `reset to fresh`, exit 0.
- Worker preflight: invalid key → `PROCESSING_FAILED: AI provider request failed.`, exit 2, key not echoed; worker flag off → `ENABLE_PROCESSING_WORKER is false`, exit 2.
- Not run: live Gemini extraction (no API key). Opt-in: `TAKUMI_LIVE_GEMINI=1 GEMINI_API_KEY=… GEMINI_MODEL=… TAKUMI_LIVE_VIDEO=/path/to.mp4 uv run pytest tests/test_gemini_live.py`.
