import { ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, Crosshair, Hand, LockKeyhole, RotateCw, Trophy, Wrench } from 'lucide-react';
import type { ComponentId } from '../simulation';
import type { WorkshopState } from '../workshop';
import { getWorkshopObjective } from '../workshop';
import type { getMissionProgress } from '../mission';

export const workshopParts: { id: ComponentId; name: string; hint: string }[] = [
  { id: 'base', name: 'Base plate', hint: 'Workbench datum' },
  { id: 'housing', name: 'Bearing housing', hint: 'Mount on the base' },
  { id: 'shaft', name: 'Drive shaft', hint: 'Align before inserting' },
  { id: 'bearing', name: 'Ball bearing', hint: 'Position with sleeve' },
];
const tools = [
  { id: 'alignment-jig', name: 'Alignment jig', hint: 'Center the shaft' },
  { id: 'bearing-sleeve', name: 'Bearing sleeve', hint: 'Position and press' },
  { id: 'hex-key', name: 'Hex key', hint: 'Secure four bolts' },
  { id: 'handwheel', name: 'Handwheel', hint: 'Test rotation' },
] as const;
type Props = { state: WorkshopState; enabled: boolean; onAction: (action: string) => void };
type Progress = ReturnType<typeof getMissionProgress>;

export function WorkshopTray({ state, enabled, onAction }: Props) {
  return <section className="workshop-tray" aria-label="Component tray and tools">
    <div className="section-caption"><h2>Component tray</h2><span><Hand size={12}/> Pick up, then place on the highlighted target</span></div>
    <div className="tray-parts">{workshopParts.map(part => <button key={part.id} aria-label={`Pick up ${part.name}`} aria-pressed={state.heldPart === part.id} draggable={enabled && !state.placed[part.id]} disabled={!enabled || state.placed[part.id] || state.completed} className={`tray-part ${state.heldPart === part.id ? 'held' : ''} ${state.placed[part.id] ? 'installed' : ''}`} onClick={() => onAction(`pick:${part.id}`)} onDragStart={event => { event.dataTransfer.setData('application/takumi-part', part.id); event.dataTransfer.effectAllowed = 'move'; }}><span className={`part-glyph ${part.id}`}><span/></span><strong>{part.name}</strong><small>{state.placed[part.id] ? 'Installed ✓' : state.heldPart === part.id ? 'In your hand' : part.hint}</small></button>)}</div>
    <div className="tool-rack"><div className="tool-rack-heading"><Wrench size={14}/><strong>Tool rack</strong><span>{state.tool ? tools.find(tool => tool.id === state.tool)!.name + ' equipped' : 'Choose a tool for the task'}</span></div><div className="tool-options">{tools.map((tool, index) => <button key={tool.id} aria-label={`Use ${tool.name}`} aria-pressed={state.tool === tool.id} disabled={!enabled || state.completed} className={state.tool === tool.id ? 'equipped' : ''} onClick={() => { if (state.tool !== tool.id) onAction(`tool:${tool.id}`); }}><span className="tool-drawing">{index === 0 ? <Crosshair size={20}/> : index === 1 ? <span className="sleeve-icon"/> : index === 2 ? <span className="hex-key-icon"/> : <RotateCw size={22}/>}</span><strong>{tool.name}</strong><small>{tool.hint}</small>{state.tool === tool.id && <Check size={12}/>}</button>)}</div></div>
    {!enabled && !state.completed && <div className="tray-locked"><LockKeyhole size={13}/> Inspect all four components and request the observation to unlock the workbench.</div>}
  </section>;
}

