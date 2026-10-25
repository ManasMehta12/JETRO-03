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
- Gemini model actually used: `gemini-3.5-flash-lite` (2026-10-25, real key). `gemini-invalid` was used earlier only for an intentionally invalid-key worker preflight.
- SDK and API methods: installed `google-genai 2.33.0`; code uses `models.get`, `files.upload`, `files.get`, `models.generate_content` with `Part.from_uri` and Pydantic `response_schema`, then `files.delete`. These calls completed in the live run below.
- Provider availability: verified for `gemini-3.5-flash-lite` with a real key. The earlier invalid-key call failed with `PROCESSING_FAILED: AI provider request failed.`, exit 2, without echoing the key.
- Processing stages implemented: `uploaded` → `preparing_media` → `extracting` → `detecting_gaps` → `ready_for_review`; statuses `queued`, `running`, `completed`, `failed`.
- Successful extraction evidence: on a temporary database, the real worker path (`run_once` + `GeminiAIProvider`) processed a 25.8 s synthetic narrated MP4 (espeak-ng voice, captioned flat-colour frames, four inspection steps at known times) in 14.6 s, one attempt, no warnings. It produced 4 knowledge units with video evidence intervals within 0.7 s of the spoken segments and 3 clarification questions. Usage: 2,682 prompt tokens (2,363 video), 528 output tokens. Weakness: on-screen captions were copied into `cue`. Mocked-provider tests still cover draft/evidence/clarification persistence.
- Retry and recovery results: passing mocked-provider suite covers retry, provider-file reuse, invalid-output retry-once, timeout exhaustion and lease recovery. No live-provider retry/recovery claim is made.
- V1 integration results: passing suite includes fixture and mocked-extraction integration. Real-server fixture CLI/reset regression is reserved for final verification below.
- Historical C5 real-server smoke: existing v2 database at `/tmp/takumi_v2.db` upgraded in place; health reported schema version 3 at that checkpoint (current code uses schema version 7). New task/upload returned 201. Live processing with fixture provider returned 503 `AI_PROVIDER_UNAVAILABLE`, with required configuration list `[AI_PROVIDER=gemini, ENABLE_LIVE_EXTRACTION=true, GEMINI_API_KEY, GEMINI_MODEL]`. Demo processing returned 422 `FIXTURE_NOT_AVAILABLE`. Playback remained 200 after failed processing. Unknown job returned 404 `PROCESSING_JOB_NOT_FOUND`.
- Worker without `ENABLE_PROCESSING_WORKER` returned exit 2 and `ENABLE_PROCESSING_WORKER is false`.

## Testing

- Baseline command: `uv run pytest -q` — 88 passed before V2.
- Dependencies: `python-multipart 0.0.32`, `google-genai 2.33.0`, installed through `uv add`.
- C4 commands: `uv run pytest -q` — 113 passed; `uv run ruff check .` and `uv run ruff format --check .` clean.
- C5 commands: `uv run pytest -q` — 192 passed, 1 skipped; `uv run ruff check .` and `uv run ruff format --check .` clean.
- Tests failed: none in those checkpoint gate results.
- Tests skipped: `tests/test_gemini_live.py`, opt-in, no key.
- Live integration status: media HTTP smoke and successful Gemini extraction verified on an earlier synthetic narrated clip and the Navy clip in Final acceptance (§26). Quality is promising, not validated.
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
- Live configuration requires `AI_PROVIDER=gemini` with `GEMINI_API_KEY` and `GEMINI_MODEL`, `AI_PROVIDER=ollama` with `OLLAMA_BASE_URL`, `OLLAMA_MODEL` and `WHISPER_BASE_URL`, or `AI_PROVIDER=openrouter` with `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` and `WHISPER_BASE_URL`. Each requires the shared media upload, processing, live extraction and worker flags. Enable streaming for browser playback and `video_flow.py`.
- Server and worker share database/storage configuration. Lease (180 seconds by default) must exceed provider timeout (120 seconds).
- Live Q&A/gaps, multilingual, embeddings, advanced retrieval and model-input logging remain reserved and disabled. Q&A/gaps stay deterministic for every extraction provider.

## Outstanding work

- Live Gemini extraction is verified on a synthetic narrated clip and one Navy training film excerpt. Broader recording coverage, visual-only action quality and other Gemini models remain unverified. Quality is promising, not validated. Saved job `usage` covers only the successful attempt; reconcile retries against provider billing.

## Final verification

All commands run from `takumi-backend/`. Historical smoke results below are retained; Final acceptance (§26) records the latest run.

