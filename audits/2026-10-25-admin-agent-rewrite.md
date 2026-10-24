# Admin panel: agent workflow rewrite

## What was still fixed

The previous interface chose an authored fixture whenever no key existed, populated the source from that fixture, hardcoded `task_001` in the frontend and prefilled a publication note. `/studio/admin` was only an alias of the expert page. These defaults could make a real agent integration look like a fixed demonstration.

## Current behavior

- `/studio/admin` opens tutor administration. The authenticated user display name comes from the backend.
- `GET /api/v1/studio/workspace` resolves the task connected to apprentice learning and returns its current draft, evidence, configuration and latest run. The frontend uses the returned task ID and title.
- Initial source material comes from the task's stored evidence, with attribution. The operator can add expert source notes.
- Live AI is the default. Missing credentials show **Configuration required** and disable the live action. The API independently rejects a keyless live request.
- The three provider roles extract source facts, propose source-supported field patches and independently critique them. The panel renders the returned proposals, evaluation and actual persisted phase.
- Rehearsal requires an explicit Analysis mode selection and a request with `mode: rehearsal`. It is available only in demo mode. Old rehearsal output is not automatically displayed as the live result.
- Source/revision checks and explicit human publication remain. There is no prefilled approval note. Nothing is published just by running diagnosis.
- Published changes still reach apprentice course content and subsequent interview preparation.

The connected apprentice experience is still the existing single course. This change removes frontend assumptions about its task identity; it does not add a course catalogue or production identity management.

## Real-provider issue found and fixed

A real isolated request exposed a schema transport problem: the provider rejected strict Pydantic `additionalProperties` through `response_schema`. The adapter now sends `response_json_schema` and continues validating responses locally. A regression test checks the actual SDK configuration rather than mocking the entire agent class.

`STUDIO_AI_THINKING_LEVEL` defaults to `low` and can be changed to `medium` or `high`. The configured model is preserved. Google's [thinking documentation](https://ai.google.dev/gemini-api/docs/thinking) documents these controls and the supported levels for the model family.

## Verification

- Production build passed.
- 16 targeted backend tests passed; Ruff checks and formatting passed.
- Four browser checks passed: server-driven admin metadata, live agent API result rendering, explicit rehearsal through apprentice publication/report, and clarification field mapping.
- The configured Gemini model was reachable through the model metadata API.
- Actual generation requests were attempted in temporary databases using illustrative source material. After correcting the schema transport, the provider returned a 504 timeout and a 503 service-unavailable response. No successful full live extraction is claimed, and no changes were published to the user's course during these checks.

A provider outage remains an external dependency. The interface retains the failed live state and allows another diagnosis attempt; it never switches to a fixture implicitly. Browser live-response tests use mocked provider output and are labelled separately from the attempted real-provider checks above.
