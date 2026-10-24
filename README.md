# Takumi learning workspace

A unified apprentice dashboard for the current shaft-and-bearing course. One consistent header provides Course content, Simulation playground, and Virtual interview. Progress, results, manual completions, and interview answers are stored by the FastAPI backend in SQLite.

## Run locally

Install Node.js and Python 3.11 with `uv`, then run from the repository root:

```powershell
npm install
uv sync --directory backend
npm run dev
```

This starts the learning backend on `127.0.0.1:8000` and the Vite frontend on `127.0.0.1:5173`. Open the frontend URL. For separate processes use `npm run dev:backend` and `npm run dev:frontend`. The frontend proxies `/api` to the backend; `VITE_API_TARGET` can override its address. Production hosting must similarly route `/api` to the backend.

The local application signs in as the existing demo apprentice. This is a shared demo identity, not a production login system. The seeded approved knowledge release supplies the course outline. Existing Studio knowledge-engine APIs remain available.

## Learning sequence

1. **Course content:** play the recording within the interface. Playback resumes from the server record; visible playback sends timed heartbeats. Watching the course unlocks the playground. You can also explicitly select **Mark section complete**.
2. **Simulation playground:** inspect components, assemble the bearing, use the tools, answer the knowledge checks, and make a release or escalation decision. The backend replays the submitted actions to calculate the result before unlocking the interview. **Mark section complete** can also unlock the interview without a simulation score.
3. **Virtual interview:** answer three authored technical questions and optionally record an ungraded reflection. The backend grades fixed answer choices and stores the evaluation. Reloading restores the saved progression and interview.

Manual completion records the learner, source context, stage, and timestamp. It does not invent watched time, simulation attempts, or passing scores. The final evaluation explicitly identifies a manually completed, unassessed playground.

## Connect the course video

Set these values in `backend/.env` and restart the backend:

```dotenv
COURSE_VIDEO_URL=https://your-host.example/course.mp4
COURSE_VIDEO_DURATION_SECONDS=120
```

Use the recording's actual duration. The direct MP4/WebM URL must be accessible to the browser and permit embedded playback. No recording has been supplied yet, so the initial Course tab shows its outline and an honest recording-not-configured state. Manual completion remains available. Changing the recording or reviewed release starts a new course progression context.

## Validation

```powershell
npm test
npm run build
npm run test:e2e
uv run --directory backend pytest tests/test_learning.py -q
```

Browser tests need Playwright Chromium (`npx playwright install chromium`), or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an installed Chrome executable. They start isolated test servers on ports 5174 and 8001, use a six-second test recording, and write test databases/screenshots under ignored `test-results/`. The recording in `e2e/fixtures/` is only a playback test asset, never course content. Regenerate it with `node scripts/create-test-video.mjs` if needed.

The frontend suite covers the dashboard, locked stages, video playback and seek restrictions, manual unlocks, interview evaluation and reload, the original simulation scenarios, responsive layouts, and the WebGL fallback. Backend learning tests cover prerequisite enforcement, server-authoritative scores, source changes, ownership, private rubric choices, revisions, duplicate submissions, and manual completions.

## Implementation

`src/components/CourseHub.tsx` owns the unified dashboard and stage navigation. `CoursePlayer.tsx` handles embedded recording playback; `src/learning-api.ts` handles typed authenticated API requests. `src/App.tsx` remains the simulation workspace, embedded without a second header or status section. Local in-progress simulation histories are scoped to the course release and recording; completed results are persisted on the server.

The isolated `backend/app/learning/` package integrates with the existing authentication, reviewed releases, database, and error envelopes. See [learning API documentation](backend/docs/LEARNING_INTEGRATION.md), [backend integration handoff](backend/docs/INTEGRATION_HANDOFF.md), and the [simulation workflow](markdowns/globals/Takumi_Bearing_Assembly_Demo_Workflow.md).

Course fixtures and assessment remain illustrative. The simulation demonstrates authored movement and judgment rather than mechanical physics. The interview is scripted, and free-text reflections are ungraded. Results do not replace supervised practical assessment. The existing Studio media-processing tests also require system ffmpeg/ffprobe.
