from pydantic import BaseModel, Field

from app.models.schemas import Claim, EvidenceType, GapType, KnowledgeUnit, QAStatus, SourceLabel


class TaskContext(BaseModel):
    task_id: str
    title: str
    equipment: str
    language: str


class MediaReference(BaseModel):
    fixture_id: str | None = None
    media_id: str | None = None


class Provenance(BaseModel):
    provider: str
    model_id: str | None = None
    prompt_version: str | None = None
    fixture_id: str | None = None


class ExtractedEvidence(BaseModel):
    id: str
    type: EvidenceType
    author_id: str
    author_label: str
    content: str | None = None
    media_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    source_label: SourceLabel


class ExtractionResult(BaseModel):
    knowledge_units: list[KnowledgeUnit]
    evidence_items: list[ExtractedEvidence]
    provenance: Provenance


class ClarificationCandidate(BaseModel):
    knowledge_unit_id: str
    gap_type: GapType
    priority: int
    question: str


class ApprovedContext(BaseModel):
    release_id: str
    knowledge_units: list[KnowledgeUnit]
    evidence_ids: set[str]


class QAProviderResult(BaseModel):
    status: QAStatus
    claims: list[Claim] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    provenance: Provenance
