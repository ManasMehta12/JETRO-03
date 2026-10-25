# V2 implementation plan — C4 media and C5 extraction

## Scope and status

Extend the V1 knowledge engine without replacing clarify → publish → training-pack → ask.
C4 implementation commit: `0672220`. C5 implementation commit: `9bd6d58`.
Checkpoint gates, media smoke and live Gemini extraction are verified, including an earlier synthetic clip and the Navy clip final acceptance run. Quality is promising, not validated.
See [docs/V2_CHECKPOINTS.md](docs/V2_CHECKPOINTS.md) for observed results, not inferred provider readiness.

## Fixed decisions

- Create a task, upload, then process. Existing drafts reject processing with 409 `DRAFT_ALREADY_EXISTS`; no replacement or automatic publication.
- Store recordings privately under `MEDIA_STORAGE_DIR`; accept only MP4 (not QuickTime), h264/av1 video, optional audio.
- Validate metadata with ffprobe, size/duration limits and SHA-256. This is not full decode validation.
- Playback uses bearer auth or a reusable 10-minute token scoped to one media ID. Apprentice access requires citation in any release snapshot of that task.
- Task detail stays unchanged. Frontend retains `media_id` and `job_id` from upload/process responses.
- Invalid model timestamps retain a knowledge unit without evidence and add warnings; never clamp. Publication remains blocked until human review supplies supported corrections or rejects unsupported units.
- Schema-invalid output gets at most one automatic retry, bounded by the global retry limit, reusing the provider file.
- Require explicit `GEMINI_MODEL` and `GEMINI_API_KEY`; no default model or fixture substitution for uploaded media.
- Q&A and gap detection remain fixture-backed/deterministic, even with `AI_PROVIDER=gemini`.
- No optional media-cleanup or raw-model-debug flags are implemented. Provider file deletion after success is best-effort; failures retain local media/provider references.

## Code path

1. `app/api/media.py`: thin authenticated upload, metadata, playback, process and job routes.
2. `app/services/media_service.py`: bounded copy, ffprobe, private storage, visibility and playback URLs.
3. `app/services/processing_service.py`: idempotent job creation; reject demo uploads, missing live configuration, existing drafts or concurrent processing.
4. `app/services/processing_worker.py`: separate durable worker; lease, provider calls, checkpoint and atomic completion.
5. `app/ai/gemini_provider.py`: model preflight, Files upload/poll/delete and structured `generate_content`.
6. `app/ai/prompts/video_extraction_v1.py`: versioned extraction instructions, task context, timestamp and no-audio rules.
7. `app/services/extraction_service.py`: validate units/evidence, deduplicate intervals and persist draft/revision/clarifications.

## Schema v7 and transactions

`MediaAsset` stores private storage key, task/owner, filename, hash, size, duration, codec and dimensions.
`ProcessingJob` stores task/media/mode/request identity, input hash, status/stage, attempts, lease, next attempt, provider file reference/state/expiry, extraction checkpoint, usage, warnings, errors and result draft ID.
Unique `(task_id, media_id, mode, request_id)` makes duplicate requests idempotent, including completed jobs.

Schema v1–v6 upgrades add missing tables through `create_all` and advance the schema stamp to 7 (`app/database.py:SCHEMA_VERSION`).
Unsupported schema versions fail startup; never discard existing databases automatically. Back up before upgrades.
Every SQLite transaction starts `BEGIN IMMEDIATE`; keep DB work short.
Services flush; routers/scripts/worker own commits. No ffprobe, file copying or Gemini calls run inside open transactions.
Persist evidence, draft, revision, deterministic clarifications and lease-guarded job completion in one transaction.
A lost lease rolls back the draft; release rows remain untouched. Fixture reset removes fixture jobs/media records, then files after commit.

## Job state machine

```text
queued / uploaded
  -> running / preparing_media
  -> running / extracting
  -> running / detecting_gaps
  -> completed / ready_for_review

retryable failure -> queued (next_attempt_at)
non-retryable or exhausted failure -> failed (stage retained)
expired running lease -> reclaimed running job, or failed after retry exhaustion
```

Claim the oldest eligible job atomically; increment attempts and extend its lease.
Heartbeat/provider polling extends the lease through guarded `_update` writes.
Reuse an existing provider file; re-upload on `AI_FILE_EXPIRED`.
Persist validated extraction before draft creation so recovery can resume without another model generation.
Completion sets draft ID and clears errors. Best-effort provider deletion runs afterward.
Worker logs identifiers, hashes, stages, durations and safe error codes, never keys, paths, prompts, responses or playback tokens.

## Retry table

Default `PROCESSING_MAX_RETRIES=2` allows up to three total attempts.
Delay uses provider retry-after, else `min(60, poll_interval * 2 ** attempt_count)` seconds.

| Failure | Policy |
|---|---|
| AI_RESPONSE_INVALID | Retry once at most, also bounded by global limit; reuse uploaded file |
| AI_PROVIDER_RATE_LIMITED | Retry with provider delay when available |
| AI_PROVIDER_UNAVAILABLE, PROCESSING_TIMEOUT | Retry to global limit |
| AI_FILE_EXPIRED | Re-upload when recovering an existing provider reference; other propagated failures use bounded retry |
| AI_PROVIDER_AUTH_FAILED, AI_FILE_PROCESSING_FAILED | Fail without retry |
| MEDIA_NOT_FOUND, DRAFT_ALREADY_EXISTS, DRAFT_PERSISTENCE_FAILED | Fail without retry |
| Other provider 4xx / unexpected failure | Safe PROCESSING_FAILED, no retry |
| Lease lost | Stop writing; current owner handles recovery |

## Configuration and commands

Defaults: upload/stream/processing/live/worker disabled; fixture flow needs no credentials.
Live mode requires all relevant flags, real credentials and an explicit video-capable model.
Server/worker share `DATABASE_URL`, `MEDIA_STORAGE_DIR` and settings.
Polling defaults to 2 seconds, lease to 180 seconds, provider timeout to 120 seconds; lease must exceed timeout.

Run from `takumi-backend/`, in separate terminals:
```sh
uv run uvicorn app.main:app --port 8000 --no-access-log
uv run python scripts/run_worker.py
uv run python scripts/video_flow.py --video demo.mp4
```

Use `scripts/demo_flow.py` for the unchanged 16-step fixture path.
Contract exporter retains the existing four schema files and 16 fixture examples and adds `contracts/media.json` and `contracts/processing-job.json`.
Live Gemini extraction succeeded through the worker/script path on a synthetic narrated clip and the Navy acceptance clip. Final regression: 321 passed, 1 skipped (opt-in live Gemini test); see [Final acceptance (§26)](docs/V2_CHECKPOINTS.md#final-acceptance-26) for the evaluation block, human rejection and manual completion.