- Latest `uv run pytest -q` → 321 passed, 1 skipped (`tests/test_gemini_live.py`, opt-in). Coverage includes `test_unusable_output_is_not_checkpointed`: model output with no usable steps is not checkpointed, so the single retry re-asks the model. Live Gemini verification used the worker/script path, not the skipped opt-in test.
- `uv run ruff check .` → no issues; `uv run ruff format --check .` → all files formatted.
- `uv run python scripts/export_contracts.py` → OpenAPI, six schemas (`contracts/media.json`, `contracts/processing-job.json` new) and 16 examples; examples reverted because ids are random.
- Fresh server with `ENABLE_MEDIA_UPLOAD/STREAMING/PROCESSING=true` and fixture provider, `uv run python scripts/video_flow.py --video /tmp/takumi_demo.mp4` (5 s h264+aac) printed `media_id=…`, `duration_ms=5000`, `range=206`, then `HTTP 503: … AI_PROVIDER_UNAVAILABLE … "required":["AI_PROVIDER=gemini","ENABLE_LIVE_EXTRACTION=true","GEMINI_API_KEY","GEMINI_MODEL"]`, exit 1 (expected: live not configured).
- After that 503, the playback URL still streamed 200 (66281 bytes): media preserved. A text file named `fake.mp4` → 422 `INVALID_MEDIA`.
- Historical smoke on the default-configuration server and existing schema-v1 `data/takumi.db`: startup succeeded and `/api/v1/health` reported `schema_version` 3 at that checkpoint (current code uses 7). `scripts/demo_flow.py` → `OK 1` … `OK 16`. `scripts/reset_demo.py --state fresh --yes` → `reset to fresh`, exit 0.
- Worker preflight: invalid key → `PROCESSING_FAILED: AI provider request failed.`, exit 2, key not echoed; worker flag off → `ENABLE_PROCESSING_WORKER is false`, exit 2.
- Live Gemini extraction later succeeded on the synthetic clip and the Navy acceptance clip below. The opt-in pytest test remains skipped; its command is `TAKUMI_LIVE_GEMINI=1 GEMINI_API_KEY=… GEMINI_MODEL=… TAKUMI_LIVE_VIDEO=/path/to.mp4 uv run pytest tests/test_gemini_live.py`.

## Ollama transcript provider

Pipeline: backend ffmpeg extracts 16 kHz mono WAV → whisper.cpp `whisper-server` `/inference` with `verbose_json` → non-speech markers such as `[BLANK_AUDIO]` are dropped → cached transcript → Ollama `/api/chat` with JSON-schema `format`, `temperature=0`, `num_ctx=8192`. Cache path is `MEDIA_STORAGE_DIR/transcripts/<media_id>.json`; success deletes it, and missing cache raises `AI_FILE_EXPIRED` so the worker re-transcribes. Steps are forced to `source_modality="spoken"`; `detected_language` uses whisper's language name, such as `english`.

This text-only provider captures narration, not visual-only knowledge. Job provenance is `provider="ollama"`, `model_id=OLLAMA_MODEL`, `prompt_version="transcript_extraction_v1"`. Q&A/gaps remain deterministic. A 503 `details.required` list identifies the selected provider's settings.

### Verified (Linux development box, 2026-10-25)

- `uv run pytest -q` → 204 passed, 1 skipped; ruff check/format clean. `tests/test_ollama_provider.py` uses mocked whisper/Ollama HTTP via `httpx.MockTransport` and real ffmpeg. `tests/test_processing.py::test_ollama_requires_audio_and_records_provenance` covers the audio gate and job provenance.
- Worker preflight with `OLLAMA_BASE_URL=http://127.0.0.1:9 WHISPER_BASE_URL=http://127.0.0.1:9` → stderr `AI_PROVIDER_UNAVAILABLE: AI provider is unavailable.`, exit 2.
- Real server and worker against a local HTTP stub imitating whisper-server/Ollama (**not real models**): an espeak-ng narrated 13.28 s clip produced `range=206`, job `completed`, `knowledge_units=3`, with evidence intervals 0–4000, 4500–9500 and 9500–13000 ms.
- The stub confirmed a real WAV arrived and `[BLANK_AUDIO]` was absent from the prompt. The job row recorded `provider=ollama`, `model_id=qwen2.5:7b`, `prompt_version=transcript_extraction_v1`, and usage keys `prompt_eval_count`, `eval_count`. The transcript file was removed after success.
- Silent clip → `HTTP 422 MEDIA_HAS_NO_AUDIO`. Non-speech-only transcription is covered by mocked tests as non-retryable `NO_SPEECH_DETECTED`; no real transcription claim is made.

### Not verified

