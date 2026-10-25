# TAKUMI V1 — Backend & AI Knowledge Engine
## Autonomous Coding Agent: Master Implementation Prompt

**Project:** Takumi — Expert Knowledge Capture & Digital Apprenticeship  
**Challenge:** JETRO PS-03, Japan Hackathon 2026  
**Implementation:** Version 1 — Backend and AI Knowledge Pipeline  
**Development strategy:** Hardcode first, validate contracts, enable capabilities incrementally  
**Primary objective:** Build a reliable backend that other developers can integrate immediately.

---

# 0. YOUR ROLE

You are a senior backend engineer, AI engineer, and software architect responsible for implementing the **Takumi Knowledge Engine**.

You are working as part of a three-person development team.

Other developers are independently building:

- The frontend and Expert Studio interface.
- The 3D Apprentice Playground, scenario engine, and technical viva integration.

**Your responsibility is exclusively the non-frontend, non-simulation backend.**

You own:

1. FastAPI application and API contracts.
2. Task management.
3. Persistent data models.
4. Knowledge extraction pipeline.
5. Knowledge-gap detection.
6. Expert clarification management.
7. Evidence attribution and validation.
8. Review and publication workflow.
9. Immutable approved knowledge releases.
10. Evidence-grounded Q&A.
11. AI provider abstraction.
12. Seeded/demo processing.
13. Authentication and basic authorization.
14. Media and processing infrastructure when enabled.
15. Testing, documentation, and integration fixtures.
16. Approved knowledge exports for the simulation developer.

You do NOT own:

- React or Next.js application.
- Frontend components.
- 3D rendering.
- Assembly geometry.
- Scenario scoring.
- Simulation state transitions.
- Learner interaction logic.
- Viva user interface.
- Automated industrial physics.

Do not implement another developer's subsystem.

Your most important deliverable is a stable, tested API that exposes approved knowledge and evidence for the rest of the application.

---

# 1. CORE ENGINEERING PHILOSOPHY

This is a time-constrained hackathon.

**Prefer a complete, working, deterministic implementation over an ambitious but unreliable system.**

Follow these principles.

## 1.1 Hardcoding is allowed and encouraged where appropriate

For V1, you may hardcode:

- Initial task data.
- Demonstration knowledge units.
- Sample video metadata.
- Gap-detection priority weights.
- Three clarification questions.
- Example expert answers in demo fixtures.
- Q&A intent patterns and canned response templates.
- Training-task terminology.
- Fixture IDs where stable IDs aid integration.
- Demo user identities.
- Small knowledge-release templates.

However, hardcoded content must be centralized, versioned, and clearly marked as illustrative.

Do not scatter business-specific hardcoded strings across routers and services.

## 1.2 Never fake important state

The following must genuinely work:

- Database persistence.
- Creating and editing knowledge.
- Saving expert clarification responses.
- Assigning evidence IDs.
- Updating draft revisions.
- Reviewer approvals.
- Publication of immutable releases.
- Retrieving approved releases.
- Authorization checks.
- Returning evidence-grounded answers.
- Handling invalid requests.
- Rejecting unsupported knowledge.

A hardcoded extraction result is acceptable.

A fake publish button represented by an API that returns success without storing a release is not acceptable.

## 1.3 Feature flags control complexity

Optional capabilities must be enabled through configuration, without rewriting existing business logic.

All feature flags should be defined centrally.

Default configuration should be the most reliable mode.

## 1.4 Implement working vertical slices

Do not implement twenty empty endpoints.

Build a small number of fully functioning endpoints, test them, then expand.

## 1.5 Follow the existing API contract

Use the previously agreed **Takumi API Specification v1.0** as the canonical interface if it is available in the repository.

Preserve its route names, field names, IDs, HTTP semantics, and state conventions unless a real contradiction exists.

If the contract must change:

1. Document the change.
2. Update the OpenAPI schema.
3. Update JSON examples.
4. Add a compatibility note.
5. Inform downstream developers through `docs/INTEGRATION_HANDOFF.md`.

Do not silently rename fields.

---

# 2. INITIAL REPOSITORY WORK

Before implementing anything:

1. Inspect the repository.
2. Identify existing backend code.
3. Inspect `pyproject.toml`, requirements, environment files, and configuration.
4. Look for existing API contracts or shared schemas.
5. Identify files owned by the other developers.
6. Check current official documentation for the dependencies you actually need.
7. Determine whether an existing implementation can be reused.

Do not overwrite working frontend or simulator code.

If there is no backend, create a standalone `backend/` directory.

Create:

- `backend/IMPLEMENTATION_PLAN.md`
- `backend/README.md`
- `backend/.env.example`
- `backend/docs/INTEGRATION_HANDOFF.md`

The implementation plan should be concise and practical.

Record major decisions, dependencies, assumptions, and checkpoints.

After planning, begin implementation immediately.

**Do not stop after preparing the plan.**

---

# 3. RECOMMENDED STACK

Use:

- Python 3.11+.
- FastAPI.
- Pydantic v2.
- pydantic-settings.
- SQLAlchemy 2.x.
- SQLite.
- Uvicorn.
- pytest.
- HTTPX / FastAPI TestClient.
- Ruff for linting and formatting.
- `google-genai` for optional Gemini integration.

Use the current stable releases compatible with the project.

Pin dependency versions in a lockfile or reproducible requirements file.

Use `uv` for dependency management if it is already available; otherwise provide standard `pip` commands.

## Not required for V1

Do not introduce:

- Redis.
- Celery.
- Kafka.
- PostgreSQL.
- pgvector.
- LangChain.
- LangGraph.
- Vector databases.
- Graph databases.
- Docker orchestration.
- Complex event buses.
- Microservices.
- Distributed tracing infrastructure.

These add complexity without helping prove the core workflow.

A small FastAPI application and SQLite database are sufficient for the first implementation.

---

# 4. PROJECT STRUCTURE

