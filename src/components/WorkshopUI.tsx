import { ArrowLeft, ArrowRight, Check, ChevronDown, Hand, RotateCw, Wrench } from 'lucide-react';
import type { ComponentId } from '../simulation';
import type { WorkshopState } from '../workshop';
import { getWorkshopObjective } from '../workshop';
import type { getMissionProgress } from '../mission';
import { PartArtwork, ToolArtwork } from './PartArtworks';

export const workshopParts: { id: ComponentId; name: string; hint: string }[] = [
  { id: 'base', name: 'Base plate', hint: 'Workbench datum' },
  { id: 'housing', name: 'Bearing housing', hint: 'Mount on base' },
  { id: 'shaft', name: 'Drive shaft', hint: 'Align before inserting' },
  { id: 'bearing', name: 'Ball bearing', hint: 'Position with sleeve' },
];

const tools = [
  { id: 'alignment-jig', name: 'Alignment jig', hint: 'Center the shaft' },
  { id: 'bearing-sleeve', name: 'Bearing sleeve', hint: 'Position and press' },
  { id: 'hex-key', name: 'Hex key', hint: 'Secure four bolts' },
  { id: 'handwheel', name: 'Handwheel', hint: 'Test rotation' },
] as const;

type Props = {
  state: WorkshopState;
  enabled: boolean;
  onAction: (action: string) => void;
  selectedPart?: ComponentId;
  onSelectPart?: (part: ComponentId) => void;
};
type Progress = ReturnType<typeof getMissionProgress>;

