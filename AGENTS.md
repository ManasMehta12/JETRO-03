# AGENTS.md

Takumi: expert knowledge capture → reviewed release → apprentice training. This repo holds planning docs and the V1 backend knowledge engine.

## Layout
- `markdowns/globals/` — product concept (`Takumi_Final_Concept_and_Three_Person_Technical_Plan.docx`) and the V1 backend master prompt (`takumi_v1_backend_prompt.md`).
- `markdowns/hackathon/` — feature specs (expert studio, apprentice playground, technical viva) and `openapi/`.
- `backend/` — FastAPI + SQLite knowledge engine (tasks, drafts, clarifications, evidence, immutable releases, training pack, grounded Q&A).

## Contracts
- Canonical API contract: `markdowns/hackathon/openapi/API.doc.md`.
- `markdowns/hackathon/openapi/*.openapi.json` and `build_openapi.py` conflict with it (`/studio/*` prefixes, flat errors, `learner` role, `Idempotency-Key`). Do not implement from them and do not edit them.
- Backend contract output: `backend/contracts/` (regenerate with `scripts/export_contracts.py`). Deviations from API.doc.md are listed in `backend/docs/INTEGRATION_HANDOFF.md`.

## Ownership boundary
`backend/` is the knowledge engine only. No frontend, 3D, scenario, attempt, viva or report code here; teammates mount their own routers in `app/main.py` and reuse `get_current_user` / `require_roles` from `app/core/security.py`.

## Commands (run from `backend/`)
```sh
uv sync
uv run uvicorn app.main:app --reload --port 8000   # DB auto-created and seeded (approved_baseline)
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/demo_flow.py --base-url http://localhost:8000   # 16-step acceptance flow, needs running server
uv run python scripts/seed_demo.py --state fresh|approved_baseline
uv run python scripts/reset_demo.py --state fresh --yes
uv run python scripts/export_contracts.py
```
Python 3.11 (`.python-version`), managed by uv. Never hand-edit `uv.lock`; use `uv add`.

## Architecture rules
- Routers (`app/api/`) stay thin; logic lives in `app/services/`.
- Transactions: services mutate then `session.flush()`; only routers, the lifespan and scripts `commit()`.
- All feature flags live in `app/config.py` (`Settings`); reserved flags fail fast at startup. Core lifecycle and auth have no flags.
- Errors: raise `AppError(code, message, status, details)` → `{"error":{code,message,details}}`. Disabled features use `feature_disabled(...)` (HTTP 501). Codes are stable; see the handoff doc table.
- Illustrative demo content lives only in `app/fixtures/shaft_bearing_v1.json` and stays labelled `illustrative`. Never invent torque, tolerance or tactile claims.
- Releases are immutable (SQLite UPDATE trigger); status (`active`/`superseded`) is derived from `Task.active_release_id`.
- Q&A answers only from the active release snapshot; `qa_service` drops any claim whose evidence is not in that snapshot.
- Draft edits go through `knowledge_service.apply_field_updates` + `bump_draft` (optimistic revision check, `REVISION_CONFLICT` 409).
- AI calls go through `app/ai/base.py` `KnowledgeAIProvider`; V1 ships only `FixtureAIProvider` (Gemini is reserved for Checkpoint 5).

## Testing
- `tests/conftest.py`: `make_client(**settings_overrides)` context manager (temp SQLite DB per test, `demo_seed_state="fresh"`), `client` fixture, `auth(client, role)` helper.
- `tests/test_integration.py` runs the full 16-step flow twice; keep it green.
- Contract examples in `contracts/api-examples/` contain generated ids/timestamps; regenerating them produces id churn only.

## Docs
`backend/README.md`, `backend/docs/{INTEGRATION_HANDOFF,CHECKPOINTS,KNOWN_LIMITATIONS}.md`, `backend/IMPLEMENTATION_PLAN.md`.