Prefer a structure similar to:

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── tasks.py
│   │   ├── drafts.py
│   │   ├── clarifications.py
│   │   ├── releases.py
│   │   ├── evidence.py
│   │   ├── qa.py
│   │   ├── media.py
│   │   └── demo.py
│   │
│   ├── models/
│   │   ├── entities.py
│   │   └── schemas.py
│   │
│   ├── services/
│   │   ├── task_service.py
│   │   ├── knowledge_service.py
│   │   ├── clarification_service.py
│   │   ├── evidence_service.py
│   │   ├── publication_service.py
│   │   ├── qa_service.py
│   │   └── training_pack_service.py
│   │
│   ├── ai/
│   │   ├── base.py
│   │   ├── fixture_provider.py
│   │   ├── gemini_provider.py
│   │   ├── prompts.py
│   │   └── schemas.py
│   │
│   ├── processing/
│   │   ├── jobs.py
│   │   └── worker.py
│   │
│   ├── fixtures/
│   │   └── shaft_bearing_v1.json
│   │
│   └── core/
│       ├── security.py
│       ├── errors.py
│       └── logging.py
│
├── tests/
│   ├── conftest.py
│   ├── test_tasks.py
│   ├── test_clarifications.py
│   ├── test_evidence.py
│   ├── test_publication.py
│   ├── test_qa.py
│   ├── test_feature_flags.py
│   └── test_integration.py
│
├── contracts/
│   ├── knowledge-unit.json
│   ├── clarification.json
│   ├── release.json
│   ├── training-pack.json
│   └── api-examples/
│
├── docs/
│   ├── API.md
│   ├── CHECKPOINTS.md
│   ├── INTEGRATION_HANDOFF.md
│   └── KNOWN_LIMITATIONS.md
│
├── scripts/
│   ├── seed_demo.py
│   ├── reset_demo.py
│   └── export_openapi.py
│
├── .env.example
├── pyproject.toml
├── README.md
└── IMPLEMENTATION_PLAN.md
```

This is a suggested structure, not a requirement to create empty files.

Prefer fewer meaningful modules over unnecessary abstraction.

Routers should remain thin.

Business logic belongs in services.

Database concerns belong in persistence code.

AI-specific code belongs behind provider interfaces.

---

# 5. FEATURE FLAG SYSTEM

Implement feature flags through Pydantic settings and environment variables.

Use a centralized, typed configuration object.

Do not read environment variables directly throughout the codebase.

## 5.1 Default configuration

Create `.env.example` with settings similar to:

```dotenv
APP_NAME=Takumi Knowledge Engine
APP_ENV=development

DATABASE_URL=sqlite:///./data/takumi.db

# Demo configuration
DEMO_MODE=true
ENABLE_DEMO_AUTH=true
ENABLE_DEMO_SEED=true
ENABLE_DEMO_RESET=true

# Core features
ENABLE_TASK_API=true
ENABLE_KNOWLEDGE_EDITING=true
ENABLE_EXPERT_CLARIFICATION=true
ENABLE_KNOWLEDGE_PUBLICATION=true
ENABLE_EVIDENCE_API=true
ENABLE_TRAINING_PACK_EXPORT=true
ENABLE_GROUNDED_QA=true

# Authentication
ENABLE_AUTH_ENFORCEMENT=true
DEMO_SIGNING_SECRET=
DEMO_TOKEN_TTL_MINUTES=480

# AI
AI_PROVIDER=fixture
ENABLE_LIVE_EXTRACTION=false
ENABLE_LIVE_GAP_GENERATION=false
ENABLE_LIVE_QA=false
GEMINI_API_KEY=
GEMINI_MODEL=

# Media
ENABLE_MEDIA_UPLOAD=false
ENABLE_MEDIA_PROCESSING=false
ENABLE_MEDIA_STREAMING=false
MAX_UPLOAD_MB=100
MAX_VIDEO_DURATION_SECONDS=240

# Processing
ENABLE_PROCESSING_WORKER=false
PROCESSING_MAX_RETRIES=2

# Optional capabilities
ENABLE_MULTILINGUAL=false
ENABLE_EMBEDDINGS=false
ENABLE_ADVANCED_RETRIEVAL=false

# Observability
LOG_LEVEL=INFO
LOG_MODEL_INPUTS=false

