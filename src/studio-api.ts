export type StudioRole = 'expert' | 'admin';
export type TacitField = 'action' | 'cue' | 'interpretation' | 'decision' | 'exception';
export interface StudioUnit { id: string; action: string; cue: string | null; interpretation: string | null; decision: string | null; exception: string | null; evidence_ids: string[]; review_status: string }
export interface StudioEvidence { id: string; type: string; content: string | null; source_label: string; author: string; start_ms: number | null; end_ms: number | null }
export interface StudioOverview {
  task: { id: string; title: string; equipment: string; source_label: string };
  draft: { revision: number; status: string; knowledge_units: StudioUnit[]; clarifications: { id: string; question: string; status: string; knowledge_unit_id: string }[] };
  evidence: StudioEvidence[];
  evaluation: null | { id: string; revision: number; passed: boolean; issues: { knowledge_unit_id: string; problem: string }[]; created_at: string };
  authorization: null | { id: string; evaluation_id: string; revision: number; expert_id: string; status: string; note: string; release_id: string | null };
  audit: { id: string; action: string; actor_id: string; details: Record<string, unknown>; created_at: string }[];
  active_release: null | { id: string; version: number; approved_by: string; approved_at: string; approval_note: string; content_hash: string; knowledge_units: StudioUnit[] };
}
let token: string | null = null;
let activeRole: StudioRole | null = null;
async function request<T>(role: StudioRole, path: string, method = 'GET', body?: unknown): Promise<T> {
  if (!token || activeRole !== role) {
    token = null;
    const login = await fetch('/api/v1/auth/demo-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ demo_user: role }) });
    const result = await login.json();
    if (!login.ok) throw new Error(result.error?.message ?? 'Studio sign-in failed.');
    token = result.access_token; activeRole = role;
  }
  const response = await fetch(`/api/v1${path}`, { method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const result = await response.json();
  if (!response.ok) { if (response.status === 401) token = null; throw new Error(result.error?.message ?? 'The studio request failed.'); }
  return result as T;
}
const taskPath = (id: string) => `/studio/tasks/${encodeURIComponent(id)}`;
export const studioApi = {
  tasks: (role: StudioRole) => request<{ items: { id: string; title: string }[] }>(role, '/tasks'),
  overview: (role: StudioRole, id: string) => request<StudioOverview>(role, taskPath(id)),
  save: (role: StudioRole, id: string, revision: number, unit: StudioUnit, fields: Partial<Record<TacitField, string | null>>) => request(role, `/tasks/${encodeURIComponent(id)}/draft`, 'PATCH', { expected_revision: revision, changes: [{ knowledge_unit_id: unit.id, fields }] }),
  evaluate: (role: StudioRole, id: string, revision: number) => request(role, `${taskPath(id)}/evaluate`, 'POST', { expected_revision: revision }),
  authorize: (role: StudioRole, id: string, evaluationId: string, note: string) => request(role, `${taskPath(id)}/authorize`, 'POST', { evaluation_id: evaluationId, expert_id: 'expert_001', note }),
  publish: (role: StudioRole, id: string, revision: number, note: string) => request(role, `${taskPath(id)}/publish`, 'POST', { expected_revision: revision, approval_note: note }),
  clarify: (role: StudioRole, id: string, revision: number, answer: string, disposition: 'answered' | 'deferred' | 'unobservable' | 'premise_rejected' = 'answered') => request(role, `/clarifications/${encodeURIComponent(id)}/respond`, 'POST', { expected_draft_revision: revision, disposition, answer }),
};
