import { describe, expect, it } from 'vitest';
import { createAttempt, transition } from './simulation';
import { restoreAttempt, serializeAttempt, STORAGE_KEY } from './persistence';
import { completeActions, inspectionActions } from './test-fixtures';
const envelope = (overrides: Record<string, unknown> = {}) => JSON.stringify({ version: 2, scenario: 'standard', mode: 'guided', actions: [], ...overrides });

describe('version 2 workshop history persistence', () => {
  it('round trips every partial build and terminal outcome across both modes and scenarios', () => {
    expect(STORAGE_KEY).toBe('takumi-bearing-v2');
    for (const scenario of ['standard', 'uncertain'] as const) for (const mode of ['guided', 'assessment'] as const) {
      let state = createAttempt(scenario, mode);
      for (const action of [...completeActions, scenario === 'standard' ? 'continue' : 'escalate']) {
        state = transition(state, action);
        expect(restoreAttempt(serializeAttempt(state))).toEqual(state);
      }
    }
  });
  it('rejects corrupt JSON, old schema and invalid or excessive envelopes', () => {
    const corrupt = [null, '', '{', 'null', 'false', '42', '"text"', '[]', '{}', envelope({ version: 1 }), envelope({ scenario: 'invented' }), envelope({ scenario: null }), envelope({ scenario: undefined }), envelope({ mode: 'unknown' }), envelope({ mode: null }), envelope({ mode: undefined }), envelope({ actions: null }), envelope({ actions: {} }), envelope({ actions: ['inspect-base', 42] }), envelope({ actions: Array(501).fill('inspect-base') })];
    for (const raw of corrupt) expect(restoreAttempt(raw)).toEqual(createAttempt());
  });
  it('rejects entire histories for old shortcuts, duplicates, bad assembly order and premature release', () => {
    const invalid = [['inspect-base', 'unknown'], ['inspect-base', 'inspect-base'], ['seat-bearing'], ['record-observation'], ['workshop:pick:base'], [...inspectionActions, 'workshop:place:base'], ['answer:q1:b', 'answer:q1:a'], ['continue'], [...completeActions, 'continue', 'workshop:verify']];
    for (const actions of invalid) expect(restoreAttempt(envelope({ actions }))).toEqual(createAttempt());
  });
  it('derives scores and physical state from history rather than trusting stored fields', () => {
    const state = restoreAttempt(envelope({ actions: ['inspect-base'], scores: { procedure: 100, judgment: 100 }, revision: 999, phase: 'complete', verified: true, workshop: { completed: true, xp: 400 } }));
    expect(state).toEqual(transition(createAttempt(), 'inspect-base'));
    expect(JSON.parse(serializeAttempt(state))).toEqual({ version: 2, scenario: 'standard', mode: 'guided', actions: ['inspect-base'] });
  });
  it('faithfully restores a fully completed but unsupported release', () => {
    const state = [...completeActions, 'continue'].reduce(transition, createAttempt('uncertain', 'assessment'));
    expect(restoreAttempt(serializeAttempt(state))).toEqual(state);
    expect(state.scores).toEqual({ procedure: 100, judgment: 0, knowledge: 100 });
    expect(state.criticalError).toBe(true);
  });
});
