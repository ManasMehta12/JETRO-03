import { describe, expect, it } from 'vitest';
import { availableActions, createAttempt, isTerminal, questions, transition, type AttemptState } from './simulation';
import { completeActions, inspectionActions, quizActions, workshopActions } from './test-fixtures';

const ready = (scenario: 'standard' | 'uncertain' = 'standard', mode: 'guided' | 'assessment' = 'guided') => completeActions.reduce(transition, createAttempt(scenario, mode));
function freeze(state: AttemptState) {
  Object.freeze(state.inspected); Object.freeze(state.questionAnswers); Object.freeze(state.scores); Object.freeze(state.log);
  Object.freeze(state.workshop.placed); Object.freeze(state.workshop.bolts); Object.freeze(state.workshop.log); Object.freeze(state.workshop); Object.freeze(state);
  return state;
}
describe('deterministic bearing assembly integration', () => {
  it('replays a complete build and quiz deterministically with bounded independent scores', () => {
    const play = () => transition(ready(), 'continue');
    expect(play()).toEqual(play());
    expect(play()).toMatchObject({ phase: 'complete', revision: completeActions.length + 1, criticalError: false, scores: { procedure: 100, judgment: 100, knowledge: 100 }, workshop: { completed: true, xp: 400 } });
    expect(play().log.map(e => e.revision)).toEqual(Array.from({ length: play().revision }, (_, i) => i + 1));
    expect(new Set(play().log.map(e => e.id)).size).toBe(play().revision);
  });
  it('distinguishes supported escalation from releasing unresolved evidence', () => {
    expect(transition(ready('uncertain'), 'escalate')).toMatchObject({ phase: 'escalated', criticalError: false, scores: { procedure: 100, judgment: 100 } });
    expect(transition(ready('uncertain'), 'continue')).toMatchObject({ phase: 'complete', criticalError: true, scores: { procedure: 100, judgment: 0 } });
    expect(transition(ready(), 'escalate').scores.judgment).toBe(60);
  });
  it('blocks decisions before every required physical checkpoint and quiz answer', () => {
    let state = createAttempt();
    for (const action of completeActions) {
      expect(() => transition(state, 'continue')).toThrow(); expect(() => transition(state, 'escalate')).toThrow();
      expect(availableActions(state).filter(a => a.kind === 'decision').every(a => !a.enabled)).toBe(true);
      state = transition(state, action);
    }
    expect(availableActions(state).filter(a => a.kind === 'decision').every(a => a.enabled)).toBe(true);
    expect(() => transition(quizActions.reduce(transition, createAttempt()), 'continue')).toThrow();
  });
  it('rejects old animation shortcuts, duplicate inspections and assembly before observations', () => {
    const initial = createAttempt();
    for (const action of ['align-shaft', 'seat-bearing', 'verify-fit', 'record-observation', 'workshop:pick:base', 'unknown']) expect(() => transition(initial, action)).toThrow();
    const inspected = transition(initial, 'inspect-bearing');
    expect(() => transition(inspected, 'inspect-bearing')).toThrow();
    expect(inspected.scores.procedure).toBe(5);
    expect(availableActions(inspected).some(a => a.id === 'inspect-bearing')).toBe(false);
    expect(availableActions(initial).some(a => a.kind === 'operation')).toBe(false);
  });
  it('derives flags and procedure points exclusively from accepted workshop state', () => {
    let state = inspectionActions.reduce(transition, createAttempt());
    expect(state.scores.procedure).toBe(25);
    for (const action of workshopActions) {
      state = transition(state, action);
      expect(state.aligned).toBe(state.workshop.placed.shaft);
      expect(state.seated).toBe(state.workshop.seatDepth === 3);
      expect(state.verified).toBe(state.workshop.completed);
      expect(state.scores.procedure).toBe(25 + Math.round(state.workshop.xp / 400 * 75));
      expect(state.scores.knowledge).toBe(0); expect(state.scores.judgment).toBe(0);
    }
    expect(state.phase).toBe('decision');
  });
  it('never mutates frozen nested state on accepted or rejected actions', () => {
    const state = freeze(inspectionActions.reduce(transition, createAttempt()));
    expect(transition(state, 'workshop:pick:base').workshop.heldPart).toBe('base');
    expect(state.workshop.heldPart).toBeNull(); expect(state.workshop.log).toEqual([]);
    expect(() => transition(state, 'workshop:place:base')).toThrow();
    expect(transition(state, 'answer:q1:b').questionAnswers).toEqual({ q1: 'b' });
    expect(state.questionAnswers).toEqual({});
  });
  it('keeps mode independent of authoritative outcomes', () => {
    const guided = transition(ready('uncertain', 'guided'), 'escalate');
    const assessment = transition(ready('uncertain', 'assessment'), 'escalate');
    expect(assessment.scores).toEqual(guided.scores); expect(assessment.outcome).toEqual(guided.outcome); expect(assessment.workshop).toEqual(guided.workshop);
  });
  it('scores questions once, rejects malformed answers, and permits completion with wrong answers', () => {
    let state = createAttempt();
    for (const q of questions) state = transition(state, `answer:${q.id}:${q.correctOptionId}`);
    expect(state.scores.knowledge).toBe(100); expect(state.scores.procedure).toBe(0);
    expect(() => transition(state, 'answer:q1:b')).toThrow();
    for (const id of ['answer:q99:a', 'answer:q1:z', 'answer:q1:b:extra', 'answer:q1']) expect(() => transition(createAttempt(), id)).toThrow();
    const wrongAnswers = [...inspectionActions, ...workshopActions, 'answer:q1:a', 'answer:q2:a', 'answer:q3:a', 'continue'].reduce(transition, createAttempt());
    expect(wrongAnswers.scores).toEqual({ procedure: 100, judgment: 100, knowledge: 0 });
  });
  it('protects terminal attempts against all workshop, question and decision actions', () => {
    for (const last of ['continue', 'escalate']) {
      const state = freeze(transition(ready(), last));
      expect(isTerminal(state)).toBe(true); expect(availableActions(state)).toEqual([]);
      for (const action of [...completeActions, 'continue', 'escalate']) expect(() => transition(state, action)).toThrow(/complete/);
    }
  });
});
