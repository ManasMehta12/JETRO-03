# Stack
Python 3.11+, FastAPI, Pydantic settings, SQLAlchemy 2.x, SQLite, uv, pytest, Ruff.

# Key decisions
- Core lifecycle and auth are always enforced; no core-lifecycle feature flags.
- Publish = approval; drafts remain draft and release status is derived from the active pointer.
- Gemini is interface only. Reserved live/media flags fail at startup.
- FEATURE_DISABLED returns 501; HMAC demo tokens use a process key unless a secret is supplied.
- Baseline auto-seed arrives in CP3; CP0 seeds fresh fixture data without overwriting edits.
- Services never call commit(). They mutate, then session.flush().
- Routers, lifespan and scripts own commit()/rollback().
- Immutable release snapshots ground Q&A; fixture content is explicitly illustrative.

# Checkpoints 0–3 exit criteria
- CP0: app boots, health and OpenAPI respond, config/auth/fixture tests pass.
- CP1: expert clarification creates evidence and updates the versioned draft atomically.
- CP2: reviewer publishes immutable releases; grounded Q&A and training-pack export pass.
- CP3: baseline/reset, reproducible demo flow, contracts and integration docs pass.

# Contract deviations
- Additive provenance and revision fields; release status derives from the active pointer.
- Publish retries return 200; publishing approves every unit without a per-unit review step.
- Reset adds state; attempts scope returns 400 because the scenario engine owns it.
- Adds GET /releases/{id} and GET /releases/{id}/training-pack.
- Reserved media/process/jobs/stream return 501 FEATURE_DISABLED (additional HTTP status).
- CP3 auto-seeds approved_baseline/release_001; reset to fresh before a live expert demo.
- Scenario/attempt/viva/report routes belong to teammates and are not served here.
- API.doc.md wins over generated OpenAPI: no /studio prefix, flat errors, learner role,
  or Idempotency-Key convention.
- Task reads omit media/processing fields until Checkpoint 4.
