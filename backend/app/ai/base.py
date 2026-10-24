from typing import Annotated, Protocol

from fastapi import Depends

from app.ai.schemas import (
    ApprovedContext,
    ClarificationCandidate,
    ExtractionResult,
    MediaReference,
    QAProviderResult,
    TaskContext,
)
from app.config import Settings, get_settings
from app.core.errors import AppError
from app.models.schemas import KnowledgeUnit


class KnowledgeAIProvider(Protocol):
    def extract_knowledge(self, media: MediaReference, task: TaskContext) -> ExtractionResult: ...

    def generate_clarifications(
        self, knowledge_units: list[KnowledgeUnit], task: TaskContext
    ) -> list[ClarificationCandidate]: ...

    def answer_question(
        self, question: str, language: str, context: ApprovedContext
    ) -> QAProviderResult: ...


def get_ai_provider(settings) -> KnowledgeAIProvider:
    from app.ai.fixture_provider import FixtureAIProvider

    if settings.ai_provider == "fixture":
        return FixtureAIProvider()
    raise AppError("AI_PROVIDER_UNAVAILABLE", "Configured AI provider is not available in V1.", 503)


def ai_provider(settings: Annotated[Settings, Depends(get_settings)]) -> KnowledgeAIProvider:
    return get_ai_provider(settings)
