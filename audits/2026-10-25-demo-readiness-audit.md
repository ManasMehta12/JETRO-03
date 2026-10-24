# Takumi: critical application and judges’ demo audit

> Historical audit snapshot. The subsequent [demo remediation](2026-10-25-demo-remediation.md) documents implemented fixes and the revised one-button workflow. The original findings and reproduction evidence below are preserved.

**Audit date:** 25 October 2026 · **Target:** a reliable 3–4 minute judges’ demonstration.  
**Scope:** apprentice dashboard, video/course progression, simulation, viva, Expert Studio, tutor administration, knowledge extraction, publication, evidence, persistence, reset, operations, UI and test coverage.  
**Change boundary:** this audit creates documentation, screenshots and isolated reproduction evidence. It does not fix application behavior, publish content, reset the running demo, or change configuration.

## 1. Decision for the team

**The app is suitable for a prepared demonstration of reviewed expert knowledge flowing into a course and a structured assessment. The current running configuration is not ready for a live “record video → AI extracts tacit knowledge → adaptive AI interview” demonstration.**

The strongest story is one visible chain: **expert correction → evidence review → tutor authorization → immutable publication → changed apprentice guidance → interview grounded in that release.** Make the same sentence visibly travel through those screens. Avoid spending most of the slot on assembly mechanics.

The main risks are functional and narrative, rather than visual polish:

1. The running app has **no connected course recording** and **live extraction is disabled**.
2. The old reviewer publication endpoint bypasses the new admin authorization path.
3. Answering a clarification stores an answer as evidence but does **not** apply it to the tacit fields from this UI.
4. Reset is unreliable across the integrated app: full demo reset can retain learner completion, and the UI can announce a successful reset after a failed backend reset.
5. Publishing starts a new learner context and clears the current downstream progression. Publish **before** running the apprentice sequence.
6. The viva is a deterministic three-question multiple-choice assessment. It does not perform adaptive spoken interviewing or grade free-text reasoning.

**If presenting today:** use the bearing task only; start from a prepared draft; manually edit the first decision; resolve blocking questions before the timed slot; publish first; show one course change and one playground action; explicitly use manual progression; show the changed interview evidence. Keep an assessed simulation recording available, clearly labelled.

## 2. What was actually verified

### Running application snapshot

The audit queried the local service on port 8000 and inspected the UI on port 5173 without mutating its course or release.

| Check | Observed result | Meaning |
| --- | --- | --- |
| API/database | Healthy; development mode; schema 5 | Local service is available; this is not a production deployment. |
| Provider | `fixture` | Current runtime is not using Gemini or Ollama for extraction. |
| Media/live features | Upload, streaming, processing, worker and live extraction all disabled | A judge cannot exercise a live extraction workflow in this configuration. |
| Course | `task_001`, release `release_001`, version 1, three knowledge units | The apprentice is connected to the seeded bearing task. |
| Video | `video_configured: false` | The real course recording is still missing. |
| Studio | Draft revision 2; two pending clarifications; no evaluation or admin authorization | The untouched running state cannot immediately pass the new Studio publication checks. |
| Media tools | `ffmpeg` and `ffprobe` not found on the audit shell PATH | Live media operation needs an explicit dependency check; tools could exist outside PATH. |
| Desktop UI | Dashboard, Studio and admin checked at 1366×768 | Page bounds fit the viewport; panel content uses internal scrolling. No page JavaScript errors were observed during these navigations. |
| Mobile admin | 390×844 viewport; rendered document height 1917px | No horizontal overflow in this sample, but the admin workflow spans more than two screen heights. |

Screenshots: [dashboard](evidence/dashboard-1366.png), [Studio](evidence/studio-1366.png), [tutor admin](evidence/admin-1366.png), [mobile admin](evidence/admin-mobile.png). Raw geometry: [runtime observations](evidence/runtime-observations.json); service flags: [runtime health snapshot](evidence/runtime-health.json). Local navigation/ready measurements were single samples, not a performance benchmark.

### Checks rerun for this audit