# Network configuration
CORS_ORIGINS=http://localhost:3000
```

The signing secret must be supplied securely at runtime or generated for a development session. Never ship a reusable hardcoded secret.

## 5.2 Rules for feature flags

Every optional feature must have:

1. A clearly named flag.
2. A safe default.
3. An explicit enabled path.
4. An explicit disabled path.
5. At least one test confirming disabled behavior.
6. Documentation describing what the flag does.

Disabled functionality must not silently pretend to work.

For example:

- If live extraction is disabled, use a labelled known fixture when explicitly requested.
- If an unsupported new video is submitted for fixture-only processing, return a meaningful error.
- If Gemini is unavailable, preserve existing approved releases.
- If media processing is disabled, do not enqueue imaginary jobs.
- If Q&A is enabled in fixture mode, return only supported fixture answers.

Avoid creating flags for every individual function.

Feature flags should correspond to meaningful product capabilities.

## 5.3 Feature flag precedence

Use the following approach:

**Demo mode** permits fixtures and controlled reset operations.

**AI provider selection** determines which provider is available.

**Live capability flags** explicitly permit provider calls.

**Core publication rules** must never be bypassed by demo flags.

For example, even in demo mode, an apprentice must not be allowed to publish knowledge.

## 5.4 Fail-fast configuration validation

Reject invalid combinations at startup or at the relevant boundary.

Examples:

- Live AI enabled without an API key.
- Demo login enabled in production.
- Demo reset enabled in production.
- An invalid configured model name.
- A media-processing worker enabled without its required storage configuration.

Do not accidentally fail startup when optional disabled features lack credentials.

---

# 6. DATA MODEL

V1 should implement a minimal persistent domain model.

Favor SQLAlchemy entities with JSON columns where appropriate.

Avoid constructing an elaborate enterprise schema.

## 6.1 Task

Fields:

```text
id
title
equipment
description
language
owner_id
status
active_release_id
created_at
updated_at
```

Initially support one organization or workspace.

Design identifiers so organization ownership can be added without breaking the external contract.

## 6.2 DraftVersion

```text
id
task_id
revision
status
knowledge_units
created_at
updated_at
```

`knowledge_units` may be stored as validated JSON for V1.

A draft is mutable through explicit revision-checked operations.

Published releases are not.

## 6.3 KnowledgeUnit

The required structure is:

```json
{
  "id": "ku_001",
  "action": "Inspect the bearing housing",
  "cue": null,
  "interpretation": null,
  "decision": null,
  "exception": null,
  "evidence_ids": ["ev_001"],
  "field_evidence": {
    "action": ["ev_001"]
  },
  "review_status": "draft"
}
```

Preserve the six conceptual fields:

**Action → Cue → Interpretation → Decision → Exception → Evidence**

Unknown information must remain `null`.

Never convert unknown information into model-generated certainty.

## 6.4 EvidenceItem

```text
id
task_id
type
author_id
author_label
content
media_id
start_ms
end_ms
source_label
created_at
```

Evidence types:

- `video_segment`
- `expert_response`
- `reviewer_correction`

Source labels:

- `real`
- `illustrative`

For video intervals:

```text
0 <= start_ms < end_ms <= media_duration_ms
```

Validate this when media duration is known.

Fixture-only evidence without a real media source must not invent a playable source URL.

## 6.5 Clarification

```text
id
task_id
draft_id
knowledge_unit_id
question
gap_type
priority
status
answer
evidence_id
created_at
answered_at
```

The expert's answer must be persisted separately from the AI-generated question.

## 6.6 Release

```text
id
task_id
version
content_hash
approved_by
approved_at
knowledge_snapshot
evidence_snapshot
status
```

Published releases are immutable snapshots.

Do not modify historical release contents.

## 6.7 ProcessingJob

Implement the model only when needed, but reserve its contract.

```text
id
task_id
media_id
input_hash
status
stage
attempt_count
error
result_draft_id
created_at
updated_at
```

## 6.8 Schema best practices

Use:

- Unique constraints where required.
- Foreign keys.
- Database transactions.
- UTC timestamps.
- Pydantic validation at API boundaries.
- Optimistic revision checks.
- Stable opaque IDs.
- Explicit nullability.

For SQLite:

- Enable foreign-key enforcement for connections.
- Configure a reasonable busy timeout.
- Keep write transactions short.
- Use a file-backed database for application persistence.
- Do not assume SQLite supports high-concurrency distributed workloads.

Use Alembic only if schema changes are already becoming painful. For a new V1, a deterministic initialization mechanism plus a clearly documented schema version can be sufficient.

Never silently destroy existing data on startup.

---

# 7. SEED DATA — CRITICAL V1 REQUIREMENT

Create one comprehensive fixture:

`app/fixtures/shaft_bearing_v1.json`

This is the heart of V1.

The backend must be fully demonstrable without any Gemini API calls.

## 7.1 Task fixture

Create an illustrative task:

```json
{
  "id": "task_001",
  "title": "Shaft and Bearing Inspection",
  "equipment": "Unpowered Shaft-and-Bearing Bench Assembly",
  "language": "en",
  "source_label": "illustrative"
}
```

## 7.2 Initial draft

Provide approximately three or four knowledge units.

One unit should have:

- An observable action.
- A source reference where one genuinely exists.
- Missing interpretation.
- Missing decision reasoning.

Example:

```json
{
  "id": "ku_001",
  "action": "Inspect the bearing housing",
  "cue": null,
  "interpretation": null,
  "decision": null,
  "exception": null,
  "evidence_ids": [],
  "field_evidence": {},
  "review_status": "draft"
}
```

This is illustrative content, not a validated mechanical procedure.

Use another unit with more complete information to test different retrieval cases.

## 7.3 Clarification fixtures

Seed three questions of different types:

1. Missing reasoning.
2. Changed-condition reasoning.
3. Beginner mistake or escalation.

Questions should be sufficiently specific to demonstrate why expert knowledge matters.

## 7.4 Example expert responses

Seed illustrative example answers separately.

Do not automatically mark them as genuine responses from an actual expert.

The real clarification endpoint must also accept arbitrary typed responses and save them.

## 7.5 Two fixture states

Support two useful demo states:

**Fresh state**

- Task exists.
- Draft exists.
- Clarification remains unanswered.
- No new expert response has been approved.

**Approved baseline state**

- Illustrative responses exist.
- Release exists.
- Approved knowledge is available.
- Q&A can return supported sample answers.

The reset mechanism should allow restoring these states explicitly.

## 7.6 Idempotent seeding

Running the seed script twice must not duplicate tasks, clarifications, releases, or evidence.

Use stable fixture identifiers and upsert/skip logic as appropriate.

Never overwrite genuine user-authored content during ordinary startup seeding.

---

# 8. API OWNERSHIP AND ENDPOINTS

All routes use:

`/api/v1`

You own the following APIs.

## 8.1 Infrastructure and demo

```text
GET  /health
POST /auth/demo-login
POST /demo/reset
```

`GET /health` must report actual service health.

Do not include secrets.

Demo login must issue a server-signed, expiring token and establish a server-validated role.

Demo reset must be disabled outside demo mode.

It should support:

- Reset learner-related demo data only, via coordination with the simulation team.
- Reset the backend knowledge demo to its initial fixture state.

Do not delete another developer's data without an agreed reset interface.

## 8.2 Tasks

```text
GET  /tasks
POST /tasks
GET  /tasks/{id}
```

Implement actual database persistence.

Task creation must not require an AI call.

## 8.3 Drafts

```text
GET   /tasks/{id}/draft
PATCH /tasks/{id}/draft
```

Implement revision-checked editing.

Request shape:

```json
{
  "expected_revision": 1,
  "changes": [
    {
      "knowledge_unit_id": "ku_001",
      "fields": {
        "action": "Corrected action description"
      }
    }
  ]
}
```

Return the incremented revision.

On a revision mismatch, return HTTP 409 with a stable error code.

Do not allow arbitrary fields or evidence IDs to be injected.

## 8.4 Clarifications

```text
POST /clarifications/{id}/respond
```

Request:

```json
{
  "expected_draft_revision": 2,
  "disposition": "answered",
  "answer": "Explanation provided by the expert",
  "knowledge_update": {
    "knowledge_unit_id": "ku_001",
    "fields": {
      "cue": "Expert-supplied observation",
      "interpretation": "Expert-supplied interpretation",
      "decision": "Expert-supplied decision"
    }
  }
}
```

Allowed dispositions:

- `answered`
- `premise_rejected`
- `unobservable`
- `deferred`

For answered clarifications:

1. Validate the draft revision.
2. Save the answer.
3. Create an attributed evidence item.
4. Apply allowed knowledge field updates.
5. Link updated fields to the new evidence item.
6. Increment the draft revision.
7. Commit the operation transactionally.

The answer and knowledge update must not be partially persisted.

If the question premise is rejected, preserve that rejection rather than forcing a fabricated answer.

## 8.5 Publication

```text
POST /tasks/{id}/publish
```

Only reviewers may publish.

Request:

```json
{
  "expected_revision": 3,
  "approval_note": "Reviewed for the training demonstration."
}
```

Publication must:

1. Validate authorization.
2. Check the draft revision.
3. Validate all required evidence references.
4. Check required knowledge fields or documented exceptions.
5. Create an immutable snapshot.
6. Compute and store a content hash.
7. Advance the release version.
8. Update the active release pointer.
9. Commit atomically.

Do not accept client-supplied approval identity.

Derive it from the authenticated session.

Return the new release ID.

## 8.6 Releases

```text
GET /tasks/{id}/release
GET /releases/{release_id}
```

The first endpoint retrieves the active release.

The second retrieves a specific immutable release by ID.

The version-specific endpoint is useful because the simulation developer needs to bind attempts to the exact knowledge release used during training.

No draft content should leak into these responses.

## 8.7 Evidence

```text
GET /evidence/{id}
```

Return the source evidence and attribution.

Verify that the authenticated user can access the evidence's task.

For video evidence, provide a media reference and timestamp only when a valid source is available.

## 8.8 Grounded Q&A

```text
POST /tasks/{id}/ask
```

The endpoint must work without an LLM in V1.

Input:

```json
{
  "question": "Why did the expert perform this check?",
  "language": "en"
}
```

Output:

```json
{
  "status": "answered",
  "release_id": "release_001",
  "claims": [
    {
      "text": "Approved explanation from the knowledge pack",
      "knowledge_unit_id": "ku_001",
      "evidence_ids": ["ev_002"]
    }
  ],
  "missing_information": [],
  "review_required": false
}
```

Allowed statuses:

- `answered`
- `needs_context`
- `insufficient_evidence`

The release ID must be resolved server-side.

Do not allow client-supplied knowledge to replace approved knowledge.

---

# 9. TRAINING PACK EXPORT — TEAM INTEGRATION CONTRACT

Implement:

```text
GET /releases/{release_id}/training-pack
```

This is the primary integration boundary with the simulation and frontend developers.

The endpoint must return an approved, versioned, self-contained knowledge package.

Example:

```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "release_id": "release_001",
  "version": 1,
  "equipment": "Unpowered shaft-and-bearing assembly",
  "language": "en",
  "source_label": "illustrative",
  "knowledge_units": [
    {
      "id": "ku_001",
      "action": "Inspect the bearing housing",
      "cue": "Approved observation",
      "interpretation": "Approved explanation",
      "decision": "Approved decision",
      "exception": null,
      "evidence_ids": ["ev_002"],
      "field_evidence": {
        "cue": ["ev_002"],
        "interpretation": ["ev_002"],
        "decision": ["ev_002"]
      }
    }
  ],
  "evidence_items": [
    {
      "id": "ev_002",
      "type": "expert_response",
      "author": "Demo Expert",
      "content": "Illustrative clarification",
      "source_label": "illustrative"
    }
  ]
}
```

All text and evidence identifiers shown above are examples, not validated mechanical guidance.

## Training-pack invariants

1. The release is approved.
2. The release ID is immutable.
3. Every knowledge unit belongs to that release.
4. Every evidence ID resolves to approved evidence in that release.
5. Unknown fields remain unknown.
6. No hidden assessment rules are included.
7. The response shape is stable.
8. The schema version is explicit.

The simulation developer may hardcode scenario logic against these knowledge-unit IDs.

**Do not build their scenario engine.**

Your job is to provide the data contract that makes the integration possible.

## Optional readiness validation

If useful, provide a pure backend function:

```python
validate_required_knowledge(
    release_id: str,
    required_knowledge_ids: list[str]
) -> ValidationResult
```

This function can tell the simulation team whether a release contains the approved knowledge required by an authored scenario.

Do not use it to publish or evaluate scenarios.

---

# 10. KNOWLEDGE-GAP DETECTION

V1 should use deterministic rules.

Do not require an LLM to identify the three demonstration questions.

## 10.1 Detect missing fields

Given a knowledge unit, inspect:

- Cue.
- Interpretation.
- Decision.
- Exception.

Missing interpretation or decision reasoning should usually be more important than a missing cosmetic description.

## 10.2 Rank gaps

Use a transparent heuristic.

Example:

```text
priority =
    decision_importance
    + missing_reasoning_weight
    + novice_confusion_weight
