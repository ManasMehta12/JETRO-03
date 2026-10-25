export type StudioRole = 'expert' | 'admin';
export type TacitField = 'action' | 'cue' | 'interpretation' | 'decision' | 'exception';
export interface StudioUnit { id: string; action: string; cue: string | null; interpretation: string | null; decision: string | null; exception: string | null; evidence_ids: string[]; field_evidence?: Partial<Record<TacitField, string[]>>; review_status: string }
export interface StudioEvidence { id: string; type: string; content: string | null; source_label: string; author: string; start_ms: number | null; end_ms: number | null }
export interface CourseContent { version: number; script_text: string; script_filename: string; review_notes: string; video: { id: string; filename: string; duration_ms: number; sha256: string } | null; available: boolean }
export interface AnalysisConfig { course_source_hashes?: { with_review_notes: string; without_review_notes: string } | null; course_content?: CourseContent | null; media_upload_enabled?: boolean; enabled: boolean; reset_enabled?: boolean; mode: 'live' | 'unconfigured'; provider: string; model: string; source_notes: string; source_label: string | null; source_kind: string; rehearsal_available: boolean; rehearsal_source_notes: string | null; agent_roles: { stage: string; label: string }[]; notice: string }
export interface AnalysisProposal { id: string; knowledge_unit_id: string; field: TacitField; before: string | null; after: string; source_quote: string; rationale: string; video_evidence?: { media_id: string; start_ms: number; end_ms: number; modality: string } }
export interface LearningGap { id: string; knowledge_unit_id: string; field: TacitField; source_quote: string; missing_explanation: string; suggested_fix: string | null; expert_question: string; status: 'suggested_fix' | 'expert_required' | 'already_covered'; proposal_id: string | null; video_evidence?: AnalysisProposal['video_evidence'] | null }
export interface AnalysisRun { id: string; task_id: string; revision: number; source_notes: string; mode: 'live' | 'rehearsal'; status: 'running' | 'ready' | 'failed' | 'published' | 'applied'; stage: string; model?: string; source_label?: string; source_hash?: string; requested_by?: string; created_at?: string; updated_at?: string; proposals: AnalysisProposal[]; evaluation: { passed: boolean; issues: string[]; summary: string; learning_gaps?: LearningGap[]; replace_draft?: boolean; source_manifest?: { input_hash: string; include_review_notes: boolean; video: CourseContent['video']; script_filename: string }; unresolved_clarifications?: { id: string; question: string; knowledge_unit_id: string }[] } | null; error: { code: string; message: string } | null; release_id: string | null }
export interface StudioOverview {
  task: { id: string; title: string; equipment: string; source_label: string };
  draft: { revision: number; status: string; knowledge_units: StudioUnit[]; clarifications: { id: string; question: string; status: string; knowledge_unit_id: string }[] };
  evidence: StudioEvidence[];
  analysis_runs?: AnalysisRun[];
  evaluation_scope?: string;
  evaluation: null | { id: string; revision: number; passed: boolean; stale: boolean; issues: { knowledge_unit_id: string; problem: string }[]; created_at: string };
  authorization: null | { id: string; evaluation_id: string; revision: number; expert_id: string; status: string; note: string; release_id: string | null };
  audit: { id: string; action: string; actor_id: string; details: Record<string, unknown>; created_at: string }[];
  active_release: null | { id: string; version: number; approved_by: string; approved_at: string; approval_note: string; content_hash: string; knowledge_units: StudioUnit[] };
}
export interface StudioWorkspace { overview: StudioOverview; analysis: AnalysisConfig; latest_run: AnalysisRun | null; user: { id: string; role: string; display_name: string } }
let token: string | null = null;
let activeRole: StudioRole | null = null;
async function request<T>(role: StudioRole, path: string, method = 'GET', body?: unknown, allowMissing = false): Promise<T> {
  if (!token || activeRole !== role) {
    token = null;
    const login = await fetch('/api/v1/auth/demo-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ demo_user: role }) });
    const result = await login.json();
    if (!login.ok) throw new Error(result.error?.message ?? 'Studio sign-in failed.');
    token = result.access_token; activeRole = role;
  }
  const response = await fetch(`/api/v1${path}`, { method, headers: { Authorization: `Bearer ${token}`, ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }) }, ...(body === undefined ? {} : { body: body instanceof FormData ? body : JSON.stringify(body) }) });
  const result = await response.json();
  if (allowMissing && response.status === 404) return null as T;
  if (!response.ok) { if (response.status === 401) token = null; throw new Error(result.error?.message ?? 'The studio request failed.'); }
  return result as T;
}
const taskPath = (id: string) => `/studio/tasks/${encodeURIComponent(id)}`;
export const studioApi = {
  saveCourseContent: (role: StudioRole, id: string, version: number, changes: Partial<Pick<CourseContent, 'script_text' | 'script_filename' | 'review_notes'>>) => request<CourseContent>(role, `${taskPath(id)}/course-content`, 'PATCH', { expected_version: version, ...changes }),
  uploadVideo: (role: StudioRole, id: string, file: File) => { const body = new FormData(); body.append('file', file); return request(role, `/tasks/${encodeURIComponent(id)}/media`, 'POST', body); },
  reset: (role: StudioRole, id: string, revision: number) => request(role, `${taskPath(id)}/reset`, 'POST', { expected_revision: revision, confirm: 'RESET_EXPERT_DATA' }),
  workspace: (role: StudioRole) => request<StudioWorkspace>(role, '/studio/workspace'),
  tasks: (role: StudioRole) => request<{ items: { id: string; title: string }[] }>(role, '/tasks'),
  overview: (role: StudioRole, id: string) => request<StudioOverview>(role, taskPath(id)),
  analysisConfig: (role: StudioRole, id: string) => request<AnalysisConfig>(role, `${taskPath(id)}/analysis/config`),
  latestAnalysis: (role: StudioRole, id: string) => request<AnalysisRun | null>(role, `${taskPath(id)}/analysis/latest`, 'GET', undefined, true),
  analyze: (role: StudioRole, id: string, revision: number, sourceNotes: string, mode: 'live' | 'rehearsal' = 'live', useCourseContent = false, includeReviewNotes = true) => request<AnalysisRun>(role, `${taskPath(id)}/analysis`, 'POST', { expected_revision: revision, ...(useCourseContent ? {} : { source_notes: sourceNotes }), mode, use_course_content: useCourseContent, include_review_notes: includeReviewNotes }),
  publishAnalysis: (role: StudioRole, id: string, runId: string, revision: number, proposalIds: string[], note: string, deferUnanswered = false) => request<{ run: AnalysisRun; release: { id: string } }>(role, `${taskPath(id)}/analysis/${encodeURIComponent(runId)}/publish`, 'POST', { expected_revision: revision, proposal_ids: proposalIds, approval_note: note, defer_unanswered: deferUnanswered }),
  applyAnalysis: (role: StudioRole, id: string, runId: string, revision: number, proposalIds: string[], note: string) => request(role, `${taskPath(id)}/analysis/${encodeURIComponent(runId)}/apply`, 'POST', { expected_revision: revision, proposal_ids: proposalIds, approval_note: note }),
  save: (role: StudioRole, id: string, revision: number, unit: StudioUnit, fields: Partial<Record<TacitField, string | null>>) => request(role, `/tasks/${encodeURIComponent(id)}/draft`, 'PATCH', { expected_revision: revision, changes: [{ knowledge_unit_id: unit.id, fields }] }),
  evaluate: (role: StudioRole, id: string, revision: number) => request(role, `${taskPath(id)}/evaluate`, 'POST', { expected_revision: revision }),
  authorize: (role: StudioRole, id: string, evaluationId: string, expertId: string, note: string) => request(role, `${taskPath(id)}/authorize`, 'POST', { evaluation_id: evaluationId, expert_id: expertId, note }),
  publish: (role: StudioRole, id: string, revision: number, note: string) => request(role, `${taskPath(id)}/publish`, 'POST', { expected_revision: revision, approval_note: note }),
  clarify: (role: StudioRole, id: string, revision: number, answer: string, disposition: 'answered' | 'deferred' | 'unobservable' | 'premise_rejected' = 'answered', update?: { unitId: string; field: TacitField }) => request(role, `/clarifications/${encodeURIComponent(id)}/respond`, 'POST', { expected_draft_revision: revision, disposition, answer, ...(update ? { knowledge_update: { knowledge_unit_id: update.unitId, fields: { [update.field]: answer } } } : {}) }),
};
