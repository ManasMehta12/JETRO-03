# Sequential learning API

The isolated `app/learning/` package composes the reviewed knowledge release with the bearing workshop and a deterministic technical interview. Existing knowledge-engine endpoints and permissions are preserved. All learning endpoints require an authenticated `apprentice` bearer token; progress is scoped to that identity in SQLite. The supplied demo authentication still represents a single shared demo apprentice, not a production identity provider.

## Configure the course recording

Set `COURSE_VIDEO_URL` to a browser-playable course video URL and `COURSE_VIDEO_DURATION_SECONDS` to its actual duration (default 60). The URL is empty by default because the user has not supplied their recording. Blank configuration never records completed watching. A learner can explicitly use the manual section-completion action described below to progress without a recording. Configure a URL that permits browser playback from this application's origin; native playback cannot use a standard video-platform watch-page URL.

The course reads `task_001` and its active immutable release. A reviewed release is required for watching. A changed release, URL or duration resets the current enrollment's watch progress and downstream results. Course content retains its `source_label`, including `illustrative` on the supplied demo. No unpublished draft is used as course content.

## Endpoints

All paths have prefix `/api/v1/learning`.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/course` | — | Course metadata, recording configuration and active-release knowledge units |
| GET | `/progress` | — | Current authoritative enrollment progress |
| POST | `/playback` | — | `{session_id, position_seconds, progress}`; starts/resumes a timed watch session |
| POST | `/playback/{session_id}` | `{position_seconds}` | Progress; send every five seconds during playback and at pause/end |
| POST | `/playground` | `{scenario, mode, actions: string[]}` | Progress with replay-validated scores and result |
| POST | `/complete` | `{stage: "course" or "playground"}` | Progress with an audited manual section completion |
| POST | `/interview` | — | Progress with the existing or newly started interview |
| POST | `/interview/answers` | `{session_id, question_id, option_id, reflection?, expected_revision}` | Progress after exact authored option grading |

Course metadata: `{id, title, description, equipment, source_label, release_id, video_url, video_duration_seconds, video_configured, knowledge_units}`.

Progress: `{course_id, release_id, watched_seconds, course_completed, playground_unlocked, interview_unlocked, playground_result, interview, manual_completion}`. A playground result includes `id`, source release, scenario, mode, independent `scores` (`procedure`, `judgment`, `knowledge`), `critical_error`, outcome and its submitted action history. Scores are derived by replaying all inspections, observation, physical workshop puzzle checkpoints, knowledge choices and final decision; client score fields are rejected.

The watch service uses a server clock and a monotonic playback frontier, allows rewinds, rejects implausible forward jumps, caps each elapsed credit at 15 seconds, and permits up to one second (or two percent for short videos) of end tolerance. Jitter debt can catch up on a subsequent heartbeat. This is practical progression tracking, not proof of human attention or secure video attestation.

Manual section completion is an explicit learner action. Course completion requires an approved release; playground completion also requires the course section complete. The server stores identity, source context, stage and UTC timestamp in the additive `learning_completions` table. It unlocks later sections without inventing watch time, attempts, results or simulation scores. An interview after manual playground completion returns `playground_assessed: false` and an explicit unscored notice. Source changes invalidate manual completion for the new course context too.

Only the current interview question and option labels are public. Private points, future questions and rubric data stay on the server. Accepted answers expose authored feedback, points and evidence IDs from the bound release snapshot. Optional reflection text is stored but never graded. Three accepted answers freeze a result with explanation points out of six and recognition-of-limits points out of three; a critical playground error remains visible. Exact answer retries return the original response, including after later answers; stale revisions and out-of-order answers fail. Starting again returns the existing session. Submitting a different completed playground attempt replaces the current interview; identical attempt retries are idempotent.

Stable learning errors include `COURSE_VIDEO_UNAVAILABLE`, `COURSE_RELEASE_UNAVAILABLE`, `INVALID_PLAYBACK_PROGRESS`, `COURSE_INCOMPLETE`, `INVALID_ATTEMPT`, `PLAYGROUND_INCOMPLETE`, `INVALID_ANSWER`, `INTERVIEW_COMPLETED`, plus the shared `NOT_FOUND` and `REVISION_CONFLICT`. Error envelopes use the existing application format. The implementation intentionally does not consume the conflicting generated OpenAPI specifications.

## Validation

`uv run pytest tests/test_learning.py -q` covers sequencing, missing video/release, session ownership, seeking, actual frontend action-fixture parity, invalid operations, server-authoritative scores, session reuse, answer order/revisions/retries, completion, reload, source changes and manual completion without fabricated scores. The full existing backend suite remains the regression gate.