```

Weights can be hardcoded in a single configuration module.

The score is only a prioritization heuristic.

It is not model confidence or a measured educational risk.

## 10.3 Question generation

For V1, map gap categories to predefined question templates.

Examples:

**Missing reasoning**

"What observation caused you to choose this action?"

**Changed condition**

"What would make you change your next decision?"

**Beginner mistake**

"What mistake could a beginner make here, and how would you recognize it?"

Customize templates using available task information.

Avoid awkward or misleading interpolations.

If there is insufficient context, use a general, neutral question.

Select a maximum of three useful questions.

## 10.4 Provider abstraction

Keep question generation behind an interface so LLM-powered generation can replace templates later.

Do not require a separate implementation of the entire knowledge pipeline when changing providers.

---

# 11. AI PROVIDER ABSTRACTION

Implement the interface early, even though V1 defaults to fixtures.

Suggested interface:

```python
from typing import Protocol

class KnowledgeAIProvider(Protocol):

    def extract_knowledge(
        self,
        media_reference,
        task_context
    ):
        ...

    def generate_clarifications(
        self,
        draft
    ):
        ...

    def answer_question(
        self,
        question,
        approved_context
    ):
        ...
```

Use precise Pydantic request and response types in the actual implementation.

Do not create an unnecessarily complex agent framework.

## 11.1 Fixture provider

Implement:

`FixtureAIProvider`

Responsibilities:

- Load known fixture results.
- Return validated structures.
- Support deterministic tests.
- Require no network calls.
- Return explicit fixture provenance.
- Reject unsupported arbitrary-media processing.

Example:

```python
provider = get_ai_provider(settings)
result = provider.extract_knowledge(
    media_reference,
    task_context
)
```

When `AI_PROVIDER=fixture`, the configured demo workflow must work even when `GEMINI_API_KEY` is absent.

## 11.2 Gemini provider

Implement a clean, gated adapter:

`GeminiAIProvider`

For V1, it may be disabled by default.

Use the supported Google GenAI SDK and verify the current API surface before implementing live requests.

Keep:

- Model identifier configurable.
- Extraction prompt versioned.
- Structured response parsing centralized.
- API key server-side only.
- Provider errors normalized.
- Input/output schemas identical to the fixture provider.

Do not hardcode an unverified model identifier.

## 11.3 Output validation

Every model response must pass Pydantic validation.

Also validate semantic constraints:

- Knowledge unit IDs.
- Evidence references.
- Allowed source intervals.
- Known task ownership.
- Missing values.
- Duplicate IDs.
- Unsupported certainty claims.

Structured JSON does not imply factual accuracy.

## 11.4 AI provenance

Store or log relevant processing metadata:

```text
provider
model_id
prompt_version
processing_stage
started_at
completed_at
status
```

If usage information is available, record it.

Do not expose secrets or raw confidential media in logs.

---

# 12. MEDIA PIPELINE — DISABLED INITIALLY

Keep live media features behind flags.

Reserve the agreed API routes:

```text
POST /tasks/{id}/media
POST /tasks/{id}/process
GET  /jobs/{id}
GET  /media/{id}/stream
```

Do not spend significant V1 effort building multimedia infrastructure before the knowledge lifecycle works.

## When media upload is enabled

Validate:

- File size.
- Allowed format.
- Actual media type.
- Media duration where tools are available.
- Safe storage location.
- Authorized access.

Store a checksum.

Never use the original uploaded filename directly as a trusted filesystem path.

## When media processing is enabled

Implement a small database-backed worker.

Processing stages:

```text
uploaded
preparing_media
extracting
detecting_gaps
ready_for_review
```

Job statuses:

```text
queued
running
completed
failed
```

The worker should:

1. Claim a pending job.
2. Run one stage.
3. Persist its output.
4. Update the stage.
5. Continue or mark failure.
6. Avoid duplicating successful processing results.
7. Recover abandoned jobs using persisted state.

Do not rely on an in-memory dictionary or ordinary request-local background work for durable processing.

## Video evidence rules

When live video processing is eventually enabled:

- Use a supported provider upload mechanism.
- Wait until provider-side media processing is complete.
- Extract timestamps where available.
- Validate intervals against the actual duration.
- Make timestamps editable during review.
- Leave unobserved physical properties unknown.

Do not claim that a sampled video captures hidden forces, torque, tactile feel, or precision measurements.

---

# 13. GROUNDED Q&A — DETERMINISTIC V1

This is an important part of your scope.

For V1, build a conservative question-answering system that uses only the approved release.

Do not introduce vector search yet.

## 13.1 Retrieval approach

Use:

1. Server-side task and active-release resolution.
2. Simple normalization of the question.
3. Keyword or phrase matching against approved units.
4. Curated fixture question patterns where appropriate.
5. Basic relevance ranking.
6. Explicit fallback when no reliable match exists.

Since the corpus has only a few knowledge units, this is sufficient for demonstration.

## 13.2 Answer construction

Do not hardcode full answers unrelated to database content.

Instead:

- Use deterministic intent matching to identify a relevant knowledge field.
- Read its value from the approved release.
- Attach its approved evidence IDs.
- Build the response from that stored value.

This is important because an expert's newly approved answer must automatically become available through the Q&A endpoint.

For example:

A question asking why a particular action was taken should use the approved interpretation or decision explanation.

If those fields are absent, return insufficient evidence.

## 13.3 Abstention

An unsupported question must not receive an invented answer.

Examples:

- Exact torque specification not recorded.
- Manufacturer tolerances not supplied.
- Equipment safety rating not provided.
- Diagnosis outside the approved task context.

Return:

```json
{
  "status": "insufficient_evidence",
  "release_id": "release_001",
  "claims": [],
  "missing_information": [
    "The approved knowledge pack does not contain this information."
  ],
  "review_required": false
}
```

## 13.4 Live Q&A later

When `ENABLE_LIVE_QA=true`, the provider may formulate an answer using only retrieved approved context.

The server must still:

- Validate returned citations.
- Reject unknown evidence IDs.
- Reject unapproved sources.
- Preserve the release ID.
- Abstain when evidence is insufficient.
- Avoid presenting unsupported claims as confirmed.

Do not let the model decide access permissions.

---

# 14. EXPERT CLARIFICATION MUST CHANGE THE RELEASE

This is the most important technical behavior of Takumi.

Implement the following sequence as a real backend operation.

### Initial state

Knowledge unit:

```json
{
  "id": "ku_001",
  "action": "Inspect the housing",
  "cue": null,
  "interpretation": null,
  "decision": null,
  "exception": null
}
```

### Expert answers a question

The expert supplies missing reasoning through the clarification API.

### Backend operation

The backend:

1. Saves the expert response.
2. Creates an evidence record.
3. Updates the specified knowledge fields.
4. Links the evidence to those fields.
5. Advances the draft revision.
6. Preserves the earlier draft history or correction audit.
7. Allows reviewer inspection.

### Reviewer publishes

The updated knowledge becomes part of an immutable release.

### Apprentice integration

The training-pack export now contains the approved reasoning.

The simulator developer can reference that knowledge unit in a scenario.

The frontend can display its evidence.

The Q&A API can answer questions using the newly added reasoning.

**This entire chain must work even with all live AI features disabled.**

That is the most important V1 acceptance test.

---

# 15. AUTHENTICATION AND SECURITY

Use simple but genuine authorization.

V1 does not require OAuth, SSO, or production identity management.

Implement development-only demo identities.

Roles:

- Expert.
- Reviewer.
- Apprentice.

Use signed, expiring tokens or another server-verifiable session approach.

The backend must derive the role from the validated session.

Do not trust:

```text
X-Role: reviewer
```

or arbitrary client-supplied role fields as proof of authorization.

## Permissions

Expert:

- Create tasks.
- Edit drafts.
- Answer clarifications.
- Read own task evidence.

Reviewer:

- Expert permissions.
- Approve and publish releases.
- Review publication history.

Apprentice:

- Read approved releases.
- Read authorized evidence.
- Ask approved-content questions.

Apprentices must never access unpublished drafts through normal learner APIs.

## Other safeguards

- Validate all request payloads.
- Reject unknown fields on mutation APIs where practical.
- Restrict CORS to configured origins.
- Do not expose stack traces in API responses.
- Do not log API keys or bearer tokens.
- Protect file paths against traversal.
- Limit request sizes.
- Treat uploaded transcripts as untrusted data.
- Do not allow uploaded text or model output to override system instructions or access-control rules.
- Disable demo login and reset in production.
- Never commit `.env` secrets.

For a hackathon, prioritize the security boundaries that affect the actual demonstration.

Avoid spending time on enterprise features outside the MVP.

---

# 16. ERROR HANDLING

Implement one consistent error response:

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Draft revision does not match.",
    "details": {
      "expected": 2,
      "actual": 3
    }
  }
}
```

