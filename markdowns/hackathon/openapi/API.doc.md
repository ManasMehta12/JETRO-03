# TAKUMI — API Specification v1.0

**Project:** Takumi — AI-Powered Expert Knowledge Transfer & Digital Apprenticeship  
**Challenge:** JETRO PS-03  
**Architecture:** Next.js Frontend + FastAPI Backend  
**Status:** Implementation Contract — Hackathon MVP

---

## 1. General API conventions

**Base URL:** `http://localhost:8000/api/v1`

**Documentation:** `http://localhost:8000/docs`

**Data format:** JSON unless specified otherwise.

**Time format:** ISO 8601 UTC.

**Identifiers:** Opaque string IDs, e.g., `task_001`, `release_001`.

**Authentication:** Bearer tokens issued by the backend. For the hackathon, development-only demo accounts are sufficient.

### User roles

| Role       | Permissions                                                           |
| ---------- | --------------------------------------------------------------------- |
| Expert     | Upload demonstrations, answer clarification questions, edit knowledge |
| Reviewer   | Expert permissions, approve knowledge, publish scenarios              |
| Apprentice | Access approved knowledge, complete scenarios, submit viva            |

In demo mode, role switching may be enabled through a development-only login endpoint. Never trust a frontend-provided role header as authorization.

### Standard error response

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "The resource was modified by another operation.",
    "details": {}
  }
}
```

Standard HTTP codes:

| Code | Meaning                        |
| ---- | ------------------------------ |
| 200  | Successful retrieval or update |
| 201  | Resource created               |
| 202  | Background processing accepted |
| 400  | Invalid request                |
| 401  | Authentication required        |
| 403  | Insufficient permission        |
| 404  | Resource not found             |
| 409  | State or revision conflict     |
| 413  | Upload too large               |
| 422  | Request validation failed      |
| 500  | Internal error                 |
| 503  | AI provider unavailable        |

Never return HTTP 200 for a failed operation while silently pretending it succeeded.

---

# 2. API endpoint registry

These are the canonical routes. Use `/api/v1` as the prefix.

| Method | Endpoint                       | Purpose                      | Priority |
| ------ | ------------------------------ | ---------------------------- | -------- |
| GET    | `/health`                      | Backend health               | P0       |
| POST   | `/auth/demo-login`             | Obtain demo token            | P0       |
| GET    | `/tasks`                       | List tasks                   | P0       |
| POST   | `/tasks`                       | Create task                  | P0       |
| GET    | `/tasks/{id}`                  | Task details                 | P0       |
| POST   | `/tasks/{id}/media`            | Upload video                 | P1       |
| POST   | `/tasks/{id}/process`          | Start extraction             | P1       |
| GET    | `/jobs/{id}`                   | Processing status            | P1       |
| GET    | `/tasks/{id}/draft`            | Get editable knowledge       | P0       |
| PATCH  | `/tasks/{id}/draft`            | Update knowledge             | P0       |
| POST   | `/clarifications/{id}/respond` | Record expert answer         | P0       |
| POST   | `/tasks/{id}/publish`          | Publish knowledge release    | P0       |
| GET    | `/tasks/{id}/release`          | Retrieve approved knowledge  | P0       |
| GET    | `/evidence/{id}`               | Retrieve evidence details    | P0       |
| GET    | `/media/{id}/stream`           | Play source video            | P1       |
| POST   | `/tasks/{id}/ask`              | Evidence-grounded Q&A        | P0       |
| GET    | `/tasks/{id}/scenarios`        | List available scenarios     | P0       |
| GET    | `/scenarios/{id}`              | Get public scenario manifest | P0       |
| POST   | `/scenarios/{id}/publish`      | Approve scenario             | P0       |
| POST   | `/scenarios/{id}/attempts`     | Start practice attempt       | P0       |
| GET    | `/attempts/{id}`               | Current learner state        | P0       |
| POST   | `/attempts/{id}/actions`       | Execute scenario action      | P0       |
| POST   | `/attempts/{id}/viva`          | Submit technical viva        | P0       |
| GET    | `/attempts/{id}/report`        | Get learner assessment       | P0       |
| POST   | `/demo/reset`                  | Reset demo data              | P0       |

P0 means required for the core hackathon demonstration. P1 means the live media/AI path can be integrated after the preloaded demonstration works.

---

# 3. Shared data contracts

All teams must use consistent field names and semantics.

## 3.1 KnowledgeUnit

```json
{
  "id": "ku_001",
  "action": "Inspect the bearing housing",
  "cue": "Observation awaiting review",
  "interpretation": null,
  "decision": null,
  "exception": null,
  "evidence_ids": ["ev_001"],
  "field_evidence": {
    "action": ["ev_001"],
    "cue": ["ev_001"]
  },
  "review_status": "draft"
}
```

`null` means the information is unknown, not that it is false.

The `field_evidence` mapping identifies which evidence supports each field.

### Knowledge review states

- `draft`
- `reviewed`
- `approved`

A model-generated claim cannot become approved merely because it has an evidence ID.

## 3.2 EvidenceItem

```json
{
  "id": "ev_002",
  "task_id": "task_001",
  "type": "expert_response",
  "author": "Demo Expert",
  "content": "Illustrative expert explanation",
  "media_id": null,
  "start_ms": null,
  "end_ms": null,
  "source_label": "illustrative",
  "created_at": "2026-10-24T10:00:00Z"
}
```

Permitted types:

- `video_segment`
- `expert_response`
- `reviewer_correction`

`source_label` must distinguish `real` from `illustrative`.

For a video source, `media_id`, `start_ms`, and `end_ms` identify the original interval.

## 3.3 Approved release

```json
{
  "id": "release_001",
  "task_id": "task_001",
  "version": 1,
  "status": "active",
  "approved_by": "reviewer_001",
  "approved_at": "2026-10-24T10:00:00Z",
  "knowledge_units": [],
  "evidence_items": []
}
```

Published releases are immutable. New edits produce new releases.

---

# 4. Task and authentication APIs

## 4.1 POST /auth/demo-login

**Purpose:** Obtain a short-lived token for an approved demo identity.

Request:

```json
{
  "demo_user": "expert"
}
```

Response:

```json
{
  "access_token": "server_signed_token",
  "token_type": "bearer",
  "user": {
    "id": "expert_001",
    "role": "expert"
  }
}
```

Available demo identities: `expert`, `reviewer`, `apprentice`.

This endpoint must be disabled outside explicitly configured demo environments.

## 4.2 POST /tasks

**Access:** Expert / Reviewer

Request:

```json
{
  "title": "Shaft and Bearing Inspection",
  "equipment": "Unpowered bench assembly",
  "description": "Inspection training for a shaft-and-bearing assembly",
  "language": "en"
}
```

Response: `201 Created`

```json
{
  "id": "task_001",
  "title": "Shaft and Bearing Inspection",
  "equipment": "Unpowered bench assembly",
  "status": "created",
  "active_release_id": null
}
```

## 4.3 GET /tasks

Returns tasks visible to the authenticated user.

Response:

```json
{
  "items": [
    {
      "id": "task_001",
      "title": "Shaft and Bearing Inspection",
      "status": "published",
      "active_release_id": "release_001"
    }
  ]
}
```

## 4.4 GET /tasks/{id}

Returns the task metadata, media references, processing status, and active-release ID.

Do not expose unpublished knowledge to apprentices.

---

# 5. Video upload and processing APIs

## 5.1 POST /tasks/{id}/media

**Access:** Expert / Reviewer

**Content-Type:** `multipart/form-data`

Form field: `file`

Supported formats: MP4 and other formats explicitly supported by the deployed processing stack.

Application limits:

- 100 MB maximum.
- Four minutes maximum.

Response: `201 Created`

```json
{
  "media_id": "media_001",
  "task_id": "task_001",
  "filename": "demo.mp4",
  "status": "uploaded",
  "duration_ms": 150000
}
```

Reject invalid media and provide actionable errors.

Do not publish uploaded files in a publicly browsable directory.

## 5.2 POST /tasks/{id}/process

**Access:** Expert / Reviewer

Request:

```json
{
  "media_id": "media_001",
  "mode": "live",
  "request_id": "process_request_001"
}
```

`mode` must be either `live` or `demo`.

Live mode requires configured AI credentials. Demo mode uses explicitly labelled fixtures.

Response: `202 Accepted`

```json
{
  "job_id": "job_001",
  "status": "queued",
  "stage": "uploaded"
}
```

Repeated requests with the same task, media, mode, and request ID must not create duplicate processing jobs.

## 5.3 GET /jobs/{id}

Response:

```json
{
  "job_id": "job_001",
  "status": "completed",
  "stage": "ready_for_review",
  "progress_label": "Draft extracted",
  "draft_id": "draft_001",
  "error": null
}
```

Supported job statuses:

- `queued`
- `running`
- `completed`
- `failed`

Supported stages:

- `uploaded`
- `preparing_media`
- `extracting`
- `detecting_gaps`
- `ready_for_review`

Display stage labels instead of estimated percentages.

---

# 6. Knowledge extraction and clarification APIs

## 6.1 GET /tasks/{id}/draft

**Access:** Expert / Reviewer

Response:

```json
{
  "draft_id": "draft_001",
  "task_id": "task_001",
  "revision": 1,
  "status": "draft",
  "knowledge_units": [
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
  ],
  "clarifications": [
    {
      "id": "clar_001",
      "knowledge_unit_id": "ku_001",
      "question": "What observation prompted this inspection?",
      "status": "pending"
    }
  ]
}
```

The extraction worker may create these fields through AI, but the record must preserve the distinction between observed information and unsupported reasoning.

## 6.2 PATCH /tasks/{id}/draft

**Access:** Expert / Reviewer

Purpose: Correct extracted knowledge.

Request:

```json
{
  "expected_revision": 1,
  "changes": [
    {
      "knowledge_unit_id": "ku_001",
      "fields": {
        "action": "Visually inspect the housing"
      }
    }
  ]
}
```

Response:

```json
{
  "draft_id": "draft_001",
  "revision": 2,
  "status": "draft",
  "updated_knowledge_unit_ids": ["ku_001"]
}
```

Each reviewer correction must produce an attributed evidence record or correction history entry.

When `expected_revision` differs from the stored revision, return HTTP 409.

## 6.3 POST /clarifications/{id}/respond

**Access:** Expert / Reviewer

Purpose: Store the reasoning acquired through an expert interview.

Request:

```json
{
  "expected_draft_revision": 2,
  "disposition": "answered",
  "answer": "The expert's actual explanation goes here.",
  "knowledge_update": {
    "knowledge_unit_id": "ku_001",
    "fields": {
      "cue": "Expert-confirmed observation",
      "interpretation": "Expert-confirmed interpretation",
      "decision": "Expert-confirmed next action"
    }
  }
}
```

Allowed dispositions:

- `answered`
- `premise_rejected`
- `unobservable`
- `deferred`

Response:

```json
{
  "clarification_id": "clar_001",
  "status": "answered",
  "evidence_id": "ev_002",
  "knowledge_unit_id": "ku_001",
  "draft_revision": 3
}
```

The backend must create a new attributed `EvidenceItem`.

For `answered`, apply validated field updates and link them to that evidence.

For other dispositions, preserve the response and do not fabricate missing knowledge.

**This endpoint is critical to the product. The acquired knowledge must influence the approved training content.**

---

# 7. Publication and evidence APIs

## 7.1 POST /tasks/{id}/publish

**Access:** Reviewer

Request:

```json
{
  "expected_revision": 3,
  "approval_note": "Knowledge checked against available expert input."
}
```

Response: `201 Created`

```json
{
  "release_id": "release_001",
  "task_id": "task_001",
  "version": 1,
  "status": "active",
  "approved_by": "reviewer_001"
}
```

Publication requirements:

1. The draft revision matches.
2. The reviewer has permission.
3. Required technical content has been reviewed.
4. Referenced evidence exists.
5. Evidence belongs to the current task.
6. A new immutable release is created.

The active release pointer changes only after successful publication.

Publishing knowledge does not automatically approve a dependent scenario.

## 7.2 GET /tasks/{id}/release

**Access:** Expert / Reviewer / Apprentice

Returns the active approved release, including its knowledge units and evidence references.

Draft material must never appear in the apprentice response.

If no release exists, return 404 with code `NO_ACTIVE_RELEASE`.

## 7.3 GET /evidence/{id}

Returns a referenced evidence record, subject to task and role permissions.

Video evidence response:

```json
{
  "id": "ev_001",
  "type": "video_segment",
  "media_id": "media_001",
  "start_ms": 25000,
  "end_ms": 41000,
  "author": "Demo Expert",
  "source_label": "real"
}
```

Expert-response evidence includes the attributed answer as `content`.

For video evidence, open the streaming endpoint and seek to `start_ms`.

## 7.4 GET /media/{id}/stream

Returns authorized video bytes.

Requirements:

- Support browser range requests.
- Return HTTP 206 for valid partial-content requests.
- Validate access before serving.
- Support seeking to cited intervals.
- Return a clear error when the source is unavailable.

---

# 8. Evidence-grounded question answering

## POST /tasks/{id}/ask

**Access:** Any authorized user with access to the approved task.

Request:

```json
{
  "question": "Why did the expert perform this check?",
  "language": "en"
}
```

The backend resolves the active approved release. Do not allow the client to choose arbitrary unpublished knowledge as the source.

Possible successful response:

```json
{
  "status": "answered",
  "release_id": "release_001",
  "claims": [
    {
      "text": "The approved expert explanation.",
      "knowledge_unit_id": "ku_001",
      "evidence_ids": ["ev_002"]
    }
  ],
  "missing_information": [],
  "review_required": false
}
```

Possible insufficient-evidence response:

```json
{
  "status": "insufficient_evidence",
  "release_id": "release_001",
  "claims": [],
  "missing_information": [
    "The approved knowledge does not contain the requested specification."
  ],
  "review_required": false
}
```

Supported statuses:

- `answered`
- `needs_context`
- `insufficient_evidence`

**Rules:**

- Use only the active approved release.
- Validate every referenced knowledge/evidence ID.
- Do not invent technical values or specifications.
- Reject nonexistent, stale, or cross-task evidence references.
- Return insufficient evidence when the approved material cannot support the answer.

Grounding is a product requirement, not an optional prompt instruction.

---

# 9. Scenario and playground APIs

## 9.1 GET /tasks/{id}/scenarios

Returns the visible, approved scenarios for the active release.

Response:

```json
{
  "items": [
    {
      "id": "scenario_001",
      "title": "Guided Inspection",
      "mode": "guided",
      "release_id": "release_001",
      "status": "published"
    },
    {
      "id": "scenario_002",
      "title": "Changed-Condition Assessment",
      "mode": "assessment",
      "release_id": "release_001",
      "status": "published"
    }
  ]
}
```

## 9.2 GET /scenarios/{id}

Returns the public scenario manifest.

Response:

```json
{
  "id": "scenario_001",
  "title": "Guided Shaft Inspection",
  "release_id": "release_001",
  "mode": "guided",
  "scene_template": "shaft_bearing",
  "components": [
    { "id": "base", "label": "Base" },
    { "id": "shaft", "label": "Shaft" },
    { "id": "bearing", "label": "Bearing" },
    { "id": "housing", "label": "Housing" }
  ],
  "public_actions": [
    "inspect",
    "request_observation",
    "choose_check",
    "continue",
    "escalate"
  ]
}
```

Never expose private decision rules, expected answers, hidden observations, or unrevealed assessment outcomes through this endpoint.

## 9.3 POST /scenarios/{id}/publish

**Access:** Reviewer

Request:

```json
{
  "release_id": "release_001",
  "approval_note": "Scenario branches reviewed."
}
```

Response:

```json
{
  "scenario_id": "scenario_001",
  "release_id": "release_001",
  "status": "published"
}
```

The backend must validate required knowledge units and approved evidence.

A scenario cannot be published if an essential knowledge unit is absent or unapproved.

A newer release requires dependent scenario re-review before activation against it.

## 9.4 POST /scenarios/{id}/attempts

**Access:** Apprentice

Request:

```json
{
  "mode": "guided"
}
```

Response: `201 Created`

```json
{
  "attempt_id": "attempt_001",
  "scenario_id": "scenario_001",
  "release_id": "release_001",
  "revision": 0,
  "status": "in_progress",
  "public_state": {
    "phase": "inspection",
    "selected_component": null,
    "revealed_observations": [],
    "available_actions": ["inspect", "request_observation", "escalate"]
  }
}
```

The mode must match an allowed version of the scenario.

Store the exact release and scenario version for the entire attempt.

## 9.5 GET /attempts/{id}

Returns the authoritative public state of the attempt.

Used for:

- Resuming after refresh.
- Recovering from lost API responses.
- Displaying available actions.
- Loading viva questions once the scenario is completed.

Include `viva_questions` only when they are available to the learner.

Do not reveal hidden assessment outcomes prematurely.

## 9.6 POST /attempts/{id}/actions

**Access:** Apprentice

Request:

```json
{
  "expected_revision": 0,
  "client_event_id": "event_001",
  "action_type": "request_observation",
  "target_id": "housing",
  "observation_id": "obs_001"
}
```

Response:

```json
{
  "attempt_id": "attempt_001",
  "event_id": "event_001",
  "accepted": true,
  "revision": 1,
  "status": "in_progress",
  "public_state": {
    "phase": "inspection",
    "revealed_observations": [
      {
        "id": "obs_001",
        "text": "Illustrative observation provided by the reviewed scenario."
      }
    ],
    "available_actions": ["inspect", "choose_check", "escalate"]
  },
  "feedback": null
}
```

Supported actions:

- `inspect`
- `request_observation`
- `choose_check`
- `continue`
- `escalate`

The server owns all scenario transitions and scores.

A pedagogically incorrect but valid learner action may be recorded as an unsuccessful decision. An invalid API request must not change the state.

### Idempotency

`client_event_id` must be unique per attempt.

If the same event is submitted again, return the original recorded response without applying the transition twice.

If `expected_revision` does not match the current revision for a new event, return HTTP 409.

State changes and event recording must occur atomically.

### Important integration requirement

Scenario feedback should include:

```json
{
  "feedback": {
    "outcome": "review_required",
    "message": "The reviewed explanation relevant to this decision.",
    "knowledge_unit_ids": ["ku_001"],
    "evidence_ids": ["ev_002"]
  }
}
```

In assessment mode, withhold explanatory feedback until the appropriate reveal stage.

This is how the 3D playground connects to real approved knowledge.

---

# 10. Technical viva APIs

## 10.1 Viva questions

Once an attempt reaches `scenario_completed`, `GET /attempts/{id}` may return:

```json
{
  "attempt_id": "attempt_001",
  "status": "scenario_completed",
  "viva_questions": [
    {
      "id": "viva_001",
      "type": "decision_explanation",
      "question": "Why did you choose that inspection?"
    },
    {
      "id": "viva_002",
      "type": "changed_condition",
      "question": "What would change your next decision?"
    },
    {
      "id": "viva_003",
      "type": "knowledge_boundary",
      "question": "When would you request more evidence or escalate?"
    }
  ]
}
```

Question content comes from an instructor-reviewed bank linked to the scenario release.

## 10.2 POST /attempts/{id}/viva

**Access:** Apprentice

Request:

```json
{
  "client_submission_id": "viva_submission_001",
  "responses": [
    {
      "question_id": "viva_001",
      "answer": "Learner's explanation of the chosen action."
    },
    {
      "question_id": "viva_002",
      "answer": "Learner's response to the changed condition."
    },
    {
      "question_id": "viva_003",
      "answer": "Learner's explanation of when to escalate."
    }
  ]
}
```

Response:

```json
{
  "attempt_id": "attempt_001",
  "status": "completed",
  "evaluation": {
    "decision_accuracy": {
      "score": 1,
      "max_score": 1
    },
    "evidence_gathering": {
      "score": 1,
      "max_score": 1
    },
    "explanation_quality": {
      "status": "provisional",
      "feedback": "Feedback based on the approved viva rubric."
    },
    "recognition_of_limits": {
      "status": "review_required"
    }
  },
  "evidence_ids": ["ev_002"]
}
```

Scores above are illustrative response values, not achieved project results.

Viva submissions should be idempotent using `client_submission_id`.

### Scoring requirements

- Backend determines decision accuracy.
- Backend records observations requested.
- Optional AI evaluates written explanations against an approved rubric.
- If model evaluation is unavailable, show provisional rubric feedback or pending review.
- Technical fluency must not compensate for a critical decision error.
- No scoring of accent, personality, or apparent confidence.

---

# 11. Learner report

## GET /attempts/{id}/report

**Access:** Apprentice (own attempt), Expert / Reviewer (authorized task).

Response:

```json
{
  "attempt_id": "attempt_001",
  "task_id": "task_001",
  "scenario_id": "scenario_001",
  "release_id": "release_001",
  "status": "completed",
  "summary": {
    "actions_taken": 4,
    "observations_requested": 2,
    "decision_errors": 1,
    "escalations": 0
  },
  "viva": {
    "submitted": true,
    "feedback_status": "provisional"
  },
  "evidence_ids": ["ev_002"]
}
```

Generate all numerical results from stored attempts and events.

Do not hardcode analytics percentages or learner-improvement claims.

---

# 12. Demo reset

## POST /demo/reset

**Access:** Demo Reviewer

**Availability:** Only when demo mode is enabled.

Request:

```json
{
  "scope": "attempts"
}
```

Permitted scopes:

- `attempts` — Clear demo learner attempts while preserving training content.
- `full_demo` — Restore the original illustrative seed dataset.

For `full_demo`, require an explicit confirmation field:

```json
{
  "scope": "full_demo",
  "confirm": "RESET_DEMO_DATA"
}
```

Response:

```json
{
  "success": true,
  "scope": "attempts"
}
```

Never expose a destructive reset endpoint in a production configuration.

---

# 13. Required state machines

## Knowledge lifecycle

`created → uploaded → processing → draft → review → published`

Processing failures must preserve the last successful data.

Publishing produces a frozen release snapshot.

A later edit does not mutate the published snapshot.

## Clarification lifecycle

`pending → answered / premise_rejected / unobservable / deferred`

An answered clarification must create attributed evidence.

## Scenario lifecycle

`draft → reviewed → published`

A scenario is bound to a specific approved knowledge release.

## Learner lifecycle

`created → in_progress → scenario_completed → viva_submitted → completed`

All authoritative state transitions take place on the backend.

---

# 14. Frontend and backend integration contracts

## Expert Studio must receive

- Task ID.
- Upload and processing status.
- Extracted knowledge units.
- Clarification questions.
- Draft revision.
- Saved expert responses.
- Evidence IDs.
- Approved release ID.

## Apprentice Playground must receive

- Public scenario manifest.
- Scene component IDs.
- Attempt ID.
- Attempt revision.
- Current public state.
- Available actions.
- Revealed observations.
- Approved feedback.
- Supporting knowledge/evidence references.

## Technical Viva must receive

- Attempt context.
- Reviewed questions.
- Learner submission status.
- Decision scores.
- Rubric feedback.
- Evidence references.

**The frontend must not locally reconstruct hidden scoring rules.**

It may control visual selection, camera movement, panels, and animations.

The backend controls learning decisions and assessment outcomes.

---

# 15. Integration checkpoints

### Checkpoint 1 — Shared contracts

Backend provides:

- OpenAPI schema.
- Sample task fixture.
- Knowledge unit fixture.
- Scenario manifest.
- Attempt action request/response.

Frontend can immediately build against these fixtures.

### Checkpoint 2 — Expert loop

Verify:

- A clarification answer is persisted.
- It receives an evidence ID.
- The draft revision changes.
- Reviewer approval creates a release.
- A learner can retrieve only that approved release.

### Checkpoint 3 — Training loop

Verify:

- A learner starts an attempt.
- Requests an observation.
- Chooses an action.
- Receives a backend transition.
- Can open feedback connected to the approved expert explanation.

### Checkpoint 4 — Viva

Verify:

- Three questions are available.
- Answers persist.
- Decision scores remain server-authoritative.
- Feedback references approved knowledge.

### Checkpoint 5 — Demo reliability

Verify:

- Seeded demo works without an API key.
- Live mode never silently substitutes fixture outputs.
- Retry and failure states are visible.
- Browser refresh preserves progress.
- Duplicate actions do not score twice.
- Reset restores the demonstration.

---

# 16. Team ownership

| Area                               | Owner     | Responsibility                            |
| ---------------------------------- | --------- | ----------------------------------------- |
| Task creation and media processing | A + B     | AI extraction and backend storage         |
| Draft knowledge contracts          | A + B     | Data format, corrections, attribution     |
| Clarification workflow             | A + B     | Question generation, response persistence |
| Publication and permissions        | B         | Immutable releases, authorization         |
| Grounded knowledge Q&A             | A + B     | Retrieval and evidence validation         |
| Scenario authoring                 | A + B     | Reviewed content and scenario rules       |
| Scenario engine                    | B         | Authoritative transitions and scoring     |
| React Three Fiber scene            | C         | Geometry, inspection, component selection |
| Apprentice interface               | C         | State rendering, actions, feedback        |
| Technical viva                     | A + B + C | Rubric, scoring, UI                       |
| Deployment and recovery            | B         | Infrastructure, logs, reset               |
| Final integration                  | All       | End-to-end acceptance                     |

---

# 17. Non-negotiable acceptance criteria

The implementation is acceptable only if:

1. The API schemas are consistent between frontend and backend.
2. The complete seeded journey works without an external AI dependency.
3. An expert clarification becomes attributed evidence.
4. An approved release is immutable.
5. The apprentice never accesses unpublished content.
6. A training scenario references approved knowledge.
7. At least one clarification-derived knowledge unit is used in learner feedback.
8. Scenario scoring cannot be forged through client requests.
9. Duplicate actions are idempotent.
10. Unsupported technical questions do not receive invented answers.
11. Viva feedback can open supporting evidence.
12. Browser refresh does not erase authoritative progress.

**Final implementation directive:** Favor a smaller, fully functioning API over a large set of incomplete endpoints. Implement P0 routes first, use fixed schemas, and preserve the defining connection between expert-acquired reasoning and apprentice decisions.

**End of specification.**
