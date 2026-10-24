export type StudioRole = 'expert' | 'admin';
export type TacitField = 'action' | 'cue' | 'interpretation' | 'decision' | 'exception';
export interface StudioUnit { id: string; action: string; cue: string | null; interpretation: string | null; decision: string | null; exception: string | null; evidence_ids: string[]; review_status: string }
export interface StudioEvidence { id: string; type: string; content: string | null; source_label: string; author: string; start_ms: number | null; end_ms: number | null }
export interface AnalysisConfig { enabled: boolean; mode: 'live' | 'unconfigured'; provider: string; model: string; source_notes: string; source_label: string | null; source_kind: string; rehearsal_available: boolean; rehearsal_source_notes: string | null; agent_roles: { stage: string; label: string }[]; notice: string }
export interface AnalysisProposal { id: string; knowledge_unit_id: string; field: TacitField; before: string | null; after: string; source_quote: string; rationale: string }
export interface AnalysisRun { id: string; task_id: string; revision: number; source_notes: string; mode: 'live' | 'rehearsal'; status: 'running' | 'ready' | 'failed' | 'published'; stage: string; proposals: AnalysisProposal[]; evaluation: { passed: boolean; issues: string[]; summary: string; unresolved_clarifications?: { id: string; question: string; knowledge_unit_id: string }[] } | null; error: { code: string; message: string } | null; release_id: string | null }
export interface StudioOverview {
  task: { id: string; title: string; equipment: string; source_label: string };
  draft: { revision: number; status: string; knowledge_units: StudioUnit[]; clarifications: { id: string; question: string; status: string; knowledge_unit_id: string }[] };
  evidence: StudioEvidence[];
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
  const response = await fetch(`/api/v1${path}`, { method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const result = await response.json();
  if (allowMissing && response.status === 404) return null as T;
  if (!response.ok) { if (response.status === 401) token = null; throw new Error(result.error?.message ?? 'The studio request failed.'); }
  return result as T;
}
const taskPath = (id: string) => `/studio/tasks/${encodeURIComponent(id)}`;
export const studioApi = {
  workspace: (role: StudioRole) => request<StudioWorkspace>(role, '/studio/workspace'),
  tasks: (role: StudioRole) => request<{ items: { id: string; title: string }[] }>(role, '/tasks'),
  overview: (role: StudioRole, id: string) => request<StudioOverview>(role, taskPath(id)),
  analysisConfig: (role: StudioRole, id: string) => request<AnalysisConfig>(role, `${taskPath(id)}/analysis/config`),
  latestAnalysis: (role: StudioRole, id: string) => request<AnalysisRun | null>(role, `${taskPath(id)}/analysis/latest`, 'GET', undefined, true),
  analyze: (role: StudioRole, id: string, revision: number, sourceNotes: string, mode: 'live' | 'rehearsal' = 'live') => request<AnalysisRun>(role, `${taskPath(id)}/analysis`, 'POST', { expected_revision: revision, source_notes: sourceNotes, mode }),
  publishAnalysis: (role: StudioRole, id: string, runId: string, revision: number, proposalIds: string[], note: string, deferUnanswered = false) => request<{ run: AnalysisRun; release: { id: string } }>(role, `${taskPath(id)}/analysis/${encodeURIComponent(runId)}/publish`, 'POST', { expected_revision: revision, proposal_ids: proposalIds, approval_note: note, defer_unanswered: deferUnanswered }),
  save: (role: StudioRole, id: string, revision: number, unit: StudioUnit, fields: Partial<Record<TacitField, string | null>>) => request(role, `/tasks/${encodeURIComponent(id)}/draft`, 'PATCH', { expected_revision: revision, changes: [{ knowledge_unit_id: unit.id, fields }] }),
  evaluate: (role: StudioRole, id: string, revision: number) => request(role, `${taskPath(id)}/evaluate`, 'POST', { expected_revision: revision }),
  authorize: (role: StudioRole, id: string, evaluationId: string, note: string) => request(role, `${taskPath(id)}/authorize`, 'POST', { evaluation_id: evaluationId, expert_id: 'expert_001', note }),
  publish: (role: StudioRole, id: string, revision: number, note: string) => request(role, `${taskPath(id)}/publish`, 'POST', { expected_revision: revision, approval_note: note }),
  clarify: (role: StudioRole, id: string, revision: number, answer: string, disposition: 'answered' | 'deferred' | 'unobservable' | 'premise_rejected' = 'answered', update?: { unitId: string; field: TacitField }) => request(role, `/clarifications/${encodeURIComponent(id)}/respond`, 'POST', { expected_draft_revision: revision, disposition, answer, ...(update ? { knowledge_update: { knowledge_unit_id: update.unitId, fields: { [update.field]: answer } } } : {}) }),
};