- Real whisper.cpp transcription and real Qwen output quality/speed on the MacBook Air M2; its RAM is unknown.
- LAN reachability and Windows/other demo-host OS behavior.
- AI must run on the separate Mac, not the backend host. See [README local-model setup](../README.md#local-models-ollama--whispercpp) for commands, recommended 300 s provider timeout/360 s lease, memory/language fallbacks and the trusted-network-only warning.

## OpenRouter transcript extraction

OpenRouter replaces only Ollama's text extraction request. ffmpeg and whisper.cpp still produce a timestamped transcript locally; only that transcript is sent to OpenRouter using strict JSON-schema output with `provider.require_parameters=true`. `OPENROUTER_MODEL` is a comma-separated fallback list sent as `models`; each job records the model that answered. Preflight passes when any listed model is reachable; 401/403 stays fatal.

### Verified (real key, 2026-10-25, 3-line English bearing transcript, extraction call only)

- `nvidia/nemotron-3.5-super-vl:free`: 3 faithful steps with correct intervals, 5–10 s. Chosen as primary.
- `xingchen-agi/xing4.0-29b-a4b:free` and `liquid/lfm-2.5-2.6b:free`: 429 upstream rate limit at test time.
- `nvidia/nemotron-3-super-120b-a12b:free`: provider 404 at test time; removed from the default list.
- `openrouter/free` routed to `dots-studio/dots-3-note-preview:free`, which returned 0 steps; the worker treats that as retryable `AI_RESPONSE_INVALID`.
- Not verified: whisper.cpp on the Mac, the full worker run with OpenRouter, Japanese transcripts.

## Final acceptance (§26)

### Run and media

- Date: 2026-07. Local server and worker processes used isolated database `/tmp/takumi_accept.db` on port 8011.
- Provider: `gemini`; model: `gemini-3.5-flash-lite`; prompt: `video_extraction_v2`.
- Video: `navy-bearing-clip.mp4`, a US Navy bearing training film excerpt; licence not verified. Duration: 230 030 ms; size: 17.6 MB; codecs: h264/aac.
- Upload succeeded. Range playback returned 206; full playback returned 200.
- Observed job stages: `uploaded` (0 s) → `preparing_media` (2 s) → `extracting` (16 s) → `ready_for_review` / `completed` (24 s).

### Extraction and human review

- Extraction created 6 knowledge units. Five had valid video evidence. Unit `ku_288214e78eef` (master ring gauge measurement) had no evidence: the model returned 227000–250000 ms, beyond the media end.
- Job warning: `INVALID_EVIDENCE_INTERVAL step 6 (227000-250000 ms): Video evidence interval exceeds media duration.`
- Two clarifications were created. The expert answered `missing_reasoning`, creating `expert_response` evidence `ev_ba54f3c8f837` and updating the interpretation. The `beginner_mistake` clarification was deferred.
- Studio evaluation failed as designed with `UNSUPPORTED_FIELD:action|cue|interpretation` on `ku_288214e78eef`. `scripts/video_flow.py` stopped with exit 1: `Evaluation failed: review flagged units before publishing`. This was the intended review gate: AI output never publishes without human review.
- The reviewer rejected that unit through `PATCH /tasks/{id}/draft` with `operation: reject`, advancing revision 2→3. Re-evaluation passed with no issues. The remaining steps were then run manually with the same requests the script uses; this was not an uninterrupted successful script run.
- Reviewer publication returned 201: `release_17de35601648`, version 1, active, with 5 units. Its training pack includes `ev_ba54f3c8f837`.
- Second live run (same clip, same script, job `job_e66d4e166a64`): 22 s, 5 units, 4 with evidence. The model returned 298000–321000 ms for step 5 (`ku_644e03fbd5ed`, sketching damage), beyond the media end, so evaluation failed with `UNSUPPORTED_FIELD:action` and the script exited 1 again. Usage: prompt 20 612, output 617, total 21 229 (≈ ₹0.74).
- Third live run (same clip, same script, job `job_97c3c4ed0c2c`): 32 s, 7 units, 4 with evidence. Steps 5–7 returned 213000–250000, 298000–322000 and 335000–347000 ms, all past the 230 030 ms media end; evaluation flagged `ku_38bc8048c50f`, `ku_c200440a9bbe` and `ku_e8bb33a192db` and the script exited 1. Usage: prompt 20 612, output 1 094, total 21 706 (≈ ₹0.90).
- The script's success path (lines after evaluation: reviewer publish, release, training pack, supported and unsupported questions) was exercised end to end in-process with the test `FakeExtractor` on a synthetic 3 s clip: it printed `release_id=release_7102621cfff5` and `acceptance=ok`. No live run printed `acceptance=ok`: in all three live runs Gemini produced intervals past the media end, and the review gate correctly blocked publication.

### Apprentice Q&A

- “Why do you show tilting pad bearing and precision insert split sleeve type bearing?” → `answered`; claims cite `ev_325f6d812391` and `ev_ba54f3c8f837`.
- “Why record the identification numbers?” → `answered`, but with the same claims. Keyword matching picked the first unit; answer relevance is promising, not validated.
- “What is the torque specification for this task?” → `insufficient_evidence`.

### Usage and regression

- Token usage is stored in `processing_jobs.usage`, not exposed by `GET /jobs/{id}`: prompt 20 612 (video 20 240, text 372), output 909, total 21 521.
- Estimated cost: ≈ $0.0085 ≈ ₹0.80, using $0.30 per 1M input tokens, $2.50 per 1M output tokens and ₹95/USD.
- Part F used the fixture provider on fresh database `/tmp/takumi_partf.db`. `scripts/demo_flow.py` completed `OK 1`–`OK 16`.
- `uv run pytest -q`: 321 passed, 1 skipped (live Gemini test). `uv run ruff check .` and `uv run ruff format --check .` were clean.
- This final acceptance used three live runs on one clip, in addition to the earlier synthetic-clip run. Every live run produced at least one out-of-range interval (1 of 6, 1 of 5, 3 of 7 steps), always late in the video; late-video timestamps from `gemini-3.5-flash-lite` are unreliable on this clip. Quality is promising, not validated beyond this limited evidence.