| Verification | Result | Limit |
| --- | --- | --- |
| `npm test` | 33 passed | Mostly state, persistence and API behavior; does not establish all UI workflows. |
| `npm run build` | Passed | Vite still warns about the approximately 904 kB uncompressed 3D chunk. |
| Selected backend tests: Studio admin, learning, interview script, integration and seed | 38 passed | The entire backend/media suite was not rerun. |
| `uv run ruff check .` | Passed | Static checks do not validate content accuracy. |
| Isolated audit probes | Three issues reproduced | See findings A1–A3 and the stored probe results. |
| Prior implementation browser verification | Three real-backend journey/publication checks passed before this audit | Not rerun as a full browser suite here; the publication test prepares pending gaps using direct API calls. |

Reproduction evidence: [probe source](evidence/backend-audit-probes.py), [probe results](evidence/backend-probe-results.json). These probes use temporary SQLite databases, never the presenter’s database.

Passing tests do not prove a genuine expert recording was extracted successfully, that an instructor validated the bearing procedure, or that every published change alters a graded interview answer.

## 3. Capability map: implemented versus missing

| Area | Current capability | Missing or constrained | Demo stance |
| --- | --- | --- | --- |
| Landing/dashboard | Unified course, progression and assessment entry points | One hard-coded course/task; no course catalogue or real learner roster | Ready for the single bearing story. |
| Course | Native video player, watched-time tracking, approved knowledge outline, manual completion | No real video configured; duration is operator configured; no recording/source-segment integration | Configure a real short lesson or disclose the missing recording. |
| Playground | Two authored scenarios, inspection, tools, placement, checks, deterministic scoring, 3D and fallback | Not physics; published tacit edits do not rewrite its scenario or scoring | Show one meaningful action, not an entire build. |
| Viva | Three questions assembled from the release; private scoring; saved responses and source/script hashes | No speech, adaptive follow-up, free-response grading or genuine mistake-based question selection | Call it a release-grounded structured viva. |
| Expert capture | Backend media/job/provider adapters exist | Studio has no upload, new-task, extraction-progress or source-video controls | Start with a prepared draft; do not pretend to extract live. |
| Clarifications | Existing questions, dispositions, attributed answer evidence | No explicit answer-to-field mapping in the UI; no visible generation/rerun action | Manually apply the reviewed answer to the relevant field. |
| Tutor admin | Revision/hash-specific authorization to the demo expert; actor/time audit | Alternate publish route; no revoke, rejection/request-changes queue, real users or grant expiry | Demonstrate the narrow implemented path. |
| Publication | Immutable release snapshots, evidence references, optimistic draft revisions | Technical truth is not automatically verified; full governance is not centralized | Explain structural validation and human judgment separately. |
| Evidence | Stored references, attributed corrections, release snapshots | Mostly text; no clickable video spans in Studio; weak field-to-evidence visualization | Show one correction, its attribution and its published wording. |
| Reporting/history | Current simulation/interview result and feedback | No complete historical learner reports, export or cohort dashboard | Do not promise an enterprise analytics product. |
| Operations | Local launcher, SQLite, health endpoint, optional worker | No unified demo preflight/reset/checkpoint tooling; production auth and hosting work remain | Freeze one laptop and one presenter session. |

## 4. Critical findings and solutions

Priority means demo impact: **P0** can invalidate the main claim or derail the timed path; **P1** materially weakens the demonstration; **P2** is important product work that can usually wait until after judging. Estimates below are planning estimates, not measured implementation commitments.

### A1 — P0: admin authorization is not enforced across every publication path

**Confirmed by isolated reproduction.** `POST /api/v1/tasks/task_001/publish` with the reviewer role returned **201**, despite no Studio evaluation, no admin authorization and two pending clarifications. The new `/studio/.../publish` path correctly checks the grant; the old path calls the core publication service directly.

**Evidence:** `backend/app/api/releases.py:23`, `backend/app/services/publication_service.py:77`, `backend/app/services/studio_service.py:150`; probe `legacy_reviewer_publication`.

**Why judges may challenge it:** “An admin must authorize every publication” is broader than what the system enforces. This is an alternate privileged reviewer authority, not proof that the new Studio endpoint itself ignores permissions.

**Fix:** move the governing policy into a shared publication boundary or explicitly designate and document a separate reviewer override with an auditable reason. Exercise both endpoints in regression tests. Do not silently break the existing API contract.

**Until fixed:** use the new Studio path and say, “Expert publication through this workflow requires a tutor grant.” Do not claim universal admin enforcement.

