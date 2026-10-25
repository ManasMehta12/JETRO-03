import json
from pathlib import Path

from app.ai.schemas import ExtractionResult
from app.core.errors import AppError
from app.services.evidence_service import validate_evidence_items
from app.services.gap_detection import detect_gaps

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "shaft_bearing_v1.json"


class FixtureAIProvider:
    def extract_knowledge(self, media, task):
        if media.fixture_id != "shaft_bearing_v1":
            raise AppError(
                "FIXTURE_NOT_AVAILABLE",
                "Only the shaft_bearing_v1 fixture can be processed in fixture mode.",
                422,
            )
        fixture = json.loads(FIXTURE_PATH.read_text())
        validate_evidence_items(fixture["evidence_items"], task.task_id)
        return ExtractionResult(
            knowledge_units=fixture["draft"]["knowledge_units"],
            evidence_items=fixture["evidence_items"],
            provenance={"provider": "fixture", "fixture_id": fixture["fixture_id"]},
        )

    def generate_clarifications(self, knowledge_units, task):
        return detect_gaps(knowledge_units)

    def answer_question(self, question, language, context):
        from app.services.qa_matching import deterministic_answer

        return deterministic_answer(question, language, context)
