# Demo remediation and current runbook

This supersedes the operational recommendations in the [original audit](2026-10-25-demo-readiness-audit.md). The audit remains a historical record of the issues found before these changes.

## Current workflow

**One diagnosis action → source extraction → proposed patches → independent support evaluation → human review and publication → apprentice course and new interview script.**

The demo no longer requires switching between expert and administrator to authorize publication. Both public publication paths require a successful current-revision evaluation and an explicit human publish action. The stricter grant policy remains outside demo mode.

1. Start the app with `npm run dev`. Open `/studio` and keep `/` in another tab if desired.
2. Live AI agents are the default. Press **Run AI diagnosis** when credentials are configured. Without a key the live action is disabled; explicitly select **Illustrative rehearsal** in Analysis mode if needed.
3. Review the source quote, current field, proposed replacement and evaluation. Choose the patches to accept.
4. Answer outstanding expert questions in **Expert review**, mapping responses to a selected field where appropriate. Alternatively, explicitly check the option to retain unanswered prompts as unknown and defer them for the demo.
5. Select **Approve & publish changes**. Patch application, evidence creation, structural evaluation and release publication commit together. No source or draft change is published merely by running diagnosis.
6. The apprentice opens the new course automatically through a publication notification, focus refresh or ten-second visible-page check. A refresh control is also available.
7. Use the course and playground manual completion buttons if the presentation is time constrained. The viva and downloaded report explicitly identify the absence of an assessed simulation score.

Editing source notes after diagnosis disables approval until that source is diagnosed again or restored. Draft revision changes invalidate proposals. Failed live calls remain failed; they never silently switch to a recorded/rehearsal result.

## Keys and configuration

Put credentials only in `backend/.env`, then restart the backend:

```dotenv
GEMINI_API_KEY=your_key_here
STUDIO_AI_MODEL=gemini-2.5-flash
ENABLE_STUDIO_AI_ANALYSIS=true
STUDIO_AI_TIMEOUT_SECONDS=30
```

Choose a model available to the supplied account. `GEMINI_MODEL` overrides `STUDIO_AI_MODEL` when set. No API key is read or sent by frontend code. Live diagnosis sends the source notes and draft context to Gemini.

Studio source-note analysis detects the key independently of the legacy video extraction flags. There is no need to enable media upload, a processing worker or change `AI_PROVIDER` to run this button. These are separate video-processing capabilities.

The live pipeline uses three bounded model roles: source fact extraction, minimal extractive patch proposal, and independent support critique. Proposed replacement text must equal an exact quote in the submitted source. Unknown IDs, duplicate field changes, unsupported text, stale revisions and rejected critiques cannot publish.

Without a key, the interface says **Configuration required** and does not invent results. Only an explicitly selected illustrative rehearsal uses authored fixture source/proposals. Custom source analysis requires a live key. Real Gemini execution is still unverified until the supplied key is configured and rehearsed; automated tests exercise the live adapter boundary with mocks, not a billed provider call.

## Audit finding disposition

| Finding | Current status |
| --- | --- |
| A1: alternate publication authority bypassed evaluation/authorization | Fixed for the current policy: both public routes use the same fresh evidence-evaluation check; separate admin grant removed in demo mode as requested. |
| A2: clarification answer did not reach tacit fields | Fixed in the UI with explicit answer-to-field mapping through `knowledge_update`; evidence-only answers remain an explicit choice. |
| A3: reset could retain/fake learner state | Fixed: full reset clears learner enrollments, manual completions and analysis runs. Frontend reset changes nothing on backend failure and only clears exact app attempt namespaces after success. |
| A4: no simple extraction/review demo | Implemented for source notes: three live agent roles with a one-action trigger, persisted stages, proposals, evaluation and review. Video ingestion remains separate/deferred. |
| A5: course recording unavailable | Deferred by request; current manual progression and hardcoded lesson structure remain usable. |
| A6: publication changes learner context | Made explicit in UI/runbook, with automatic source refresh and source-specific browser persistence. Full historical enrollment retention remains future work. |
| A7: misleading multi-task propagation | Studio demo now explicitly targets the connected bearing task. A general course catalogue/mapping is future work. |
| A8: narrow interview coverage and misleading scoring | Reviewed answers now cover all published units; later-unit corrections change the choices. Limits scoring applies only to the actual limits item. Live/adaptive interview remains deferred and the current script is explicitly structured. |
| A9: evaluation could be mistaken for technical certification | Patch evaluation is labelled source support; technical review and publication stay human-controlled. Unknown questions require explicit disposition. |
| A10: full assembly too slow for a short pitch | One diagnosis action plus explicit manual progression is available; full assembly remains optional and assessed scores are never fabricated. |
| Refresh and stale review | Added publication notifications, periodic visible-page updates, explicit refresh, source binding and unsaved editor/answer guards. |
| Evidence/report visibility | Approved source text is available alongside the viva. Saved responses include question/selected answer and source identity. Final evaluation downloads as Markdown. |
| Venue font dependency | Removed external font imports; the professional system-font stack works offline. |
| Preflight | `npm run demo:preflight` checks current health, schema, diagnosis mode, pending questions and release without changing content. |
| Remaining production features | Real user management, tenant isolation, historical reports, grant revocation, append-only audit hardening, video-span UI and adaptive spoken assessment remain outside this demo. |

