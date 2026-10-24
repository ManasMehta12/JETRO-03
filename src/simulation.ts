import { createWorkshop, isWorkshopReady, workshopTransition } from './workshop';
import type { WorkshopState } from './workshop';
/** Frozen, illustrative training content. No physical engineering calculations or live AI. */
export type ScenarioId = 'standard' | 'uncertain';
export type Mode = 'guided' | 'assessment';
export type ComponentId = 'base' | 'housing' | 'shaft' | 'bearing';
export type Phase = 'inspect' | 'align' | 'seat' | 'verify' | 'decision' | 'complete' | 'escalated';
export type ActionId = `inspect-${ComponentId}` | 'record-observation' | 'align-shaft' | 'seat-bearing' | 'verify-fit' | 'continue' | 'escalate' | `answer:${string}:${string}` | `workshop:${string}`;
export interface EventEntry { id: string; revision: number; actionId: string; title: string; detail: string }
export interface AttemptState {
  workshop: WorkshopState;
  id: string; scenarioId: ScenarioId; mode: Mode; revision: number; phase: Phase;
  selectedComponent: ComponentId | null; inspected: ComponentId[]; observationRecorded: boolean;
  aligned: boolean; seated: boolean; verified: boolean; questionAnswers: Record<string, string>;
  log: EventEntry[]; scores: { procedure: number; judgment: number; knowledge: number };
  outcome: string | null; criticalError: boolean;
}
export interface ActionDefinition { id: ActionId; label: string; description: string; kind: 'inspection' | 'operation' | 'decision'; enabled: boolean }
export const componentInfo: Record<ComponentId, { name: string; description: string; inspection: string }> = {
  base: { name: 'Fixture base', description: 'The reference platform supporting the assembly.', inspection: 'The authored base datum is clear and the fixture is stable.' },
  housing: { name: 'Bearing housing', description: 'The outer support around the bearing.', inspection: 'The housing reference face is visible; no obstruction is depicted.' },
  shaft: { name: 'Drive shaft', description: 'The central shaft passing through the bearing.', inspection: 'The shaft reference axis is visible. Alignment has not yet been checked.' },
  bearing: { name: 'Rolling bearing', description: 'The modeled inner ring, outer ring and rolling elements.', inspection: 'The bearing rings are identified. The view alone cannot establish fit quality.' },
};
export const scenarios = [
  { id: 'standard' as const, title: 'A clean assembly', subtitle: 'Inspect, align, seat and verify', description: 'Complete the authored assembly sequence and support your release decision with the recorded checks.', observation: 'The fixture card records matching reference marks and a clear housing face. Complete the remaining checks before deciding.', verification: 'The scripted check confirms reference alignment and a flush seated position. All required observations are recorded.', expectedDecision: 'continue' as const, difficulty: 'Foundation', duration: '4–6 min' },
  { id: 'uncertain' as const, title: 'The uncertain fit', subtitle: 'Know when to stop and escalate', description: 'Follow the same inspection sequence, then judge whether the supplied evidence is enough to release the assembly.', observation: 'A previous inspection note flags an unconfirmed housing reference. Continue only the simulated checks; release requires resolved evidence.', verification: 'The scripted visual check is inconclusive: a reference gap remains ambiguous and no approved fit measurement is supplied.', expectedDecision: 'escalate' as const, difficulty: 'Judgment', duration: '4–6 min' },
];
export const insights = [
  { id: 'inspect', title: 'Observe before acting', body: 'Select each part and record its inspection. Rotating a model does not record evidence.', evidence: 'Illustrative demo note · E-01' },
  { id: 'align', title: 'References matter', body: 'The animation shows an authored alignment state; it does not measure tolerances or validate a real assembly.', evidence: 'Illustrative demo note · E-02' },
  { id: 'verify', title: 'A plausible view is not proof', body: 'The decision follows the supplied check result. An uncertain result is a reason to escalate.', evidence: 'Illustrative demo note · E-03' },
];
export const questions = [
  { id: 'q1', title: 'What makes an inspection count?', prompt: 'You have rotated and selected the bearing. What records an inspection?', options: [{ id: 'a', label: 'The part becomes highlighted' }, { id: 'b', label: 'Use the explicit inspection action' }, { id: 'c', label: 'Spend more time viewing it' }], correctOptionId: 'b', feedback: 'Only the explicit inspection action records an event. Camera movement and selection do not establish evidence.' },
  { id: 'q2', title: 'What does seating prove?', prompt: 'The bearing reaches its seated position in the animation. What can you conclude?', options: [{ id: 'a', label: 'The real assembly is mechanically safe' }, { id: 'b', label: 'The authored seating step is complete; verification is still required' }, { id: 'c', label: 'No further evidence is needed' }], correctOptionId: 'b', feedback: 'A visual animation completes a training step. It does not calculate fit, force, stress or real mechanical safety.' },
  { id: 'q3', title: 'How should uncertainty be handled?', prompt: 'The final check is inconclusive and approved measurements are missing. What is the supported decision?', options: [{ id: 'a', label: 'Continue because the model looks aligned' }, { id: 'b', label: 'Repeat the animation until it looks correct' }, { id: 'c', label: 'Stop release and escalate the unresolved evidence' }], correctOptionId: 'c', feedback: 'Escalation preserves the unresolved observation for review. Confidence in a rendering cannot replace missing evidence.' },
];
const components = Object.keys(componentInfo) as ComponentId[];
export const isTerminal = (state: AttemptState) => state.phase === 'complete' || state.phase === 'escalated';
export function createAttempt(scenarioId: ScenarioId = 'standard', mode: Mode = 'guided'): AttemptState {
  if (!scenarios.some(s => s.id === scenarioId) || !['guided', 'assessment'].includes(mode)) throw new Error('Invalid scenario or mode');
  return { workshop: createWorkshop(), id: `demo-v2-${scenarioId}-${mode}`, scenarioId, mode, revision: 0, phase: 'inspect', selectedComponent: null, inspected: [], observationRecorded: false, aligned: false, seated: false, verified: false, questionAnswers: {}, log: [], scores: { procedure: 0, judgment: 0, knowledge: 0 }, outcome: null, criticalError: false };
}
export function availableActions(state: AttemptState): ActionDefinition[] {
  if (isTerminal(state)) return [];
  const result: ActionDefinition[] = components.filter(id => !state.inspected.includes(id)).map(id => ({ id: `inspect-${id}` as const, label: `Inspect ${componentInfo[id].name.toLowerCase()}`, description: componentInfo[id].description, kind: 'inspection' as const, enabled: true }));
  if (!state.observationRecorded) result.push({ id: 'record-observation', label: 'Request observation', description: 'Reveal the authored inspection note.', kind: 'inspection', enabled: state.inspected.length === components.length });
  const decisionReady = isWorkshopReady(state.workshop) && questions.every(question => Object.hasOwn(state.questionAnswers, question.id));
  result.push({ id: 'continue', label: 'Release assembly', description: 'Finish every checkpoint and answer all questions before deciding.', kind: 'decision', enabled: decisionReady }, { id: 'escalate', label: 'Escalate for review', description: 'Complete the evidence workflow, then request review.', kind: 'decision', enabled: decisionReady });
  return result;
}
/** Invalid, unavailable and repeated actions throw without changing the input. */
export function transition(state: AttemptState, actionId: string): AttemptState {
  if (isTerminal(state)) throw new Error('Attempt is complete. Start a new attempt to try again.');
  const next: AttemptState = { ...state, inspected: [...state.inspected], questionAnswers: { ...state.questionAnswers }, scores: { ...state.scores }, log: [...state.log], revision: state.revision + 1 };
  let title = ''; let detail = '';
  if (actionId.startsWith('workshop:')) {
    if (!state.observationRecorded) throw new Error('Inspect all four components and request the observation before assembling.');
    next.workshop = workshopTransition(state.workshop, actionId.slice(9));
    next.aligned = next.workshop.placed.shaft;
    next.seated = next.workshop.seatDepth === 3;
    next.verified = next.workshop.completed;
    next.phase = next.verified ? 'decision' : next.seated ? 'verify' : next.aligned ? 'seat' : 'align';
    next.scores.procedure = 25 + Math.round(next.workshop.xp / 400 * 75);
    title = 'Workshop action recorded';
    detail = actionId.slice(9).replaceAll(':', ' · ').replaceAll('-', ' ');
  } else if (actionId.startsWith('answer:')) {
    const [, questionId, optionId, extra] = actionId.split(':');
    const question = questions.find(q => q.id === questionId);
    if (extra !== undefined || !question || !question.options.some(o => o.id === optionId)) throw new Error('Unknown question or answer');
    if (Object.hasOwn(state.questionAnswers, questionId)) throw new Error('Question has already been answered');
    next.questionAnswers[questionId] = optionId;
    next.scores.knowledge = Math.round(100 * questions.filter(q => next.questionAnswers[q.id] === q.correctOptionId).length / questions.length);
    title = 'Knowledge check recorded'; detail = question.feedback;
  } else {
    const action = availableActions(state).find(a => a.id === actionId);
    if (!action) throw new Error('Unknown or unavailable action');
    if (!action.enabled) throw new Error('Complete the prerequisite checks first');
    title = action.label;
    if (actionId.startsWith('inspect-')) {
      const id = actionId.slice(8) as ComponentId;
      next.inspected.push(id); next.selectedComponent = id; next.scores.procedure += 5; detail = componentInfo[id].inspection;
    } else if (actionId === 'record-observation') {
      next.observationRecorded = true; next.phase = 'align'; next.scores.procedure += 5; detail = scenarios.find(s => s.id === state.scenarioId)!.observation;
    } else if (actionId === 'continue') {
      next.phase = 'complete';
      if (!state.verified) { next.criticalError = true; detail = 'Released too early. Required inspection and verification evidence was missing.'; }
      else if (state.scenarioId === 'uncertain') { next.criticalError = true; detail = 'Unsupported release. The fit evidence remained unresolved; escalation was required.'; }
      else { next.scores.judgment = 100; detail = 'Supported release. All authored checks were completed and the scripted result was clear.'; }
      next.outcome = detail;
    } else if (actionId === 'escalate') {
      next.phase = 'escalated';
      if (!state.verified) { next.scores.judgment = 40; detail = 'Conservative stop. You escalated before completing the available simulated checks; gather the permitted evidence next time.'; }
      else if (state.scenarioId === 'uncertain') { next.scores.judgment = 100; detail = 'Supported escalation. You identified unresolved fit evidence and stopped release for review.'; }
      else { next.scores.judgment = 60; detail = 'Conservative escalation. The authored checks supported release; no unresolved observation remained.'; }
      next.outcome = detail;
    }
  }
  next.log.push({ id: `${state.id}-event-${next.revision}`, revision: next.revision, actionId, title, detail });
  return next;
}