Use stable error codes.

Examples:

```text
TASK_NOT_FOUND
DRAFT_NOT_FOUND
NO_ACTIVE_RELEASE
REVISION_CONFLICT
FORBIDDEN
FEATURE_DISABLED
INVALID_EVIDENCE
EVIDENCE_UNAVAILABLE
INVALID_STATE_TRANSITION
UNSUPPORTED_MEDIA
FIXTURE_NOT_AVAILABLE
AI_PROVIDER_UNAVAILABLE
AI_OUTPUT_INVALID
PUBLICATION_BLOCKED
```

Map errors to appropriate HTTP status codes.

Do not return successful HTTP responses for failed operations.

Do not expose private implementation details through error messages.

Maintain useful server-side diagnostics.

---

# 17. API BEST PRACTICES

Follow these conventions.

## 17.1 Version the API

All application routes use:

`/api/v1`

Use `/api/v1/health` for consistency.

## 17.2 Keep schemas stable

Request and response schemas must be defined with Pydantic models.

Avoid returning raw SQLAlchemy objects directly.

## 17.3 Use dependency injection

Inject:

- Database session.
- Current user.
- Settings.
- AI provider.

Avoid global mutable database sessions.

## 17.4 Keep endpoints thin

Routers should:

- Validate requests.
- Check required authorization.
- Call services.
- Return typed responses.

