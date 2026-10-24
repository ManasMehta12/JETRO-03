export type Mode='voice'|'text';
export type PersonaState='idle'|'listening'|'thinking'|'speaking'|'paused'|'error';
export interface Question {id:string;prompt:string;objective?:string;is_follow_up?:boolean;parent_question_id?:string|null}
export interface Turn {id:string;sequence:number;speaker:'learner'|'interviewer';text:string;question_id?:string;input_mode?:Mode;delivery?:string;quality_flag?:string;replacement_id?:string;created_at?:string}
export interface Session {id:string;attempt_id:string;release_id:string;bundle_id?:string;bundle_hash?:string;revision:number;status:string;input_mode:Mode;answered_count:number;question_count:number;follow_up_count?:number;current_question:Question|null;transcript:Turn[];last_event_sequence:number;active_seconds?:number;max_active_seconds?:number;evaluation_job_id?:string|null;result_id?:string|null}
export interface SessionEvent {id:string;sequence:number;session_revision:number;type:string;payload:Record<string,unknown>;created_at:string}
export interface SourceDocument {id:string;title:string;version:string;checksum?:string;media_type?:string;availability?:string;resolver_url?:string;evidence_ids?:string[]}
export interface Bootstrap {provider_mode:string;attempts:{id:string;title?:string;scenario_id:string;critical_error?:boolean;status?:string}[];release:{id:string;title?:string;documents?:SourceDocument[]}|null;learner_id:string;content_notice?:string}
export interface SourceReference {document_id:string;evidence_id?:string;release_id?:string;locator:string;excerpt:string}
export interface Assessment {dimension:string;status:string;score:number|null;rationale:string;answer_turn_ids?:string[];sources?:SourceReference[]}
export interface HumanReview {id:string;report_id:string;version:number;reviewer_id:string;reason:string;overrides:Assessment[];created_at:string}
export interface ReviewBundle {report_id:string;version:number;reviews:HumanReview[];report:Report}
export interface Report {reviews?:HumanReview[];id:string;version?:number;session_id:string;attempt_id:string;release_id:string;bundle_id?:string;bundle_hash?:string;rubric_version?:string;prompt_version?:string;model_config_version?:string;created_at?:string;completion:string;finish_reason:string;assessments:Assessment[];questions?:{question_id:string;feedback:string;sources?:SourceReference[];answer_turn_ids?:string[]}[];strengths:string[];misconceptions:string[];missed_topics:string[];recommendations:string[];playground_scores:{name:string;earned:number;available:number}[];critical_error:boolean;transcript:Turn[];source_index:{document:SourceDocument;usage:string}[];assessment_notice:string;provider_mode?:string}
export interface Evaluation {status:string;error_code?:string;retryable?:boolean;result_id?:string|null}
export interface VoiceEvent {kind:string;text?:string;append?:boolean}
