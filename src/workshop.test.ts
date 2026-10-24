import { describe, expect, it } from 'vitest';
import { createWorkshop, getWorkshopCheckpoints, getWorkshopObjective, isWorkshopReady, workshopTransition, type WorkshopState } from './workshop';

const solution = [
  'pick:base', 'place:base', 'pick:housing', 'place:housing', 'tool:alignment-jig', 'adjust:left', 'adjust:left',
  'pick:shaft', 'place:shaft', 'tool:bearing-sleeve', 'pick:bearing', 'place:bearing', 'press', 'press', 'press',
  'tool:hex-key', 'tighten:A', 'tighten:C', 'tighten:B', 'tighten:D', 'tool:handwheel', 'turn', 'turn', 'turn', 'verify',
];
const through = (lastAction: string) => solution.slice(0, solution.indexOf(lastAction) + 1).reduce(workshopTransition, createWorkshop());
function expectRejected(state: WorkshopState, actions: string[]) {
  const snapshot = JSON.stringify(state);
  for (const action of actions) { expect(() => workshopTransition(state, action), action).toThrow(); expect(JSON.stringify(state)).toBe(snapshot); }
}

describe('interactive workshop assembly', () => {
  it('replays a full deterministic build with eight checkpoints and exactly 400 XP', () => {
    const build = () => solution.reduce(workshopTransition, createWorkshop());
    expect(build()).toEqual(build());
    expect(build()).toMatchObject({ placed: { base: true, housing: true, shaft: true, bearing: true }, heldPart: null, alignment: 0, seatDepth: 3, bolts: ['A', 'C', 'B', 'D'], turns: 3, completed: true, mistakes: 0, xp: 400, log: solution });
    expect(isWorkshopReady(build())).toBe(true);
    expect(getWorkshopCheckpoints(build())).toHaveLength(8);
    expect(getWorkshopCheckpoints(build()).every(checkpoint => checkpoint.complete)).toBe(true);
  });
  it('requires picking and sequential placement, with no mutation on mistakes', () => {
    const initial = createWorkshop();
    expectRejected(initial, ['place:base', 'place:housing', 'place:shaft', 'place:bearing', 'pick:unknown', 'tool:unknown', 'unknown', 'verify']);
    for (const part of ['housing', 'shaft', 'bearing']) {
      expectRejected(workshopTransition(initial, `pick:${part}`), [`place:${part}`]);
    }
    expectRejected(through('place:base'), ['pick:base', 'place:base']);
    expectRejected(through('pick:housing'), ['pick:housing']);
  });
  it('enforces alignment tool, housing prerequisite, detent bounds and post-insertion lock', () => {
    expectRejected(createWorkshop(), ['adjust:left', 'adjust:right']);
    expectRejected(workshopTransition(createWorkshop(), 'tool:alignment-jig'), ['adjust:left']);
    expectRejected(through('place:housing'), ['adjust:left']);
    expectRejected(through('tool:alignment-jig'), ['adjust:right']);
    let state = through('tool:alignment-jig');
    for (let count = 0; count < 4; count++) state = workshopTransition(state, 'adjust:left');
    expect(state.alignment).toBe(-2); expectRejected(state, ['adjust:left']);
    expectRejected(through('place:shaft'), ['adjust:left', 'adjust:right']);
    expectRejected(workshopTransition(through('place:housing'), 'pick:shaft'), ['place:shaft']);
    expectRejected(workshopTransition(through('tool:alignment-jig'), 'pick:shaft'), ['place:shaft']);
  });
  it('requires the sleeve, bearing placement and exactly three press increments', () => {
    expectRejected(through('place:shaft'), ['press']);
    expectRejected(through('tool:bearing-sleeve'), ['press']);
    expectRejected(workshopTransition(through('place:shaft'), 'pick:bearing'), ['place:bearing']);
    let state = through('place:bearing');
    expect(state.seatDepth).toBe(0);
    for (let count = 1; count <= 3; count++) { state = workshopTransition(state, 'press'); expect(state.seatDepth).toBe(count); }
    expectRejected(state, ['press']);
    expectRejected(workshopTransition(through('place:bearing'), 'tool:hex-key'), ['press']);
  });
  it('enforces tool, seating and the A C B D cross pattern without awarding repeated bolts', () => {
    expectRejected(through('place:bearing'), ['tighten:A']);
    expectRejected(workshopTransition(through('place:bearing'), 'tool:hex-key'), ['tighten:A']);
    let state = through('tool:hex-key');
    for (const bolt of ['A', 'C', 'B', 'D']) {
      const wrongBolts = ['A', 'B', 'C', 'D', 'Z'].filter(candidate => candidate !== bolt).map(candidate => `tighten:${candidate}`);
      expectRejected(state, wrongBolts);
      state = workshopTransition(state, `tighten:${bolt}`);
    }
    expect(state.bolts).toEqual(['A', 'C', 'B', 'D']);
    expectRejected(state, ['tighten:A', 'tighten:D']);
  });
  it('requires secured bolts, handwheel and three rotations before final verification', () => {
    expectRejected(through('tighten:D'), ['turn', 'verify']);
    expectRejected(workshopTransition(through('tool:hex-key'), 'tool:handwheel'), ['turn']);
    let state = through('tool:handwheel');
    for (let count = 1; count <= 3; count++) {
      expectRejected(state, ['verify']);
      state = workshopTransition(state, 'turn');
      expect(state.turns).toBe(count);
    }
    expectRejected(state, ['turn']);
    expect(isWorkshopReady(state)).toBe(false);
    expect(isWorkshopReady(workshopTransition(state, 'verify'))).toBe(true);
  });
  it('awards XP only at checkpoint completion and never for tool swapping or intermediate steps', () => {
    let state = createWorkshop();
    for (const action of solution) {
      const before = state;
      state = workshopTransition(state, action);
      const earned = getWorkshopCheckpoints(state).filter((checkpoint, index) => checkpoint.complete && !getWorkshopCheckpoints(before)[index].complete).reduce((sum, checkpoint) => sum + checkpoint.xp, 0);
      expect(state.xp - before.xp).toBe(earned);
    }
    let swapped = through('place:base');
    for (let i = 0; i < 10; i++) { swapped = workshopTransition(swapped, 'tool:hex-key'); swapped = workshopTransition(swapped, 'tool:handwheel'); }
    expect(swapped.xp).toBe(50);
  });
  it('preserves frozen nested inputs and protects terminal state from every action', () => {
    const initial = createWorkshop();
    Object.freeze(initial.placed); Object.freeze(initial.bolts); Object.freeze(initial.log); Object.freeze(initial);
    expect(workshopTransition(initial, 'pick:base').heldPart).toBe('base');
    expect(initial.heldPart).toBeNull();
    const terminal = solution.reduce(workshopTransition, createWorkshop());
    expectRejected(terminal, [...solution, 'unknown']);
  });
  it('returns contextual objectives in complete assembly order', () => {
    const targets: string[] = [];
    let state = createWorkshop();
    for (const action of solution) {
      const objective = getWorkshopObjective(state);
      expect(objective.title.length).toBeGreaterThan(0); expect(objective.instruction.length).toBeGreaterThan(0);
      if (targets.at(-1) !== objective.target) targets.push(objective.target);
      state = workshopTransition(state, action);
    }
    expect(targets).toEqual(['base', 'housing', 'shaft', 'bearing', 'press', 'bolt', 'handwheel', 'verify']);
    expect(getWorkshopObjective(state).action).toBeNull();
  });
});