Services should implement actual business logic.

## 17.5 Use transactions

Publication, clarification updates, evidence creation, and revision changes must be atomic.

## 17.6 Handle concurrency

Use expected-revision checks when editing drafts.

A stale write should return a conflict rather than silently overwriting newer data.

## 17.7 Make replay-sensitive operations idempotent

At minimum:

- Demo seeding.
- Processing requests.
- Publication retries.

Where necessary, use request IDs or unique database constraints.

Repeated requests must not create duplicate releases or evidence unintentionally.

## 17.8 Avoid unnecessary abstraction

Do not write a repository interface, factory, adapter, strategy, service locator, and event bus for every single table.

Use abstractions where there are genuine interchangeable implementations, especially AI providers.

Keep straightforward CRUD straightforward.

---

# 18. TESTING STRATEGY

Use pytest and FastAPI TestClient.

Tests should run against a temporary isolated database.

Never run destructive tests against the developer's existing database.

Use fixed fixtures and deterministic inputs.

## Test group A — Configuration

Verify:

- Fixture provider works without an API key.
- Live AI features are disabled by default.
- Invalid production/demo configurations fail safely.
- Disabled endpoints return explicit errors.
- Secrets are not exposed in configuration responses.

## Test group B — Tasks

Verify:

- Task creation persists.
- Task retrieval works.
- Unknown tasks return 404.
- Unauthorized mutation is rejected.

## Test group C — Drafts

Verify:

- Seeded draft loads.
- Knowledge fields can be updated.
- Revision increments.
- Stale revision returns 409.
- Unknown knowledge units are rejected.

## Test group D — Clarifications

Verify:

- An expert answer persists.
- Evidence is created.
- Field evidence links update.
- The draft revision increments.
- Rejected premises are preserved.
- A failed transaction does not leave partial updates.

## Test group E — Publication

Verify:

- Expert cannot publish without reviewer permission.
- Apprentice cannot publish.
- Reviewer can publish a valid draft.
- Published release remains immutable.
- Subsequent edits do not change the old release.
- A new publication advances the active release.

## Test group F — Evidence

Verify:

- Evidence IDs resolve.
- Evidence belongs to the correct task.
- Invalid cross-task evidence is rejected.
- Source labels remain accurate.
- Unsupported video intervals are rejected.

## Test group G — Grounded Q&A

Verify:

- Approved knowledge answers supported questions.
- Unapproved draft content is never used.
- Newly approved clarification appears in answers.
- Unsupported torque or tolerance questions cause abstention.
- Returned citation IDs exist in the selected release.
- Missing evidence does not produce a fabricated citation.

## Test group H — Training-pack export

Verify:

