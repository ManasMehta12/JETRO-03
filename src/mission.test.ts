import { describe, expect, it } from 'vitest';
import { getMissionCheckpoints, getMissionProgress } from './mission';
import { createAttempt, transition } from './simulation';
import { completeActions, inspectionActions, workshopActions } from './test-fixtures';

describe('mission completion and progress', () => {
  it('starts at zero with twelve unique checkpoints worth 600 XP', () => {
    const progress = getMissionProgress(createAttempt());
    expect(progress).toMatchObject({ completed: 0, total: 12, xp: 0, maxXP: 600, complete: false });
    expect(new Set(progress.checkpoints.map(checkpoint => checkpoint.id)).size).toBe(12);
  });
  it('awards kit and observation separately and maintains monotonic deterministic progress', () => {
    let state = createAttempt(); let previousXP = 0;
    for (const action of [...completeActions, 'continue']) {
      state = transition(state, action);
      const progress = getMissionProgress(state);
      expect(progress.xp).toBeGreaterThanOrEqual(previousXP);
      expect(progress.xp).toBe(progress.completed * 50);
      expect(progress.xp).toBeLessThanOrEqual(600);
      previousXP = progress.xp;
    }
    expect(getMissionProgress(state)).toMatchObject({ completed: 12, xp: 600, complete: true });
    expect(getMissionProgress(inspectionActions.slice(0, 4).reduce(transition, createAttempt())).xp).toBe(50);
    expect(getMissionProgress(inspectionActions.reduce(transition, createAttempt())).xp).toBe(100);
  });
  it('requires supported judgment for the final checkpoint in each scenario', () => {
    const clear = completeActions.reduce(transition, createAttempt());
    const uncertain = completeActions.reduce(transition, createAttempt('uncertain'));
    expect(getMissionProgress(clear)).toMatchObject({ completed: 11, xp: 550, complete: false });
    expect(getMissionProgress(transition(clear, 'continue')).complete).toBe(true);
    expect(getMissionProgress(transition(uncertain, 'escalate')).complete).toBe(true);
    for (const state of [transition(clear, 'escalate'), transition(uncertain, 'continue')]) {
      expect(getMissionProgress(state)).toMatchObject({ completed: 11, xp: 550, complete: false });
      expect(getMissionCheckpoints(state).find(checkpoint => checkpoint.id === 'decision')?.complete).toBe(false);
    }
  });
  it('tracks quiz completion separately from correctness, preserving knowledge score', () => {
    const wrong = [...inspectionActions, ...workshopActions, 'answer:q1:a', 'answer:q2:a', 'answer:q3:a', 'continue'].reduce(transition, createAttempt());
    expect(wrong.scores.knowledge).toBe(0);
    expect(getMissionProgress(wrong)).toMatchObject({ completed: 12, xp: 600, complete: true });
  });
});