export function WorkshopTask({ state, enabled, onAction }: Props) {
  const objective = getWorkshopObjective(state);
  const labels: Record<string, string> = { 'place:base': 'Mount base', 'place:housing': 'Mount housing', 'place:shaft': 'Insert shaft', 'place:bearing': 'Place bearing', press: 'Press bearing', turn: 'Turn shaft', verify: 'Verify assembly' };
  const adjusting = state.placed.housing && !state.placed.shaft;
  const bolting = state.seatDepth === 3 && state.bolts.length < 4;
  return <section className="workshop-task" aria-label="Current assembly task"><div className="task-kicker"><Wrench size={13}/><span>HANDS-ON CHALLENGE</span><span>{state.xp} / 400 build XP</span></div><h3>{objective.title}</h3><p>{objective.instruction}</p>
    {state.heldPart && <div className="held-indicator"><Hand size={14}/> Holding: {workshopParts.find(part => part.id === state.heldPart)!.name}</div>}
    {adjusting && <div className="alignment-control"><div className="alignment-caption"><span>Jig alignment</span><strong>{state.alignment === 0 ? 'Centered · 0' : `Detent ${state.alignment > 0 ? '+' : ''}${state.alignment}`}</strong></div><div className="alignment-track">{[-2, -1, 0, 1, 2].map(detent => <span key={detent} className={`${detent === 0 ? 'center' : ''} ${detent === state.alignment ? 'indicator' : ''}`}><i/>{detent}</span>)}</div><div className="nudge-buttons"><button className="button secondary" aria-label="Nudge left" disabled={!enabled || state.alignment === -2} onClick={() => onAction('adjust:left')}><ArrowLeft size={13}/> Nudge left</button><button className="button secondary" aria-label="Nudge right" disabled={!enabled || state.alignment === 2} onClick={() => onAction('adjust:right')}>Nudge right <ArrowRight size={13}/></button></div></div>}
    {state.placed.bearing && state.seatDepth < 3 && <div className="increment-meter"><span>Seating increments</span><div>{[1, 2, 3].map(i => <i key={i} className={state.seatDepth >= i ? 'filled' : ''}/>)}</div><strong>{state.seatDepth} / 3</strong></div>}
    {bolting && <div className="bolt-controls"><span className="tiny-label">DEMO CROSS SEQUENCE · A → C → B → D</span><div>{['A', 'B', 'C', 'D'].map(bolt => <button key={bolt} aria-label={`Bolt ${bolt}`} disabled={state.bolts.includes(bolt)} className={state.bolts.includes(bolt) ? 'secured' : ''} onClick={() => onAction(`tighten:${bolt}`)}>{state.bolts.includes(bolt) ? <Check size={13}/> : bolt}</button>)}</div></div>}
    {state.bolts.length === 4 && state.turns < 3 && <div className="rotation-meter"><RotateCw size={22}/><span>Rotation checks</span><strong>{state.turns} / 3</strong></div>}
    {objective.action && !objective.action.startsWith('adjust:') && <button className="button primary full" disabled={!enabled} onClick={() => onAction(objective.action!)}><Wrench size={15}/>{labels[objective.action] ?? objective.action.replace('tighten:', 'Tighten bolt ')}<ArrowRight size={14}/></button>}
    <small>Click the highlighted scene target or use these controls. Drag a tray part onto the workbench to place it. Mouse, touch and keyboard use the same rules.</small>
  </section>;
}

export function MissionChecklist({ progress }: { progress: Progress }) {
  const active = progress.checkpoints.find(checkpoint => !checkpoint.complete)?.id;
  return <details className="checkpoint-card" aria-label="Mission checkpoints"><summary className="checkpoint-heading"><div><span className="tiny-label">YOUR ASSEMBLY MISSION</span><h3>Mission checkpoints</h3></div><span>{progress.completed} / {progress.total} checkpoints</span><ChevronDown size={16}/></summary><div className="checkpoint-progress" role="progressbar" aria-label="Mission progress" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.completed}><span style={{ width: `${progress.completed / progress.total * 100}%` }}/></div><ol>{progress.checkpoints.map((checkpoint, index) => <li key={checkpoint.id} className={`${checkpoint.complete ? 'checked' : ''} ${checkpoint.id === active ? 'current-checkpoint' : ''}`}><span className="checkpoint-number">{checkpoint.complete ? <Check size={12}/> : String(index + 1).padStart(2, '0')}</span><div><strong>{checkpoint.title}</strong><p>{checkpoint.description}</p></div><span className="checkpoint-xp">{checkpoint.complete ? '+' : ''}{checkpoint.xp} XP</span></li>)}</ol></details>;
}

export function MissionBanner({ progress }: { progress: Progress }) {
  return <div className={`mission-banner ${progress.complete ? 'mission-won' : ''}`}><div className="mission-medallion">{progress.complete ? <Trophy size={24}/> : <CheckCircle2 size={22}/>}</div><div><span className="tiny-label">{progress.complete ? 'MISSION COMPLETE' : 'BUILD IT. CHECK IT. EARN IT.'}</span><strong>{progress.complete ? 'Assembly mission accomplished' : 'From parts to a working assembly'}</strong><p>{progress.complete ? 'Every checkpoint completed. Your decisions and learning scores are recorded.' : 'Place four parts, use four tools, and prove your decision through 12 checkpoints.'}</p></div><div className="mission-xp"><strong>{progress.xp}<small> / {progress.maxXP}</small></strong><span>XP EARNED</span></div></div>;
}
