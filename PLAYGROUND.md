# Takumi learning workspace

A unified apprentice dashboard for the current shaft-and-bearing course. One consistent header provides Course content, Simulation playground, and Virtual interview. Progress, results, manual completions, and interview answers are stored by the FastAPI backend in SQLite.

## Run locally

Install Node.js and Python 3.11 with `uv`, then run from the repository root:

```powershell
npm install
uv sync --directory takumi-backend
npm run dev
```

This starts the learning backend on `127.0.0.1:8001` and the Vite frontend on `127.0.0.1:5173`. Open the frontend URL. For separate processes use `npm run dev:backend` and `npm run dev:frontend`. The frontend proxies `/api` to the backend; `VITE_API_TARGET` can override its address. Production hosting must similarly route `/api` to the backend.

The local application uses shared demo identities. Open `/studio` for the source diagnosis and expert review workspace, or `/` for the apprentice. `/studio/admin` opens tutor administration using the same agent workflow and the server-provided administrator identity. In demo mode, successful evaluation and human approval publish directly; there is no separate admin authorization step.

## One-button diagnosis demo

1. Open **Expert Studio**. The bearing exercise is explicitly connected to the apprentice course.
2. The panel defaults to **Live AI agents** and loads evidence from the connected server task. Select **Run AI diagnosis** when a Gemini key is configured. Missing credentials show **Configuration required**. Select **Illustrative rehearsal** explicitly in Analysis mode only when you want the fixed demonstration. The server extracts source facts, proposes field patches and independently evaluates their support. The UI shows actual server stages, source quotes and before/after changes.
3. Review/select patches. If unanswered expert prompts remain, explicitly choose to defer them as unknown, or resolve them in **Expert review**. Enter a publication note and select **Approve & publish changes**.
4. The apprentice automatically opens the updated course. Complete the lesson/playground normally or use their explicit manual completion buttons, then start a new structured interview. The approved release supplies its source and answers.

Configure live diagnosis in `takumi-backend/.env` and restart the backend:

```dotenv
GEMINI_API_KEY=your_key_here
STUDIO_AI_MODEL=gemini-2.5-flash
ENABLE_STUDIO_AI_ANALYSIS=true
```

Use a model available to your key; `GEMINI_MODEL`, when provided, overrides `STUDIO_AI_MODEL`. Source-note diagnosis detects the key automatically and does not require enabling the separate video-upload/worker flags or changing `AI_PROVIDER`. There are three bounded model calls, with a default timeout of 30 seconds each. A failed live run stays failed and never silently becomes a rehearsal. A missing key blocks live diagnosis; it never automatically substitutes fixed patches. An illustrative rehearsal is available only when explicitly selected in demo mode. Source notes are sent to the configured provider during a live run. Keys stay on the backend.

Video URL and live conversational interviewing are deferred. The current extraction input is editable expert source notes, and the viva remains structured templates grounded in published content. Real requests were attempted with the configured credentials; the provider returned timeout/service-unavailable responses. A successful live run still needs rehearsal. See the [admin rewrite verification](audits/2026-10-25-admin-agent-rewrite.md).

Run `npm run demo:preflight` to check service health, analysis mode, pending questions and active release without resetting or publishing. Set `TAKUMI_API_ORIGIN` if the API is not on port 8001. See [demo remediation and runbook](audits/2026-10-25-demo-remediation.md).

## Learning sequence

1. **Course content:** play the recording within the interface. Playback resumes from the server record; visible playback sends timed heartbeats. Watching the course unlocks the playground. You can also explicitly select **Mark section complete**.
2. **Simulation playground:** inspect components, assemble the bearing, use the tools, answer the knowledge checks, and make a release or escalation decision. The backend replays the submitted actions to calculate the result before unlocking the interview. **Mark section complete** can also unlock the interview without a simulation score.
3. **Virtual interview:** answer three technical questions assembled from the approved release and optionally record an ungraded reflection. The backend grades fixed answer choices and stores the evaluation. Reloading restores the saved progression and interview.

Manual completion records the learner, source context, stage, and timestamp. It does not invent watched time, simulation attempts, or passing scores. The final evaluation explicitly identifies a manually completed, unassessed playground and can be downloaded as Markdown with the questions, responses and evidence. Reset success requires a saved backend reset. Publication starts a fresh learner context for the new release; publish before preparing a learner demonstration.

## Connect the course video

Set these values in `takumi-backend/.env` and restart the backend:

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
uv run --directory takumi-backend pytest tests/test_learning.py -q
```

Browser tests need Playwright Chromium (`npx playwright install chromium`), or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an installed Chrome executable. They start isolated test servers on ports 5174 and 8002, use a six-second test recording, and write test databases/screenshots under ignored `test-results/`. The recording in `e2e/fixtures/` is only a playback test asset, never course content. Regenerate it with `node scripts/create-test-video.mjs` if needed.

The frontend suite covers the dashboard, locked stages, video playback and seek restrictions, manual unlocks, interview evaluation and reload, the original simulation scenarios, responsive layouts, and the WebGL fallback. Backend learning tests cover prerequisite enforcement, server-authoritative scores, source changes, ownership, private rubric choices, revisions, duplicate submissions, and manual completions.

## Implementation

`src/components/CourseHub.tsx` owns the unified dashboard and stage navigation. `CoursePlayer.tsx` handles embedded recording playback; `src/learning-api.ts` handles typed authenticated API requests. `src/App.tsx` remains the simulation workspace, embedded without a second header or status section. Local in-progress simulation histories are scoped to the course release and recording; completed results are persisted on the server.

The isolated `takumi-backend/app/learning/` package integrates with the existing authentication, reviewed releases, database, and error envelopes. See [learning API documentation](takumi-backend/docs/LEARNING_INTEGRATION.md), [backend integration handoff](takumi-backend/docs/INTEGRATION_HANDOFF.md), and the [simulation workflow](markdowns/globals/Takumi_Bearing_Assembly_Demo_Workflow.md).

Course fixtures and assessment remain illustrative. The simulation demonstrates authored movement and judgment rather than mechanical physics. The interview is scripted, and free-text reflections are ungraded. Results do not replace supervised practical assessment. The existing Studio media-processing tests also require system ffmpeg/ffprobe.