### A2 — P0: a clarification answer can be recorded without changing the actual knowledge

**Confirmed by isolated reproduction.** Sending the same answer-only payload as Studio returned 200, added one evidence record and advanced revision 1→2. All five tacit content fields remained unchanged. `studioApi.clarify` does not send the backend’s optional `knowledge_update` object.

**Evidence:** `src/studio-api.ts:43`, `backend/app/services/clarification_service.py:52`; probe `answer_without_structured_update`.

**Demo consequence:** answering “why do you stop?” can appear successful while the course/interview still has no newly expressed decision or interpretation. “Answer captured” and “knowledge updated” are different operations today.

**Fix:** add a reviewed mapping from the response to cue/interpretation/decision/exception, preview the before/after fields and submit a structured update. Save the attributed answer separately from its interpreted field changes.

**Until fixed:** answer the question, then manually edit the relevant tacit field and save. Verify that exact field in the apprentice course after publication.

### A3 — P0: demo reset does not reliably reset the integrated application

There are two distinct problems:

- **Confirmed backend problem:** after manually completing course/playground, `/demo/reset` with `full_demo` and `approved_baseline` returned 200, but course completion and interview unlock remained true. The seeded `release_001` is reused; the learning context still matches, and reset does not remove the learning tables.
- **Code-inspection frontend problem:** `resetAllKnowledge` catches a failed learning reset, fabricates empty progress locally, removes broad sets of local-storage keys and announces a successful reset anyway. A reload can expose the unchanged server state.

**Evidence:** `backend/app/services/seed_service.py:123`, `backend/app/learning/models.py:9`, `backend/app/learning/service.py:50`, `src/components/CourseHub.tsx:114`; probe `full_demo_reset_learning_state`.

**Fix:** make the scopes explicit: learner progression reset, simulation reset, and complete demo reset. Coordinate the database operations and browser persistence. Report success only after server confirmation. Avoid broad local-storage substring deletion; delete the app’s exact scoped keys. Add reset→reload assertions for both success and failure.

**Until fixed:** do not trust the “full demo reset” name or a success toast. Reset learner progress through its own API/UI, reload, and inspect actual gates. Keep an offline backup of a rehearsed demo database and matching browser state. Never restore a database underneath a running SQLite process.

### A4 — P0: the live capture story cannot be demonstrated from the current UI/configuration

Studio edits existing task drafts. It has no recording upload, task creation, playback, extraction job progress or “extract” control. The runtime provider is fixture and all media/live flags are off. The launcher starts API and frontend, not the extraction worker.

**Evidence:** `src/components/ExpertStudio.tsx:29`, `backend/app/config.py:24`, `scripts/dev.mjs:6`, `backend/app/services/processing_worker.py:111`.

Backend Gemini and Ollama adapters exist, but their presence is not a successful live extraction rehearsal. Ollama’s adapter uses transcription; it is not visual understanding of silent hand movements. Processing requires a new task without a draft, while the apprentice integration only consumes `task_001`.

**Fast solution:** start from a prepared, clearly labelled draft and show the human knowledge correction live. Keep a recording of a genuine successful extraction and its job/model/source identity if available. Do not use the six-second browser-test animation as course or extraction evidence.

**Full solution:** wire upload → new task → worker status → source playback → draft/clarification review, plus an explicit mapping of that published task to the apprentice course. Verify real provider credentials, media binaries, a narrated clip, worker connectivity and measured latency before putting extraction on the critical path.

### A5 — P0: a real course recording is missing, and watch duration can be misconfigured

The current course has no video. The duration comes from configuration rather than being established by the actual media. A longer configured duration can leave the watch gate incomplete after the recording ends.

**Evidence:** runtime `/learning/course`; `backend/app/config.py:51`, `backend/app/learning/service.py:23`, `src/components/CoursePlayer.tsx:135`.

**Fix before rehearsal:** connect the supplied direct video URL and verify actual duration, browser playback, seeking/resume and completion on the exact presentation machine. Prefer a stable, locally served approved asset for venue independence when rights and deployment permit. Show only an excerpt in the timed talk and explicitly use manual completion if needed.

### A6 — P0: publishing resets the current learner context