export function WorkshopTray({ state, enabled, onAction, selectedPart, onSelectPart }: Props) {
  return (
    <section className="workshop-tray" aria-label="Component tray and tools">
      <div className="card-header">
        <div className="header-title">
          <span className="tray-header-cube" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
              <line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
          </span>
          <h2>Component tray</h2>
        </div>
      </div>

      <div className="tray-columns-wrapper" role="region" aria-label="Parts and tool selection" tabIndex={0}>
        {/* Left Side: Components */}
        <div className="tray-components-section">
          <div className="tray-subheading">Components</div>
          <div className="tray-parts-grid">
            {workshopParts.map(part => {
              const isHeld = state.heldPart === part.id;
              const isInstalled = state.placed[part.id];
              const isSelected = isHeld || selectedPart === part.id;
              let statusLabel = part.hint;
              if (isInstalled) statusLabel = 'Installed ✓';
              else if (isHeld || isSelected) statusLabel = 'Selected';

              return (
                <button
                  key={part.id}
                  aria-label={`Pick up ${part.name}`}
                  aria-pressed={isHeld}
                  draggable={enabled && !isInstalled}
                  disabled={!enabled || isInstalled || state.completed}
                  className={`tray-part-btn ${isHeld ? 'held' : ''} ${isSelected ? 'selected' : ''} ${isInstalled ? 'installed' : ''}`}
                  onClick={() => {
                    onSelectPart?.(part.id);
                    onAction(`pick:${part.id}`);
                  }}
                  onDragStart={event => {
                    event.dataTransfer.setData('application/takumi-part', part.id);
                    event.dataTransfer.effectAllowed = 'move';
                  }}
                >
                  <div className="tray-part-art">
                    <PartArtwork id={part.id} />
                  </div>
                  <strong className="tray-part-name">{part.name}</strong>
                  <small className="tray-part-status">{statusLabel}</small>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Side: Tool rack */}
        <div className="tray-tools-section">
          <div className="tray-subheading">
            <Wrench size={13} />
            <span>Tool rack</span>
          </div>
          <div className="tray-tools-grid">
            {tools.map(tool => {
              const isEquipped = state.tool === tool.id;
              return (
                <button
                  key={tool.id}
                  aria-label={`Use ${tool.name}`}
                  aria-pressed={isEquipped}
                  disabled={!enabled || state.completed}
                  className={`tray-tool-btn ${isEquipped ? 'equipped' : ''}`}
                  title={`${tool.name} · ${tool.hint}`}
                  onClick={() => {
                    if (state.tool !== tool.id) onAction(`tool:${tool.id}`);
                  }}
                >
                  <div className="tray-tool-art">
                    <ToolArtwork id={tool.id} />
                  </div>
                  <strong className="tray-tool-name" title={tool.name}>{tool.name}</strong>
                  {isEquipped && <Check size={12} className="tool-equipped-check" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

export function WorkshopTask({ state, enabled, onAction }: Props) {
  const objective = getWorkshopObjective(state);
  const labels: Record<string, string> = {
    'place:base': 'Mount base',
    'place:housing': 'Mount housing',
    'place:shaft': 'Insert shaft',
    'place:bearing': 'Place bearing',
    press: 'Press bearing',
    turn: 'Turn shaft',
    verify: 'Verify assembly',
  };
  const adjusting = state.placed.housing && !state.placed.shaft;
  const bolting = state.seatDepth === 3 && state.bolts.length < 4;

  return (
    <section className="workshop-task" aria-label="Current assembly task">
      <div className="task-kicker">
        <Wrench size={14} />
        <span>ASSEMBLY TASK</span>
        <span className="task-xp-badge">{state.xp} / 400 build XP</span>
      </div>
      <div className="workshop-task-scroll" role="region" aria-label="Assembly instructions" tabIndex={0}>
        <h3>{objective.title}</h3>
        <p className="task-desc">{objective.instruction}</p>

        {state.heldPart && (
          <div className="held-indicator">
            <Hand size={14} />
            <span>Holding: {workshopParts.find(part => part.id === state.heldPart)!.name}</span>
          </div>
        )}

        {adjusting && (
          <div className="alignment-control">
            <div className="alignment-caption">
              <span>Jig alignment</span>
              <strong>{state.alignment === 0 ? 'Centered · 0' : `Detent ${state.alignment > 0 ? '+' : ''}${state.alignment}`}</strong>
            </div>
            <div className="alignment-track">
              {[-2, -1, 0, 1, 2].map(detent => (
                <span key={detent} className={`${detent === 0 ? 'center' : ''} ${detent === state.alignment ? 'indicator' : ''}`}>
                  <i />
                  {detent}
                </span>
              ))}
            </div>
            <div className="nudge-buttons">
              <button
                className="button secondary"
                aria-label="Nudge left"
                disabled={!enabled || state.alignment === -2}
                onClick={() => onAction('adjust:left')}
              >
                <ArrowLeft size={13} /> Nudge left
              </button>
              <button
                className="button secondary"
                aria-label="Nudge right"
                disabled={!enabled || state.alignment === 2}
                onClick={() => onAction('adjust:right')}
              >
                Nudge right <ArrowRight size={13} />
              </button>
            </div>
          </div>
        )}

        {state.placed.bearing && state.seatDepth < 3 && (
          <div className="increment-meter">
            <span>Seating increments</span>
            <div className="increments-track">
              {[1, 2, 3].map(i => (
                <i key={i} className={state.seatDepth >= i ? 'filled' : ''} />
              ))}
            </div>
            <strong>{state.seatDepth} / 3</strong>
          </div>
        )}

        {bolting && (
          <div className="bolt-controls">
            <span className="tiny-label">DEMO CROSS SEQUENCE · A → C → B → D</span>
            <div className="bolt-buttons-row">
              {['A', 'B', 'C', 'D'].map(bolt => (
                <button
                  key={bolt}
                  aria-label={`Bolt ${bolt}`}
                  disabled={state.bolts.includes(bolt)}
                  className={`bolt-btn ${state.bolts.includes(bolt) ? 'secured' : ''}`}
                  onClick={() => onAction(`tighten:${bolt}`)}
                >
                  {state.bolts.includes(bolt) ? <Check size={13} /> : bolt}
                </button>
              ))}
            </div>
          </div>
        )}

        {state.bolts.length === 4 && state.turns < 3 && (
          <div className="rotation-meter">
            <RotateCw size={20} />
            <span>Rotation checks</span>
            <strong>{state.turns} / 3</strong>
          </div>
        )}
      </div>

      {objective.action && !objective.action.startsWith('adjust:') && (
        <button
          className="button primary full task-action-btn"
          disabled={!enabled}
          onClick={() => onAction(objective.action!)}
        >
          <Wrench size={15} />
          <span>{labels[objective.action] ?? objective.action.replace('tighten:', 'Tighten bolt ')}</span>
          <ArrowRight size={14} />
        </button>
      )}
      <small className="task-hint-sub">Use these controls or the highlighted targets on the workbench.</small>
    </section>
  );
}

export function MissionChecklist({ progress }: { progress: Progress }) {
  const active = progress.checkpoints.find(checkpoint => !checkpoint.complete)?.id;
  const fraction = progress.total > 0 ? progress.completed / progress.total : 0;

  return (
    <details className="checkpoint-card" aria-label="Mission checkpoints">
      <summary className="checkpoint-heading">
        <div className="checkpoint-heading-left">
          <span className="tiny-label">EXERCISE PROGRESS</span>
          <h3>Mission checkpoints</h3>
        </div>
        <div className="checkpoint-heading-right">
          <span className="checkpoint-badge">{progress.completed} / {progress.total} checkpoints</span>
          <ChevronDown size={16} className="checkpoint-chevron" />
        </div>
      </summary>

      {/* Segmented Progress Track */}
      <div
        className="checkpoint-progress-segmented"
        role="progressbar"
        aria-label="Mission progress"
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={progress.completed}
      >
        <span style={{ display: 'none', width: `${fraction * 100}%` }} />
        {progress.checkpoints.map((cp, idx) => (
          <div
            key={cp.id}
            className={`checkpoint-segment ${idx < progress.completed ? 'completed' : ''}`}
            title={`Checkpoint ${idx + 1}: ${cp.title}`}
          />
        ))}
      </div>

      <div className="checkpoint-list-scroll" role="region" aria-label="Checkpoint details" tabIndex={0}>
        <ol>
          {progress.checkpoints.map((checkpoint, index) => (
            <li
              key={checkpoint.id}
              className={`${checkpoint.complete ? 'checked' : ''} ${checkpoint.id === active ? 'current-checkpoint' : ''}`}
            >
              <span className="checkpoint-number">
                {checkpoint.complete ? <Check size={12} /> : String(index + 1).padStart(2, '0')}
              </span>
              <div className="checkpoint-info">
                <strong>{checkpoint.title}</strong>
                <p>{checkpoint.description}</p>
              </div>
              <span className="checkpoint-xp">{checkpoint.complete ? '+' : ''}{checkpoint.xp} XP</span>
            </li>
          ))}
        </ol>
      </div>
    </details>
  );
}

export function MissionBanner({ progress }: { progress: Progress }) {
  const percent = progress.total > 0 ? progress.completed / progress.total : 0;
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - percent * circumference;

  return (
    <div className={`mission-banner ${progress.complete ? 'mission-won' : ''}`}>
      {/* Circular Donut Ring Gauge */}
      <div className="gauge-wrapper" aria-hidden="true">
        <svg viewBox="0 0 42 42" width="36" height="36" className="progress-ring-svg">
          <circle
            cx="21"
            cy="21"
            r={radius}
            fill="transparent"
            stroke="#e2e8e4"
            strokeWidth="3.5"
          />
          <circle
            cx="21"
            cy="21"
            r={radius}
            fill="transparent"
            stroke={progress.complete ? '#16a34a' : '#20573e'}
            strokeWidth="3.5"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 21 21)"
          />
        </svg>
      </div>

      <div className="mission-copy">
        <span className="tiny-label">
          {progress.complete ? 'EXERCISE COMPLETE' : 'ASSEMBLY EXERCISE'}
        </span>
        <strong className="mission-title">
          {progress.complete ? 'All checkpoints completed' : 'Bearing assembly progress'}
        </strong>
      </div>

      <div className="mission-xp">
        <strong>{progress.xp}<small> / {progress.maxXP}</small></strong>
        <span>TOTAL XP</span>
      </div>
    </div>
  );
}
