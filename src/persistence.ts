import { createAttempt, transition } from './simulation';
import type { AttemptState, ScenarioId, Mode } from './simulation';
export const STORAGE_KEY = 'takumi-bearing-v2';
export function restoreAttempt(raw: string | null): AttemptState {
  if (!raw) return createAttempt();
  try {
    const data: unknown = JSON.parse(raw);
    if (!data || typeof data !== 'object') return createAttempt();
    const record = data as { version?: number; scenario?: ScenarioId; mode?: Mode; actions?: unknown[] };
    if (record.version !== 2 || !['standard', 'uncertain'].includes(record.scenario as string) || !['guided', 'assessment'].includes(record.mode as string) || !Array.isArray(record.actions) || record.actions.length > 500) return createAttempt();
    let state = createAttempt(record.scenario, record.mode);
    for (const action of record.actions) {
      if (typeof action !== 'string') return createAttempt();
      state = transition(state, action);
    }
    return state;
  } catch { return createAttempt(); }
}
export function serializeAttempt(state: AttemptState): string {
  return JSON.stringify({ version: 2, scenario: state.scenarioId, mode: state.mode, actions: state.log.map(event => event.actionId) });
}