A new release clears watch time, current playground result and interview when the next enrollment request runs. This prevents accidental reuse across different releases, but it is not a historical enrollment model.

**Evidence:** `backend/app/learning/service.py:50` and `:66`.

**Demo solution:** publication comes first. Only then prepare or perform the learner sequence for that exact release. A pre-completed assessed result created before the live publication will not survive the release change. Use a separate labelled recording for the full assessed simulation, or prepare it after publication outside the timed slot.

**Product solution:** retain enrollments and reports keyed by learner and release; show “new version available” and an explicit restart/continue policy rather than overwriting the current record.

### A7 — P1: Studio appears multi-task, apprentice is single-task

The Studio selector can show all tasks, but learning resolves only `task_001`. Publishing another task will not update the apprentice course. A new extraction on a new task therefore does not complete the current cross-component story automatically.

**Evidence:** `src/components/ExpertStudio.tsx:75`, `backend/app/learning/service.py:16`, `backend/app/services/processing_service.py:55`.

**Demo solution:** use only the bearing task and add a visible “connected to apprentice course” indicator if time permits. **Product solution:** explicit course/task/release assignments and a reviewed activation operation.

### A8 — P1: the interview claim is stronger than the implementation

The generated script uses three deterministic templates, fixed correct option IDs `b,b,c`, and conspicuously unsafe generic distractors. Reflections are stored but ungraded. The actual attempt is not passed into `build_script`; the same approved release produces the same interview regardless of learner mistakes.

Every approved field enters the source brief and hash, but graded correct answers use the first action, first available decision and first available exception. A changed later cue can alter the source brief without materially altering a graded answer. The “limits recognized” counter also increments for each correct answer, including ordinary inspection/decision items.

**Evidence:** `backend/app/learning/interview_script.py:27`, `:39`, `:70`; `backend/app/learning/service.py:190`, `:237`.

**Demo solution:** call it a **release-grounded structured viva**. Edit the first decision, then show it in the second question’s answer/source brief. Do not claim speech, adaptive AI follow-up, practical certification or automated grading of an expert explanation.

**Next implementation:** use explicit knowledge-unit/question coverage, select items from missed checkpoints and critical errors, strengthen reviewed distractors, and define rubric dimensions separately. If live generation is later added, validate its schema/evidence and snapshot the resulting script before assessment.

### A9 — P1: “evaluation passed” does not establish technical truth or complete tacit knowledge

Evaluation checks references, nonempty actions and unresolved pending questions. Null reasoning fields can remain; deferred/unobservable/rejected questions can resolve blockers without adding knowledge. A human correction becomes attributed evidence, which does not independently prove a physical observation.

**Evidence:** `backend/app/services/studio_service.py:31`, `backend/app/services/knowledge_service.py:110`, `backend/app/services/publication_service.py:109`.

**Solution:** present the state as “Evidence checks passed,” followed by tutor technical review. Show unknown fields and justified dispositions in the release review. Distinguish an illustrative source, a human-authored correction and an independently observed fact. Keep mechanical tolerances and tactile claims unknown unless supplied and reviewed by a qualified source.

### A10 — P1: the full playground is too long for the product pitch

The authored flow requires approximately **40 UI interactions** before the interview: selection/inspection, observation, 25 assembly operations, three quiz responses, view changes and a final decision. Its authored duration is 4–6 minutes. These are source-derived estimates, not measured presenter rehearsal times.

**Evidence:** `e2e/playground.spec.ts:5`, `src/simulation.ts:26`, `src/workshop.ts`.

**Solution:** spend 20–30 seconds on an inspection and one assembly action. Then explicitly mark the section complete for navigation; say that this creates **no assessed simulation score**. Use a short, labelled recording to establish the full assessed path. Do not attempt a complete build plus the entire governance workflow in a three-minute slot.

## 5. Remaining product, UX and reliability gaps