- The correct release is exported.
- IDs are stable.
- Approved units are included.
- Draft-only units are excluded.
- Evidence references are resolvable.
- Export schema remains valid.

## Test group I — Integration regression

Run this complete sequence:

```text
Seed task
    ↓
Read incomplete draft
    ↓
Submit new expert explanation
    ↓
Verify evidence creation
    ↓
Publish approved release
    ↓
Retrieve training pack
    ↓
Ask a supported question
    ↓
Receive evidence-linked answer
    ↓
Ask unsupported specification question
    ↓
Receive insufficient_evidence
```

This should be a repeatable automated integration test.

---

# 19. CHECKPOINT-BASED DEVELOPMENT

This is not a request to implement every future capability immediately.

Implement checkpoints sequentially.

At the end of each checkpoint:

1. Run the relevant tests.
2. Verify API responses.
3. Update the checkpoint document.
4. Preserve the working application.
5. Report what genuinely works.
6. Proceed only within the scope authorized by this prompt.

**For this V1 execution, complete Checkpoints 0–3.**

Prepare interfaces and feature flags for later checkpoints, but do not implement their full functionality yet.

## CHECKPOINT 0 — Bootstrap and contracts

Deliver:

- Running FastAPI application.
- Configuration system.
- Database connection.
- Shared schemas.
- Health endpoint.
- OpenAPI documentation.
- Error handling.
- Development authentication.
- Initial tests.
- Repository documentation.

Exit criteria:

- Server starts successfully.
- OpenAPI schema generates.
- Database initializes.
- Health endpoint works.
- Test suite runs.

## CHECKPOINT 1 — Deterministic knowledge backend

Deliver:

- Task APIs.
- Seeded demonstration task.
- Knowledge draft storage.
- Draft editing.
- Deterministic gap detection.
- Three clarification fixtures.
- Expert response API.
- Evidence creation.
- Revision control.

Exit criteria:

An API request containing a new expert explanation creates persistent evidence and updates the correct knowledge unit.

No external AI service is required.

## CHECKPOINT 2 — Approval, publication, and Q&A

Deliver:

- Reviewer authorization.
- Immutable release publication.
- Active-release retrieval.
- Specific-release retrieval.
- Evidence lookup.
- Deterministic grounded Q&A.
- Abstention behavior.
- Publication regression tests.

Exit criteria:

A newly approved clarification can be retrieved in an evidence-linked answer.

Unsupported questions return insufficient evidence.

Unapproved drafts are excluded.

## CHECKPOINT 3 — Integration handoff

Deliver:

- Training-pack export.
- Stable JSON contract fixtures.
- Example API requests/responses.
- Exported OpenAPI schema.
- Integration documentation.
- Seed/reset scripts.
- End-to-end regression tests.

Exit criteria:

The simulation and frontend developers can integrate using only the documented API contracts and fixture data.

They do not need to read internal backend implementation code to understand the response format.

**Stop V1 feature development after Checkpoint 3.**

Complete documentation and report results.

Do not automatically proceed to Checkpoints 4–6.

---

# 20. FUTURE CHECKPOINTS — FLAGS AND INTERFACES ONLY

These checkpoints are planned but not part of the current V1 implementation.

## CHECKPOINT 4 — Real media ingestion

Enable:

```dotenv
ENABLE_MEDIA_UPLOAD=true
ENABLE_MEDIA_STREAMING=true
```

Implement:

- Validated upload.
- Media persistence.
- File metadata.
- Authorized streaming.
- Browser range requests.

Do not enable until requested.

## CHECKPOINT 5 — Live video extraction

Enable:

```dotenv
AI_PROVIDER=gemini
ENABLE_LIVE_EXTRACTION=true
ENABLE_MEDIA_PROCESSING=true
ENABLE_PROCESSING_WORKER=true
```

Implement:

- Provider-side video upload.
- Media-processing readiness.
- Structured knowledge extraction.
- Timestamp checking.
- Persisted processing jobs.
- Bounded retries.
- Human review of extracted claims.

Do not enable until requested.

## CHECKPOINT 6 — Advanced intelligence

Possible flags:

```dotenv
ENABLE_LIVE_GAP_GENERATION=true
ENABLE_LIVE_QA=true
ENABLE_ADVANCED_RETRIEVAL=true
```

Potential improvements:

- More natural clarification questions.
- Better semantic retrieval.
- Multilingual terminology support.
- Prompt versioning experiments.
- Evaluation datasets.
- Cost and latency tracking.

Do not implement these merely because they appear in the roadmap.

---

# 21. CONTRACT HANDOFF TO TEAMMATES

Create:

`docs/INTEGRATION_HANDOFF.md`

This document must clearly explain:

## Available endpoints

For every implemented endpoint:

- Method.
- Path.
- Purpose.
- Required role.
- Request schema.
- Response schema.
- Example.
- Error conditions.
- Feature flag dependencies.

## How frontend developers authenticate

Provide a development login example and token usage instructions.

## How frontend developers retrieve knowledge

Document the task, draft, clarification, evidence, and release workflow.

## How simulation developers integrate

They should be able to:

1. Obtain an approved release ID.
2. Fetch its training pack.
3. Check required knowledge IDs.
4. Access approved evidence.
5. Reference knowledge-unit IDs in authored scenarios.
6. Request source-linked explanations when displaying feedback.

Do not require the simulation developer to query SQLite directly.

All integration should happen through contracts or an explicitly agreed service boundary.

## Shared identifiers

Document:

```text
task_id
draft_id
knowledge_unit_id
evidence_id
clarification_id
release_id
```

Explain their lifetime and stability.

Knowledge and evidence IDs must be stable inside a published release.

## Compatibility rules

- Do not rename fields casually.
- Preserve approved-release immutability.
- Preserve evidence provenance.
- Do not expose draft content to apprentice APIs.
- Keep fixture and live response shapes equivalent.
- Add new optional fields rather than breaking existing required fields.

---

# 22. OBSERVABILITY AND DEBUGGING

Keep observability lightweight.

Use Python's standard logging facilities or a small structured logging wrapper.

Record:

