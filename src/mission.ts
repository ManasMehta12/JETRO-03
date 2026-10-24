import type { AttemptState } from './simulation';
import { isTerminal, questions } from './simulation';
import { getWorkshopCheckpoints } from './workshop';

export function getMissionCheckpoints(attempt: AttemptState) {
  return [
    { id: 'kit', title: 'Inspect the component kit', description: 'Record an inspection of all four parts.', complete: attempt.inspected.length === 4, xp: 50 },
    { id: 'observation', title: 'Read the observation card', description: 'Request the scenario evidence before touching the build.', complete: attempt.observationRecorded, xp: 50 },
    ...getWorkshopCheckpoints(attempt.workshop),
    { id: 'knowledge', title: 'Complete the knowledge check', description: 'Answer all three questions. Correctness is reported separately.', complete: questions.every(q => Object.hasOwn(attempt.questionAnswers, q.id)), xp: 50 },
    { id: 'decision', title: 'Make a supported decision', description: 'Release clear evidence or escalate the uncertain fit.', complete: isTerminal(attempt) && !attempt.criticalError && attempt.scores.judgment === 100, xp: 50 },
  ];
}
export function getMissionProgress(attempt: AttemptState) {
  const checkpoints = getMissionCheckpoints(attempt);
  const completed = checkpoints.filter(checkpoint => checkpoint.complete).length;
  return { checkpoints, completed, total: checkpoints.length, xp: checkpoints.filter(checkpoint => checkpoint.complete).reduce((sum, checkpoint) => sum + checkpoint.xp, 0), maxXP: checkpoints.reduce((sum, checkpoint) => sum + checkpoint.xp, 0), complete: checkpoints.every(checkpoint => checkpoint.complete) };
}