| Priority | Gap / evidence | Practical solution |
| --- | --- | --- |
| P1 | Apprentice checks release updates only on window focus; Studio reloads on role/task/action, not background changes. `CourseHub.tsx:51`; `ExpertStudio.tsx:29`. | One Studio tab with role switching, one apprentice tab. Focus/reload deliberately. Add refresh and visible release-update status later. |
| P1 | Playground content/scoring are authored constants; no published knowledge pack is passed into it. `src/simulation.ts`, `src/App.tsx:25`, `CourseHub.tsx:207`. | State that course and interview update; simulation stays authored. Later introduce separately reviewed scenario mappings/versioned bundles. |
| P1 | Shared demo identities mean devices share one learner record; role selector is not independent real-person authentication. `core/security.py:14`; `learning-api.ts:87`; `studio-api.ts:41`. | One controlled presenter session. Label demo roles. Add real identity, users and assignment before external multi-user use. |
| P1 | Pending clarifications sit below editable fields in a nested scroll area. At 1366×768 they are not necessarily visible initially. | Resolve them in preflight; show a pending-count banner with a jump link. Otherwise “Evaluate” can unexpectedly fail in front of judges. |
| P1 | Evidence is text-only in Studio and does not jump to recording spans or highlight field support. `ExpertStudio.tsx:81`. | Show one attributed response now; add clickable segment playback and field-to-evidence highlighting next. |
| P1 | Switching selected unit, task or role can discard unsaved editor state without a dirty-change confirmation. `ExpertStudio.tsx:39`. | Save before switching during the demo. Add a discard/save guard. |
| P2 | Desktop layout fits and is aligned, but many labels are approximately 9–11px. Nested scroll regions hide important review content. `src/studio.css`; screenshot evidence. | Rehearse on the actual projector. Prefer a focused one-unit/diff view and larger primary labels; test any zoom setting before the event. |
| P2 | Mobile admin reaches 1917px at a viewport height of 844px. “Everything visible without scrolling” is not true across devices. | Present from desktop. Prioritize summary and approval controls on mobile; collapse secondary evidence intentionally. |
| P2 | Final evaluation omits a complete question/selected-answer/evidence-linked report; no export or historical report browser. `CourseHub.tsx:208`; `learning/models.py:9`. | Add a compact evidence report with release ID, manual-vs-assessed status, question, response, feedback and source links. |
| P2 | No authorization revoke, reject/request-changes flow, expiry or review queue. Studio audit tables lack the release table’s UPDATE-blocking trigger. | Scope claims to revision-bound authorization and a stored audit history. Add governed lifecycle and append-only audit protection later. |
| P2 | Studio API has no deduplicated login or automatic retry after an expired token; failed writes may require manual retry. `src/studio-api.ts:16`. | Use role-scoped credentials, bounded renewal and explicit retry/refresh without losing editor state. |
| P2 | Google Fonts are requested externally in both main stylesheets. The lazy 3D chunk is about 904kB uncompressed. | Use local/system fonts for venue reliability, prewarm the 3D view, retain the existing fallback and avoid clearing caches just before presenting. |
| P2 | Health checks database availability, not complete demo readiness. Worker is a separate process and not started by `npm run dev`. | Add a single preflight showing recording availability, active release, pending gaps, grant state, worker/provider readiness and last successful rehearsal. |
| P2 | Accessibility has labelled controls and a 3D fallback, but no complete assistive-technology, keyboard-only or projector-contrast audit was performed. | Use existing explicit buttons rather than drag-only gestures in the demo; schedule keyboard/contrast checks and verify scroll-area focus. |
| P2 | Production account management, hosting persistence, backup/recovery, tenant boundaries and historical reporting are not established by this demo. | Treat them as follow-on work; do not describe the current demo role system as production security. |
| P2 | Planning/docs drift: missing canonical `API.doc.md`; old specs describe different routes, fixture activation and agent tools; limitations still describe schema 3 and teammate-owned viva/reset. | Produce one current capability/API handoff. Treat conflicting planning OpenAPI files as non-authoritative; do not implement fixes from them blindly. |

## 6. Time-boxed optimization plan

### If less than 60 minutes remain

Do not attempt new live AI, speech, new scenarios, broad visual redesign or a framework migration.

1. Freeze the running build and the bearing task. Stop unrelated development/HMR changes during rehearsal.
2. Confirm the approved recording or decide on an explicit no-recording/manual-progress fallback. Never use a placeholder clip as expert evidence.
3. Resolve the two pending questions on the presenter database honestly, or rehearse their explicit dispositions before the timed presentation.
4. Choose one **first decision** correction, with truthful attribution and wording reviewed by the domain expert. Prepare short authorization/publication notes.
5. Keep one Studio tab and one apprentice tab. Save before changing roles. Start the apprentice walkthrough only after publication.
6. Rehearse the four-minute sequence below twice with a stopwatch. Cut optional inspection actions if either run exceeds 3:40.
7. Record a successful full path and prepare screenshots of source evidence, authorization audit and the final result. Label recordings as recordings.
8. Verify resets by reload and server state, not by toast text. Take an offline backup using a safe SQLite backup or with the server stopped.

