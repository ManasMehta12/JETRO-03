import json
from typing import Literal

from app.ai.fixture_provider import FIXTURE_PATH, FixtureAIProvider
from app.ai.schemas import MediaReference, TaskContext
from app.database import utcnow
from app.models.entities import Clarification, Draft, DraftRevision, Evidence, Task

FIXTURE_TASK_ID = "task_001"


def seed_demo(
    session, state: Literal["fresh", "approved_baseline"] = "fresh", provider=None
) -> bool:
    if session.get(Task, FIXTURE_TASK_ID) is not None:
        return False
    if state == "approved_baseline":
        raise NotImplementedError("Approved baseline seeding is implemented in Wave 3.")
    fixture = json.loads(FIXTURE_PATH.read_text())
    task_data = fixture["task"]
    provider = provider or FixtureAIProvider()
    context = TaskContext(
        task_id=task_data["id"],
        title=task_data["title"],
        equipment=task_data["equipment"],
        language=task_data["language"],
    )
    extraction = provider.extract_knowledge(
        MediaReference(fixture_id=fixture["fixture_id"]), context
    )
    task = Task(**task_data, status="draft", created_at=utcnow(), updated_at=utcnow())
    session.add(task)
    session.flush()
    for item in extraction.evidence_items:
        session.add(Evidence(**item.model_dump(), task_id=task.id, created_at=utcnow()))
    units = [unit.model_dump() for unit in extraction.knowledge_units]
    draft = Draft(
        id=fixture["draft"]["id"],
        task_id=task.id,
        revision=1,
        status="draft",
        knowledge_units=units,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(draft)
    session.flush()
    session.add(
        DraftRevision(
            draft_id=draft.id,
            revision=1,
            knowledge_units=units,
            actor_id="system",
            reason="seed",
            created_at=utcnow(),
        )
    )
    for index, gap in enumerate(
        provider.generate_clarifications(extraction.knowledge_units, context), 1
    ):
        session.add(
            Clarification(
                id=f"clar_{index:03}",
                task_id=task.id,
                draft_id=draft.id,
                **gap.model_dump(),
                status="pending",
                created_at=utcnow(),
            )
        )
    session.flush()
    return True
