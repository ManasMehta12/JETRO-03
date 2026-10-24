import type { ComponentId } from './simulation';

export type ToolId = 'alignment-jig' | 'bearing-sleeve' | 'hex-key' | 'handwheel';
export interface WorkshopState {
  placed: Record<ComponentId, boolean>;
  heldPart: ComponentId | null;
  tool: ToolId | null;
  alignment: number;
  seatDepth: number;
  bolts: string[];
  turns: number;
  completed: boolean;
  mistakes: number;
  log: string[];
  xp: number;
}
export interface WorkshopCheckpoint { id: string; title: string; description: string; complete: boolean; xp: number }
export interface WorkshopObjective {
  title: string;
  instruction: string;
  target: ComponentId | 'press' | 'bolt' | 'handwheel' | 'verify';
  action: string | null;
}
const parts: ComponentId[] = ['base', 'housing', 'shaft', 'bearing'];
const tools: ToolId[] = ['alignment-jig', 'bearing-sleeve', 'hex-key', 'handwheel'];
const boltOrder = ['A', 'C', 'B', 'D'];

export function createWorkshop(): WorkshopState {
  return { placed: { base: false, housing: false, shaft: false, bearing: false }, heldPart: null, tool: null, alignment: 2, seatDepth: 0, bolts: [], turns: 0, completed: false, mistakes: 0, log: [], xp: 0 };
}

export function getWorkshopCheckpoints(state: WorkshopState): WorkshopCheckpoint[] {
  return [
    { id: 'base', title: 'Anchor the base', description: 'Place the fixture base on the workbench.', complete: state.placed.base, xp: 50 },
    { id: 'housing', title: 'Locate the housing', description: 'Place the bearing housing on the base.', complete: state.placed.housing, xp: 50 },
    { id: 'shaft', title: 'Align and insert shaft', description: 'Use the jig to reach the center detent, then insert the shaft.', complete: state.placed.shaft && state.alignment === 0, xp: 50 },
    { id: 'bearing', title: 'Position the bearing', description: 'Use the bearing sleeve to position the bearing on the shaft.', complete: state.placed.bearing, xp: 50 },
    { id: 'seating', title: 'Seat the bearing', description: 'Complete three authored press increments with the sleeve.', complete: state.seatDepth === 3, xp: 50 },
    { id: 'bolts', title: 'Secure the housing', description: 'Use the hex key in the fixed A, C, B, D cross sequence.', complete: state.bolts.length === 4, xp: 50 },
    { id: 'rotation', title: 'Check rotation', description: 'Use the handwheel for three scripted rotation checks.', complete: state.turns === 3, xp: 50 },
    { id: 'verification', title: 'Verify the assembly', description: 'Confirm all workshop checkpoints are complete.', complete: state.completed, xp: 50 },
  ];
}

const physicalStepsDone = (state: WorkshopState) => parts.every(part => state.placed[part]) && state.alignment === 0 && state.seatDepth === 3 && state.bolts.length === 4 && boltOrder.every((bolt, index) => state.bolts[index] === bolt) && state.turns === 3;
export const isWorkshopReady = (state: WorkshopState) => state.completed && physicalStepsDone(state);