### If 2–4 engineering hours remain

The following is a priority order, not a promise that all items fit in four hours:

| Order | Change | Approximate effort | Acceptance criterion |
| --- | --- | --- | --- |
| 1 | Honest reset behavior and coordinated reset scopes | 45–90 min | Failed reset preserves state and displays failure; successful complete reset stays cleared after reload. |
| 2 | Close or explicitly govern legacy publication authority | 45–90 min | Both publish entry points exercise the intended policy; reviewer override, if retained, is explicit and audited. |
| 3 | Clarification response-to-field application | 60–120 min | A response changes the selected field, produces attributed evidence and reaches the next course/script. |
| 4 | Pending-gap summary, connected-task badge and refresh buttons | 30–60 min | Presenter cannot unknowingly choose an unconnected task or miss the reason publication is blocked. |
| 5 | Configure/rehearse a real short recording; prewarm assets | 20–45 min once content is available | Exact-duration playback and progression work on the presentation laptop. |

Fixing an issue requires its own focused regression checks. Do not replace a proven fallback with an untested last-minute integration.

### After judging

Complete the capture UI and successful live provider run; map published tasks to courses; add release-scoped learner history; improve evidence playback and interview coverage; add real user administration; formalize reports, audit lifecycle and production deployment. These are larger product capabilities, not demo-night polish.

## 7. Recommended four-minute demonstration

**Opening line:** “Takumi captures the reasons behind an expert’s decision, makes a tutor review them, and carries the approved guidance into apprentice learning.”

The following schedule is a rehearsal budget. It has not been measured as a complete human presentation during this audit.

| Time | Show / do | What judges should understand | Failure fallback |
| --- | --- | --- | --- |
| 0:00–0:20 | Problem and one prepared bearing knowledge unit | Instructions alone omit the expert’s cue, interpretation and decision. | Show one static before/after screenshot. |
| 0:20–0:55 | Show attributed evidence; edit the first decision; save; evaluate | Human judgment becomes explicit, evidence-linked draft content. State that the draft was prepared beforehand. | If save fails, show the recorded successful capture/review path and disclose it. |
| 0:55–1:30 | Switch to tutor admin, authorize with a note; return to expert and publish | AI/draft output does not automatically become apprentice instruction. This Studio path requires a revision-specific tutor grant. | Show the last successful authorization/publication audit; do not claim a failed click succeeded. |
| 1:30–1:50 | Open audit; point to actor/time, revision and release | The approved source is traceable and immutable. | Use the audit screenshot. |
| 1:50–2:20 | Focus apprentice, open updated course, show the exact new decision/version; play a short real excerpt if configured | The approved change reached learning content. | Reload once; if unavailable, show the labelled recording. |
| 2:20–2:45 | Explicit manual course completion; one inspection and one assembly action; manual playground completion | The authored simulation practices procedure. The shortcut unlocks navigation and creates no simulation score. | Skip the interaction and show the fallback/recording. |
| 2:45–3:25 | Start new structured viva; show reviewed source; show the changed decision in the relevant question | Interview preparation uses this approved release. It is structured assessment, not live conversational AI. | Show a prepared recording of the generated question and its source. |
| 3:25–3:45 | Finish the three responses if rehearsed; show result/manual status | Scoring and absence of a manually skipped simulation result are explicit. | Show a labelled previously completed result, never present it as newly assessed. |
| 3:45–4:00 | State current boundary and next step | Trusted knowledge propagation is the demonstrated value; live capture/adaptive interviewing are separately scoped. | End cleanly; leave questions for discussion. |

**For a three-minute slot:** cut the audit detour to 5 seconds, do not play a long course excerpt, show one playground action, and show the changed viva question rather than rushing through a full evaluation. The proof of propagation is more valuable than clicking every control.

