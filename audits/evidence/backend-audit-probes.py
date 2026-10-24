"""Read-only to the real app: reproduce audit findings in temporary databases.

Run from backend: uv run python ../audits/evidence/backend-audit-probes.py
"""

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def login(client, role):
    result = client.post("/api/v1/auth/demo-login", json={"demo_user": role})
    result.raise_for_status()
    return {"Authorization": "Bearer " + result.json()["access_token"]}


results = {}
with tempfile.TemporaryDirectory(prefix="takumi-audit-") as directory:
    root = Path(directory)
    for state in ("fresh", "approved_baseline"):
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_url=f"sqlite:///{root / (state + '.db')}",
            media_storage_dir=root / "media",
            demo_seed_state=state,
            demo_signing_secret="isolated-audit-only",
            log_level="ERROR",
        )
        with TestClient(create_app(settings)) as client:
            expert = login(client, "expert")
            reviewer = login(client, "reviewer")
            if state == "fresh":
                path = "/api/v1/studio/tasks/task_001"
                before = client.get(path, headers=expert).json()
                gap = before["draft"]["clarifications"][0]
                unit_id = gap["knowledge_unit_id"]
                response = client.post(
                    f"/api/v1/clarifications/{gap['id']}/respond",
                    headers=expert,
                    json={
                        "expected_draft_revision": before["draft"]["revision"],
                        "disposition": "answered",
                        "answer": "Audit-only response demonstrating storage, not a mechanical claim.",
                    },
                )
                response.raise_for_status()
                after = client.get(path, headers=expert).json()
                old_unit = next(u for u in before["draft"]["knowledge_units"] if u["id"] == unit_id)
                new_unit = next(u for u in after["draft"]["knowledge_units"] if u["id"] == unit_id)
                fields = ("action", "cue", "interpretation", "decision", "exception")
                publish = client.post(
                    "/api/v1/tasks/task_001/publish",
                    headers=reviewer,
                    json={"expected_revision": after["draft"]["revision"], "approval_note": "Isolated audit probe"},
                )
                results["answer_without_structured_update"] = {
                    "response_status": response.status_code,
                    "content_fields_unchanged": all(old_unit.get(f) == new_unit.get(f) for f in fields),
                    "before_revision": before["draft"]["revision"],
                    "after_revision": after["draft"]["revision"],
                    "evidence_added": len(after["evidence"]) - len(before["evidence"]),
                }
                results["legacy_reviewer_publication"] = {
                    "status": publish.status_code,
                    "admin_authorization": after["authorization"],
                    "evaluation": after["evaluation"],
                    "pending_clarifications": sum(g["status"] == "pending" for g in after["draft"]["clarifications"]),
                }
            else:
                apprentice = login(client, "apprentice")
                for stage in ("course", "playground"):
                    client.post("/api/v1/learning/complete", headers=apprentice, json={"stage": stage}).raise_for_status()
                before = client.get("/api/v1/learning/progress", headers=apprentice).json()
                reset = client.post(
                    "/api/v1/demo/reset", headers=reviewer,
                    json={"scope": "full_demo", "state": "approved_baseline", "confirm": "RESET_DEMO_DATA"},
                )
                after = client.get("/api/v1/learning/progress", headers=apprentice).json()
                results["full_demo_reset_learning_state"] = {
                    "reset_status": reset.status_code,
                    "release_before": before["release_id"],
                    "release_after": after["release_id"],
                    "course_completed_after": after["course_completed"],
                    "interview_unlocked_after": after["interview_unlocked"],
                    "manual_completions_retained": bool(after["manual_completion"]),
                }

output = Path(__file__).with_name("backend-probe-results.json")
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