## APIs and stored state

All paths use `/api/v1/studio/tasks/task_001/analysis`:

| Method/path | Purpose |
| --- | --- |
| `GET /config` | Enabled state, live/rehearsal mode, model label and included source notes. No secrets. |
| `POST` | `{expected_revision, source_notes?}` starts bounded diagnosis. The request returns the completed or failed persisted run; GET endpoints expose actual stages while it runs. |
| `GET /latest` | Last run, proposals, phase, evaluation and any failure; reload can recover the review UI. |
| `GET /{run_id}` | Inspect a particular run. |
| `POST /{run_id}/publish` | `{expected_revision, proposal_ids, approval_note, defer_unanswered}` explicitly reviews/applies/evaluates/publishes selected proposals. |

`studio_analysis_runs` is added in schema 6. Provider calls happen outside database transactions. Three calls have a default 30-second timeout each; this is not an asynchronous durable worker queue. Server startup marks interrupted runs failed and retryable. Errors are persisted without switching modes. A completed run with no patches is a valid “no changes needed” result.

## Short judges’ demo

| Time | Action |
| --- | --- |
| 0:00–0:20 | State the problem; show the missing tacit field and its expert source. |
| 0:20–1:10 | Run diagnosis; show mode, source extraction, patch and evaluation. Live latency depends on the configured model; rehearse it before choosing this time budget. |
| 1:10–1:35 | Review, explicitly retain unknowns if needed, and approve publication. |
| 1:35–2:00 | Show the exact new guidance and release version in the apprentice course. |
| 2:00–2:25 | Show one inspection/assembly action and use clearly labelled manual progression. |
| 2:25–3:00 | Start a new viva, show the updated source/answer, and display or download the result if time permits. |

For a keyless demonstration, say that this is an authored rehearsal. Do not call it a live AI run. For live mode, allow enough time for three model calls and keep a labelled successful recording available. No live interview or course-video claim is necessary for this demonstration.

Publish before preparing the learner result: each release starts a new current progression context. Learner reset preserves published knowledge. Full fixture reset is destructive; use it only intentionally between rehearsals, then reload the browser. The existing reset script is `uv run python scripts/reset_demo.py --state approved_baseline --yes` from `backend/`; it is not part of automatic startup or preflight.

## Verification

- 63 targeted backend tests passed, including source-grounded proposal validation, live failures without fallback, provider calls outside database transactions, explicit approval, stale revisions, publication policy, resets, full-unit interview coverage and source propagation.
- 33 frontend unit tests passed.
- 11 browser checks passed, covering diagnosis-to-apprentice/viva/report, clarification mapping, failed and successful reset/reload, native video progression, desktop layout and mobile manual completion.
- Production build passed. The existing large lazy 3D chunk advisory remains.
- `demo:preflight` passed against the restarted local schema-6 backend in labelled rehearsal mode.
- A final focused browser check verifies that editing source notes invalidates approval; real Gemini execution awaits credentials.

The original audit and its isolated repro artifacts are retained for comparison; they are not the current implementation status.