- Request ID.
- Endpoint.
- Response status.
- Duration.
- Task ID when applicable.
- Release ID when applicable.
- Processing stage.
- AI provider.
- Model ID when applicable.
- Error category.

Do not log confidential recordings, raw credentials, or bearer tokens.

For later AI processing, support recording:

```text
model_id
prompt_version
input_hash
stage_duration_ms
request_status
retry_count
```

Avoid building a complete tracing dashboard in V1.

Readable logs and predictable errors are sufficient.

---

# 23. DOCUMENTATION REQUIREMENTS

Create a concise README containing:

### Setup

How to install dependencies.

### Configuration

How to copy and configure `.env.example`.

### Start

How to run the FastAPI server.

### Database

How to initialize the database.

### Demo

How to seed the demonstration.

### Reset

How to reset the demonstration safely.

### API

Where to find OpenAPI documentation.

### Tests

How to execute tests and formatting checks.

### Feature flags

Which features are enabled by default.

### Limitations

Which capabilities are illustrative, disabled, or not implemented.

Provide exact commands that work in the resulting repository.

Do not document commands that have never been verified.

---

# 24. IMPLEMENTATION QUALITY RULES

Use these rules throughout development.

### Rule 1 — No fake success

Never return success unless the requested state change actually occurred.

### Rule 2 — No hidden AI dependency

The core demonstration must run with zero external AI calls.

### Rule 3 — No unauthorized publication

Only reviewers can publish.

### Rule 4 — No fabricated expertise

Illustrative fixture content must remain labelled illustrative.

### Rule 5 — No silent data corruption

Use validation and transactions for important state changes.

### Rule 6 — No release mutation

Published snapshots are immutable.

### Rule 7 — No hallucinated evidence

Answers must reference actual approved evidence.

### Rule 8 — No cross-task leakage

Knowledge and evidence must remain scoped to the appropriate task.

### Rule 9 — No unnecessary infrastructure

Keep the dependency footprint small.

### Rule 10 — No frontend development

The frontend developer owns interface implementation.

### Rule 11 — No simulation development

The simulator developer owns scenario mechanics and evaluation.

### Rule 12 — No integration surprises

Any change to shared API contracts must be reflected in OpenAPI and handoff documentation.

### Rule 13 — No unverified completion claims

If a test was not executed, say so.

### Rule 14 — No speculative feature implementation

Finish the current checkpoint before expanding scope.

### Rule 15 — Prioritize the knowledge lifecycle

If time is limited, preserve:

**Draft → Clarification → Evidence → Approval → Release → Grounded Answer**

Everything else is secondary.

---

# 25. REQUIRED FINAL DELIVERABLES

Before declaring V1 complete, ensure the repository contains:

- Working FastAPI backend.
- Typed configuration and feature flags.
- SQLite persistence.
- Demo authentication.
- Task CRUD.
- Knowledge draft retrieval and editing.
- Deterministic gap detection.
- Expert clarification endpoint.
- Evidence storage and retrieval.
- Immutable release publication.
- Approved release retrieval.
- Deterministic grounded Q&A.
- Training-pack export.
- Demonstration fixtures.
- Idempotent seed/reset scripts.
- OpenAPI contract.
- API examples.
- Automated tests.
- README.
- Integration handoff document.
- Known limitations document.
- Prepared interfaces for later live AI/media integration.

Do not implement frontend screens.

Do not implement simulation scoring or state transitions.

---

# 26. FINAL DEMONSTRATION ACCEPTANCE TEST

Your backend must support the following sequence, entirely through API requests.

**Step 1:** The developer seeds Takumi's illustrative shaft-and-bearing task.

**Step 2:** An expert retrieves a draft with missing reasoning.

**Step 3:** The expert retrieves a clarification question.

**Step 4:** The expert submits a new explanation.

**Step 5:** The server persists the response and assigns an evidence ID.

**Step 6:** The knowledge unit now references that evidence.

**Step 7:** A reviewer approves and publishes the knowledge.

**Step 8:** The server creates an immutable release.

**Step 9:** The training-pack endpoint exports the approved knowledge.

**Step 10:** A learner asks why the expert made the relevant decision.

**Step 11:** The Q&A endpoint returns the approved explanation with its evidence ID.

**Step 12:** The learner asks for an unsupported technical specification.

**Step 13:** The backend responds with `insufficient_evidence`.

**Step 14:** A user attempts to modify the old release.

**Step 15:** The backend rejects modification.

**Step 16:** The same process can be repeated after a safe reset.

This is V1's definition of done.

---

# 27. HOW TO REPORT PROGRESS

At the end of each checkpoint, provide a concise engineering report containing:

**Checkpoint completed:** Name and number.

**Implemented:** Functions and endpoints actually working.

**Verified:** Tests and commands executed successfully.

**Flags:** Which capabilities are active.

**API changes:** Any deviations from the agreed contract.

**Blocked:** Missing credentials, dependencies, or external requirements.

**Remaining:** Work explicitly deferred.

**Integration readiness:** What frontend/simulation developers can use immediately.

Update `docs/CHECKPOINTS.md` with the same information.

Do not describe planned behavior as implemented.

---

# 28. EXECUTION DIRECTIVE

Your task is to implement the Takumi V1 Backend & AI Knowledge Engine.

**Start with Checkpoint 0 and continue through Checkpoint 3.**

Use deterministic fixtures as the default.

Hardcode educational sample data and question templates where this accelerates development, but keep that data centralized and clearly labelled.

Implement real persistence, evidence attribution, revision control, authorization, publication, and release export.

Keep live AI, media processing, embeddings, and advanced retrieval behind disabled feature flags.

Build and test the full knowledge lifecycle before expanding.

Preserve the agreed API contracts for the other two developers.

Make all changes within the backend's ownership boundary.

When Checkpoint 3 is finished, run the complete test suite and API smoke test, document the verified outcomes, and report readiness for integration.

**The guiding principle:**

> Hardcode the initial intelligence, not the integrity of the system. Build the evidence-backed knowledge engine first. Make it smarter only after it reliably works.

Begin implementation now.