**For a five-minute slot:** add a real clarification response plus its explicit field correction, or a supported-versus-unsupported simulation decision. Do not add live extraction unless a complete successful run fits comfortably with a tested fallback.

## 8. Preflight and recovery checklist

### Before judges arrive

- [ ] Confirm frontend, backend and persistent database are the intended versions; `/health` is healthy.
- [ ] Check actual provider/media feature flags. If demonstrating extraction, verify worker, model, narration and media dependencies independently.
- [ ] Confirm `task_001`, active release, current draft revision and all pending clarification dispositions.
- [ ] Confirm the course video is real, playable and has the configured actual duration; cache/local hosting is prepared if appropriate.
- [ ] Verify that the chosen correction changes a graded interview answer, not just its source hash.
- [ ] Rehearse publication first, then apprentice progress for that exact release.
- [ ] Test the reset scopes, reload, and confirm actual learner gates. Do not run the old destructive `demo_flow.py` against the presenter database; it begins by resetting it.
- [ ] One Studio tab, one apprentice tab, one presenter; no other device shares the demo apprentice during the slot.
- [ ] Open the 3D view once to warm assets; confirm explicit non-drag controls and the fallback.
- [ ] Verify legibility on the actual projector, footer visibility and nested scrolling at the chosen resolution.
- [ ] Keep a clearly labelled recording and screenshots accessible without internet.
- [ ] Stop background edits, test runners, extraction jobs and notifications that could steal focus or change state.

### During the slot

| Symptom | Recovery rule |
| --- | --- |
| Evaluation fails | Read pending-gap/evidence issue once. If not immediately understood, use the recorded path rather than improvising a false domain answer. |
| Authorization or publish conflicts | Refresh the Studio state once. A changed revision requires reevaluation and fresh authorization. Do not bypass via the legacy endpoint during the demo. |
| Apprentice shows old content | Focus its tab, then reload once. Check the release version. |
| Progress disappears after publish | Expected current context reset; proceed through the disclosed manual shortcuts. Do not promise the old result survived. |
| Video unavailable | Disclose it and use the explicit manual button. Do not claim watched completion. |
| 3D stalls | Use the existing fallback or recorded simulation; preserve time for the knowledge propagation proof. |
| Backend unavailable | Switch to the labelled recording within 10–15 seconds. Never show a locally fabricated success as a persisted result. |

## 9. Questions judges are likely to ask

| Question | Accurate current answer |
| --- | --- |
| “Where is the AI actually running?” | The current runtime uses fixture data. Extraction adapters exist, but live extraction is not enabled or proven by this audit. The viva uses reviewed-content templates. Show a genuine separate extraction run only if one has been verified. |
| “Does the expert’s answer become knowledge automatically?” | The answer becomes attributed evidence. Today the UI needs an explicit manual field correction as well; automatic reviewed field mapping is missing. |
| “Can AI publish something unsafe?” | The demonstrated Studio route requires human authorization and supported fields. Structural evidence checks do not establish technical truth. The legacy reviewer path is a known separate authority that needs policy consolidation. |
| “Does every course change alter the assessment?” | All published fields affect the source brief/hash. The current three graded answers cover selected first action/decision/exception units; full coverage mapping is missing. |
| “Does it understand what the apprentice did wrong?” | The simulation records and scores authored actions. The viva displays attempt context but currently does not adapt its script to those mistakes. |
| “Is the 3D model a physical simulation?” | No. It is an authored procedural and judgment exercise; it does not establish torque, fit, force or practical certification. |
| “Is this ready for enterprise users?” | The demo has useful revision, evidence and release foundations. Real identity, complete governance, historical reporting and deployment hardening remain. |

## 10. Final release gate for the presentation

**Go:** a rehearsed, honest, prepared demonstration of one bearing knowledge correction flowing through Studio authorization into the course and structured viva, with explicit manual shortcuts and a recording fallback.

**No-go without further work:** claiming live end-to-end extraction from the UI; claiming universal admin-enforced publication; relying on full demo reset to clear learner records; claiming adaptive/spoken AI assessment; or attempting a full assembly plus the entire governance story inside three minutes.

The best use of remaining time is to repair trust-breaking state/governance gaps and rehearse one clear knowledge-propagation story. Additional decorative UI or more screens will not compensate for an unclear or unreliable proof.
