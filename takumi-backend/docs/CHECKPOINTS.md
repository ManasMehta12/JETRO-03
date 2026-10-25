# Checkpoint reports

V2 media and Gemini extraction reports: [V2_CHECKPOINTS.md](V2_CHECKPOINTS.md). Reports below record historical V1 checkpoints.

## CP0 — Bootstrap, configuration and fixture seed

**Checkpoint completed:** CP0; commit `137154a` (`feat(backend): bootstrap FastAPI app, config, auth, fixture seed (CP0)`).

**Implemented:** FastAPI factory, SQLite initialization/schema guard/immutable-release trigger, typed settings, signed demo auth, health, error envelope, deterministic fixture seed and gaps.

**Verified:** Historical checkpoint commit is present in `git log -4 --format='%h %s'`. Current regression proof lives in `tests/test_config.py` and `tests/test_seed.py`. This report does not claim a historical command was rerun independently.

**Flags:** Fixture mode and demo auth/seed/reset active; reserved live/media flags false.

**API changes:** HTTP 501 FEATURE_DISABLED added; no optional core-lifecycle/auth flags.

**Blocked:** None for V1.

**Remaining:** Production identity and reserved media/live checkpoints excluded.

**Integration readiness:** Health, demo tokens and seeded fixture available.

## CP1 — Versioned knowledge loop

**Checkpoint completed:** CP1; commit `cc2a3e2` (`feat(backend): knowledge drafts, clarifications, evidence (CP1)`).

**Implemented:** Task CRUD subset, revision-checked draft corrections, clarification dispositions and evidence provenance, atomic field-evidence updates, role-filtered reads.

**Verified:** Commit found through the same git-log command. Regression proof: `tests/test_tasks.py`, `tests/test_drafts.py`, `tests/test_clarifications.py`, `tests/test_evidence.py`. CP3 live flow also proved a new expert explanation persists and appears in per-field evidence.

**Flags:** Core lifecycle and auth always active.

**API changes:** Additive revisions and provenance; draft review_status stays draft.

**Blocked:** None.

**Remaining:** Media extraction excluded.

**Integration readiness:** Studio clients can read/edit seeded drafts and submit expert explanations.

## CP2 — Immutable releases and grounded Q&A

**Checkpoint completed:** CP2; commit `7441e01` (`feat(backend): immutable releases, training pack, grounded Q&A (CP2)`).

**Implemented:** Reviewer publish-as-approval, immutable release/evidence snapshots, training-pack export and deterministic source-grounded Q&A.

**Verified:** Commit found through git log. Regression proof: `tests/test_publication.py`, `tests/test_training_pack.py`, `tests/test_qa.py`. CP3 live flow verified citation to newly submitted expert evidence, unsupported torque abstention and 405 on release edits.

**Flags:** ENABLE_GROUNDED_QA and ENABLE_TRAINING_PACK_EXPORT true; live Q&A false.

**API changes:** Derived active/superseded status; publish retries return 200; release-by-id and training-pack routes added.

**Blocked:** None for fixture mode; Gemini intentionally unavailable.

**Remaining:** Live models and semantic retrieval excluded.

**Integration readiness:** Simulation clients can pin a release and consume its training pack without database access.

## CP3 — Baseline/reset, contracts and end-to-end integration

**Checkpoint completed:** CP3 implementation and focused/live proof completed in this run.

**Implemented:** Startup approved_baseline through real services; transactional fixture-only reset; seed/reset/demo/export scripts; repeatable integration test; generated OpenAPI, four JSON schemas and 16 API examples; environment template and teammate documentation.

**Verified:** Commands actually executed from `backend/`:

- `uv sync` — dependencies resolved and installed packages checked.
- `cp .env.example .env` — development environment copied (ignored by git).
- `uv run pytest tests/test_demo.py tests/test_integration.py` — 9 passed, including two complete flows in one test.
- `uv run python scripts/export_contracts.py` — exported OpenAPI, four schemas and 16 API examples.
- `DATABASE_URL=sqlite:////tmp/takumi-wave3.db uv run uvicorn app.main:app --port 8765` — isolated fresh server served requests. Before reset, apprentice read `release_001` with status active.
- `uv run python scripts/demo_flow.py --base-url http://localhost:8765` — 16 OK lines, exit 0. Verified expert answer → evidence → approved release → claim with that new evidence ID; unsupported torque abstained.
- `DATABASE_URL=sqlite:////tmp/takumi-wave3-readme.db uv run uvicorn app.main:app --reload --port 8000` — documented reload command served health 200.
- With that isolated DATABASE_URL, `uv run python scripts/seed_demo.py --state approved_baseline` — exit 0, already present; nothing changed.
- With that isolated DATABASE_URL, `uv run python scripts/reset_demo.py --state fresh --yes` — exit 0, reset to fresh.
- `uv run ruff format app/services/seed_service.py app/api/demo.py scripts tests/test_demo.py tests/test_integration.py tests/test_seed.py` — owned files formatted.

- `uv run pytest -q` — 87 passed, one upstream TestClient deprecation warning.
- `uv run ruff check .` — found one E501 in the reset error message. Split the literal without changing its value.
- `uv run ruff format --check .` — 58 files already formatted, exit 0 (before that literal-only lint fix).
- `uv run ruff check app/api/demo.py` — clean after the literal-only lint fix. Orchestrator owns the final full-suite recheck.

Both live servers were stopped and their temporary databases removed. The service-readiness tool timed out despite working servers; actual HTTP requests and demo CLI supplied the proof. TestClient emitted an upstream httpx deprecation warning; no test failure resulted.

**Flags:** Default DEMO_SEED_STATE is approved_baseline. Fixture/demo/Q&A/export active. Reserved capabilities remain disabled; no new capability flag introduced.

**API changes:** Confirmed reviewer reset adds state; attempts scope returns 400. Handoff lists the complete stable error table and canonical/generated-spec conflicts.

**Blocked:** None for Checkpoints 0–3.

**Remaining:** Scenario/attempt/viva/report, frontend, Gemini, media, production auth and advanced retrieval intentionally excluded. Root AGENTS.md and checkpoint commit belong to the orchestrator.

**Integration readiness:** Frontend can authenticate and complete Studio lifecycle. Simulation can retrieve active release_001 immediately, pin its training pack, resolve evidence and ask grounded questions. Reset-to-fresh enables a live expert demonstration.
