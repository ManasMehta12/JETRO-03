"""Closed request schemas prevent browser-supplied scoring or state."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ClosedModel(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class StartRequest(ClosedModel):
    attempt_id:str=Field(min_length=1,max_length=128)
    input_mode:Literal['voice','text']='text'
class RevisionRequest(ClosedModel):
    expected_revision:int=Field(ge=0)
class AnswerRequest(RevisionRequest):
    question_id:str=Field(min_length=1,max_length=128)
    client_turn_id:str=Field(min_length=1,max_length=128)
    text:str=Field(min_length=1,max_length=10000)
class ResumeRequest(RevisionRequest):
    input_mode:Literal['voice','text']
class RepeatRequest(RevisionRequest):
    question_id:str=Field(min_length=1,max_length=128)
class FlagRequest(RevisionRequest):
    turn_id:str=Field(min_length=1,max_length=128)
    reason:str=Field(min_length=1,max_length=500)
class ConnectionReadyRequest(RevisionRequest):
    connection_id:str=Field(min_length=1,max_length=128)

class ConnectionRequest(RevisionRequest):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=False)
    sdp_offer:str=Field(min_length=1,max_length=100000)
    microphone_consent:Literal[True]

# Response contracts are closed and distinct from private rubric/source payloads.
from typing import Optional, List, Dict, Any, Union, Annotated

class InterviewTurnSchema(ClosedModel):
    id:str
    sequence:int
    question_id:Optional[str]
    speaker:Literal['learner','interviewer']
    text:str
    input_mode:Literal['voice','text']
    delivery:Literal['completed','interrupted','unconfirmed']
    replacement_id:Optional[str]=None
    quality_flag:Optional[str]=None
    created_at:str

class VivaQuestionSchema(ClosedModel):
    id:str
    objective:Literal['explanation','changed_condition','limits']
    prompt:str
    is_follow_up:bool
    parent_question_id:Optional[str]=None

class VivaSessionSchema(ClosedModel):
    id:str
    attempt_id:str
    learner_id:str
    release_id:str
    bundle_id:str
    bundle_hash:str
    rubric_version:str
    prompt_version:str
    model_config_version:str
    status:Literal['created','connecting','in_progress','paused','evaluating','completed','failed']
    input_mode:Literal['voice','text']
    revision:int
    question_count:int
    answered_count:int
    follow_up_count:int
    current_question:Optional[VivaQuestionSchema]
    last_event_sequence:int
    evaluation_job_id:Optional[str]
    result_id:Optional[str]
    active_seconds:float
    max_active_seconds:int
    transcript:List[InterviewTurnSchema]=Field(default_factory=list)
    created_at:str
    expires_at:str

class EvaluationJobSchema(ClosedModel):
    id:str
    session_id:str
    status:Literal['queued','running','completed','failed']
    attempt_count:int
    result_id:Optional[str]
    error_code:Optional[str]
    retryable:bool

class AnswerResponse(ClosedModel):
    session:VivaSessionSchema
    turn:InterviewTurnSchema

class FlagResponse(AnswerResponse):
    replacement_requested:bool

class ConnectionResponse(ClosedModel):
    connection_id:str
    sdp_answer:str
    session:VivaSessionSchema

class SourceDocumentSchema(ClosedModel):
    id:str
    title:str
    version:str
    checksum:str
    media_type:str
    resolver_url:str
    evidence_ids:List[str]
    availability:Literal['available','unavailable']

class SourceReferenceSchema(ClosedModel):
    release_id:str
    document_id:str
    evidence_id:str
    locator:str
    excerpt:str

class RubricAssessmentSchema(ClosedModel):
    dimension:Literal['technical_correctness','explanation_quality','evidence_use','recognition_of_limits']
    status:Literal['assessed','not_assessed','needs_review']
    score:Optional[int]=Field(ge=0,le=4)
    rationale:str
    answer_turn_ids:List[str]
    sources:List[SourceReferenceSchema]

class QuestionAssessmentSchema(ClosedModel):
    question_id:str
    answer_turn_ids:List[str]
    feedback:str
    sources:List[SourceReferenceSchema]

class QuestionCoverageSchema(ClosedModel):
    question_id:str
    objective:Literal['explanation','changed_condition','limits']
    status:Literal['unanswered','answered','not_assessed']
    answer_turn_ids:List[str]
    follow_up_count:int=Field(ge=0,le=1)

class DimensionScoreSchema(ClosedModel):
    name:str
    earned:int=Field(ge=0)
    available:int=Field(ge=0)

class ReportSourceSchema(ClosedModel):
    document:SourceDocumentSchema
    usage:Literal['cited','available_unused','unavailable']

class VivaReportSchema(ClosedModel):
    id:str
    version:int
    session_id:str
    attempt_id:str
    release_id:str
    bundle_id:str
    bundle_hash:str
    rubric_version:str
    prompt_version:str
    model_config_version:str
    created_at:str
    snapshot_hash:str
    completion:Literal['complete','incomplete']
    finish_reason:Literal['questions_complete','learner_finished','time_limit','expired']
    coverage:List[QuestionCoverageSchema]
    transcript:List[InterviewTurnSchema]
    playground_scores:List[DimensionScoreSchema]
    critical_error:bool
    assessments:List[RubricAssessmentSchema]
    questions:List[QuestionAssessmentSchema]
    strengths:List[str]
    misconceptions:List[str]
    missed_topics:List[str]
    recommendations:List[str]
    source_index:List[ReportSourceSchema]
    assessment_notice:str

class PublicReleaseSchema(ClosedModel):
    id:str
    task_id:str
    title:str
    content_hash:str
    content_status:Optional[str]
    documents:List[SourceDocumentSchema]
    evidence:List[Dict[str,Any]]
    units:List[Dict[str,Any]]

class DocumentResponse(ClosedModel):
    document:SourceDocumentSchema
    evidence:List[Dict[str,Any]]

class AttemptSummarySchema(ClosedModel):
    id:str
    title:str
    scenario_id:str
    status:str
    critical_error:bool
    release_id:str

class BootstrapSchema(ClosedModel):
    provider_mode:Literal['fixture','openai']
    learner_id:str
    content_notice:str
    attempts:List[AttemptSummarySchema]
    release:Optional[PublicReleaseSchema]

class ErrorSchema(ClosedModel):
    code:str
    message:str
    details:Dict[str,Any]

class SessionPayload(ClosedModel):
    session:VivaSessionSchema
class TurnPayload(ClosedModel):
    turn:InterviewTurnSchema
class QuestionPayload(ClosedModel):
    question:VivaQuestionSchema
class EvaluationPayload(ClosedModel):
    evaluation:EvaluationJobSchema
class ErrorPayload(ClosedModel):
    error:ErrorSchema
class EventBase(ClosedModel):
    id:str
    sequence:int
    session_revision:int
    created_at:str
class SessionUpdatedEvent(EventBase):
    type:Literal['session_updated']
    payload:SessionPayload
class TurnCommittedEvent(EventBase):
    type:Literal['turn_committed']
    payload:TurnPayload
class QuestionPresentedEvent(EventBase):
    type:Literal['question_presented']
    payload:QuestionPayload
class EvaluationUpdatedEvent(EventBase):
    type:Literal['evaluation_updated']
    payload:EvaluationPayload
class ErrorEvent(EventBase):
    type:Literal['error']
    payload:ErrorPayload
SessionEventSchema=Annotated[Union[SessionUpdatedEvent,TurnCommittedEvent,QuestionPresentedEvent,EvaluationUpdatedEvent,ErrorEvent],Field(discriminator='type')]
class EventsResponse(ClosedModel):
    events:List[SessionEventSchema]
    next_after:int
    has_more:bool