/** An authored puzzle, not a real mechanical procedure or force/tolerance model. */
export function workshopTransition(state: WorkshopState, action: string): WorkshopState {
  if (state.completed) throw new Error('Workshop complete. Restart to build again.');
  const next: WorkshopState = { ...state, placed: { ...state.placed }, bolts: [...state.bolts], log: [...state.log] };
  const fail = (message: string): never => { throw new Error(message); };
  const requireTool = (tool: ToolId) => { if (state.tool !== tool) fail(`Select the ${tool.replaceAll('-', ' ')} first.`); };
  if (action.startsWith('pick:')) {
    const part = action.slice(5) as ComponentId;
    if (!parts.includes(part)) fail('Unknown component.');
    if (state.placed[part]) fail('That component is already installed.');
    if (state.heldPart === part) fail('You are already holding that component.');
    next.heldPart = part;
  } else if (action.startsWith('tool:')) {
    const tool = action.slice(5) as ToolId;
    if (!tools.includes(tool)) fail('Unknown tool.');
    if (state.tool === tool) fail('That tool is already selected.');
    next.tool = tool;
  } else if (action.startsWith('place:')) {
    const part = action.slice(6) as ComponentId;
    if (!parts.includes(part)) fail('Unknown component.');
    if (state.placed[part]) fail('That component is already installed.');
    if (state.heldPart !== part) fail(`Pick up the ${part} first.`);
    const index = parts.indexOf(part);
    if (parts.slice(0, index).some(previous => !state.placed[previous])) fail('Install the preceding components first.');
    if (part === 'shaft') { requireTool('alignment-jig'); if (state.alignment !== 0) fail('Center the alignment indicator before inserting the shaft.'); }
    if (part === 'bearing') requireTool('bearing-sleeve');
    next.placed[part] = true;
    next.heldPart = null;
  } else if (action === 'adjust:left' || action === 'adjust:right') {
    requireTool('alignment-jig');
    if (!state.placed.housing) fail('Place the housing before adjusting alignment.');
    if (state.placed.shaft) fail('Alignment is locked after shaft insertion.');
    const alignment = state.alignment + (action === 'adjust:left' ? -1 : 1);
    if (alignment < -2 || alignment > 2) fail('The alignment jig is at its detent limit.');
    next.alignment = alignment;
  } else if (action === 'press') {
    requireTool('bearing-sleeve');
    if (!state.placed.bearing) fail('Position the bearing before pressing.');
    if (state.seatDepth >= 3) fail('The authored seating position is already reached.');
    next.seatDepth += 1;
  } else if (action.startsWith('tighten:')) {
    requireTool('hex-key');
    if (state.seatDepth !== 3) fail('Complete bearing seating before securing the housing.');
    const bolt = action.slice(8);
    if (state.bolts.length === 4) fail('All four bolts are already secured.');
    if (bolt !== boltOrder[state.bolts.length]) fail(`Follow the cross sequence: tighten bolt ${boltOrder[state.bolts.length]} next.`);
    next.bolts.push(bolt);
  } else if (action === 'turn') {
    requireTool('handwheel');
    if (state.bolts.length !== 4) fail('Secure all four housing bolts before the rotation check.');
    if (state.turns >= 3) fail('All three scripted rotation checks are complete.');
    next.turns += 1;
  } else if (action === 'verify') {
    if (!physicalStepsDone(state)) fail('Complete every assembly checkpoint before verification.');
    next.completed = true;
  } else fail('Unknown workshop action.');

  const before = getWorkshopCheckpoints(state);
  next.xp += getWorkshopCheckpoints(next).reduce((earned, checkpoint, index) => earned + (checkpoint.complete && !before[index].complete ? checkpoint.xp : 0), 0);
  next.log.push(action);
  return next;
}

export function getWorkshopObjective(state: WorkshopState): WorkshopObjective {
  if (state.completed) return { title: 'Assembly verified', instruction: 'All eight authored checkpoints are complete. Continue to the evidence and release decision.', target: 'verify', action: null };
  if (!state.placed.base) return { title: 'Anchor the base', instruction: state.heldPart === 'base' ? 'Place the base on the highlighted workbench target.' : 'Pick up the base from the component tray, then place it on the workbench.', target: 'base', action: 'place:base' };
  if (!state.placed.housing) return { title: 'Locate the housing', instruction: state.heldPart === 'housing' ? 'Place the housing on the base.' : 'Pick up the housing, then place it on the base.', target: 'housing', action: 'place:housing' };
  if (state.alignment !== 0) return { title: 'Center the alignment jig', instruction: 'Select the alignment jig and move the indicator to the center detent (0).', target: 'shaft', action: state.alignment > 0 ? 'adjust:left' : 'adjust:right' };
  if (!state.placed.shaft) return { title: 'Insert the shaft', instruction: 'Keep the alignment jig selected. Pick up the shaft and insert it through the housing.', target: 'shaft', action: 'place:shaft' };
  if (!state.placed.bearing) return { title: 'Position the bearing', instruction: 'Select the bearing sleeve. Pick up the bearing and position it on the shaft.', target: 'bearing', action: 'place:bearing' };
  if (state.seatDepth < 3) return { title: 'Seat the bearing', instruction: `Use the bearing sleeve to apply the next authored press increment (${state.seatDepth}/3 complete).`, target: 'press', action: 'press' };
  if (state.bolts.length < 4) return { title: `Secure bolt ${boltOrder[state.bolts.length]}`, instruction: 'Select the hex key. Follow the cross sequence A → C → B → D.', target: 'bolt', action: `tighten:${boltOrder[state.bolts.length]}` };
  if (state.turns < 3) return { title: 'Check rotation', instruction: `Select the handwheel and complete three scripted checks (${state.turns}/3 complete).`, target: 'handwheel', action: 'turn' };
  return { title: 'Verify your assembly', instruction: 'All assembly steps are complete. Confirm the eight workshop checkpoints.', target: 'verify', action: 'verify' };
}
