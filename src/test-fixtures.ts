/** Shared deterministic interaction histories for unit tests. */
export const inspectionActions = ['inspect-base', 'inspect-housing', 'inspect-shaft', 'inspect-bearing', 'record-observation'];
export const workshopActions = [
  'pick:base', 'place:base', 'pick:housing', 'place:housing', 'tool:alignment-jig', 'adjust:left', 'adjust:left',
  'pick:shaft', 'place:shaft', 'tool:bearing-sleeve', 'pick:bearing', 'place:bearing', 'press', 'press', 'press',
  'tool:hex-key', 'tighten:A', 'tighten:C', 'tighten:B', 'tighten:D', 'tool:handwheel', 'turn', 'turn', 'turn', 'verify',
].map(action => `workshop:${action}`);
export const quizActions = ['answer:q1:b', 'answer:q2:b', 'answer:q3:c'];
export const completeActions = [...inspectionActions, ...workshopActions, ...quizActions];
