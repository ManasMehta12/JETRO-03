import { lazy, Suspense, useEffect, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Box,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  Eye,
  Hand,
  Layers3,
  Lightbulb,
  ListChecks,
  Maximize2,
  RotateCcw,
  Search,
  ShieldCheck,
  Target,
  Wrench,
  X,
} from 'lucide-react';
import {
  availableActions,
  componentInfo,
  createAttempt,
  insights,
  isTerminal,
  questions,
  scenarios,
  transition,
} from './simulation';
import type { ComponentId, Mode, ScenarioId } from './simulation';
import { MissionBanner, MissionChecklist, WorkshopTask, WorkshopTray } from './components/WorkshopUI';
import { PartArtwork } from './components/PartArtworks';
import { getMissionProgress } from './mission';
import { restoreAttempt, serializeAttempt, STORAGE_KEY } from './persistence';

const AssemblyScene = lazy(() => import('./components/AssemblyScene'));

const parts: { id: ComponentId; name: string; subtitle: string; code: string }[] = [
  { id: 'base', name: 'Base plate', subtitle: 'Reference & support', code: '01' },
  { id: 'housing', name: 'Bearing housing', subtitle: 'Outer ring support', code: '02' },
  { id: 'shaft', name: 'Drive shaft', subtitle: 'Rotating element', code: '03' },
  { id: 'bearing', name: 'Ball bearing', subtitle: 'Rolling element assembly', code: '04' },
];

function readInitial() {
  try {
    return restoreAttempt(localStorage.getItem(STORAGE_KEY));
  } catch {
    return createAttempt();
  }
}

export default function App() {
  const [attempt, setAttempt] = useState(readInitial);
  const [selected, setSelected] = useState<ComponentId>('bearing');
  const [tab, setTab] = useState('Practice');
  const [exploded, setExploded] = useState(true);
  const [resetKey, setResetKey] = useState(0);
  const [reset, setReset] = useState<{ scenario: ScenarioId; mode: Mode } | null>(null);
  const [error, setError] = useState('');
  const [storageWarning, setStorageWarning] = useState(false);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [reward, setReward] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [wide, setWide] = useState(false);

  const terminal = isTerminal(attempt);
  const showFeedback = attempt.mode === 'guided' || terminal;
  const scenario = scenarios.find(s => s.id === attempt.scenarioId)!;
  const actions = availableActions(attempt);
  const decisionReady = actions.find(a => a.id === 'continue')?.enabled ?? false;
  const progress = getMissionProgress(attempt);

  const sceneStage = terminal && attempt.verified
    ? 6
    : attempt.verified
    ? 5
    : attempt.seated
    ? 4
    : attempt.aligned
    ? 3
    : attempt.observationRecorded
    ? 2
    : attempt.inspected.length
    ? 1
    : 0;

  const inspected = attempt.inspected.includes(selected);
  const lastEvent = attempt.log.at(-1);

  useEffect(() => {
    if (!reward) return;
    const timer = window.setTimeout(() => setReward(''), 4000);
    return () => window.clearTimeout(timer);
  }, [reward, attempt.revision]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, serializeAttempt(attempt));
      setStorageWarning(false);
    } catch {
      setStorageWarning(true);
    }
  }, [attempt]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setEvidence(null);
        setReset(null);
        setWide(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (!reset && !evidence) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const controls = dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], select, [tabindex="0"]');
    controls?.[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !controls?.length) return;
      const first = controls[0],
        last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', trap);
    return () => {
      document.removeEventListener('keydown', trap);
      previous?.focus();
    };
  }, [reset, evidence]);

  function act(id: string) {
    try {
      const next = transition(attempt, id);
      const gained = getMissionProgress(next).xp - progress.xp;
      setAttempt(next);
      setError('');
      setReward(gained > 0 ? `Checkpoint complete · +${gained} XP` : '');
      if (id === 'workshop:verify') setExploded(false);
    } catch (err) {
      setReward('');
      setError(err instanceof Error ? err.message : 'Unable to apply action.');
    }
  }

  function workshopAct(action: string) {
    if (action.startsWith('pick:')) {
      const part = action.slice(5) as ComponentId;
      if (parts.some(item => item.id === part)) setSelected(part);
      if (attempt.workshop.heldPart === part) return;
    }
    act(`workshop:${action}`);
  }

  function dropPart(part: string) {
    if (!parts.some(item => item.id === part)) {
      setError('Choose a component from the tray.');
      return;
    }
    try {
      let next = attempt;
      if (next.workshop.heldPart !== part) next = transition(next, `workshop:pick:${part}`);
      next = transition(next, `workshop:place:${part}`);
      const gained = getMissionProgress(next).xp - progress.xp;
      setAttempt(next);
      setSelected(part as ComponentId);
      setError('');
      setReward(gained ? `Checkpoint complete · +${gained} XP` : '');
    } catch (err) {
      setReward('');
      setError(err instanceof Error ? err.message : 'That part cannot be placed here yet.');
    }
  }

  function startFresh() {
    if (!reset) return;
    setAttempt(createAttempt(reset.scenario, reset.mode));
    setSelected('bearing');
    setTab('Practice');
    setExploded(true);
    setResetKey(key => key + 1);
    setReset(null);
    setError('');
    setReward('');
  }

  return (
    <div className="app-shell">
      {/* Top Header */}
      <header className="app-header">
        <div className="header-left">
          <a className="brand" href="#playground" aria-label="Takumi home">
            <span className="brand-symbol">
              <Layers3 size={20} />
            </span>
            <span className="brand-text">
              takumi<span className="brand-period">.</span>
            </span>
          </a>
          <div className="header-divider" aria-hidden="true" />
          <nav className="module-nav" aria-label="Workspace">
            {[
              { name: 'Practice', label: 'Playground', icon: Box },
              { name: 'Knowledge check', label: 'Knowledge check', icon: ClipboardCheck },
              { name: 'Insights', label: 'Field notes', icon: BookOpen },
            ].map(({ name, label, icon: Icon }) => (
              <button
                key={name}
                className={`nav-tab ${tab === name ? 'current' : ''}`}
                aria-label={label}
                aria-current={tab === name ? 'page' : undefined}
                onClick={() => setTab(name)}
              >
                <Icon size={16} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </div>
        <div className="header-right">
          <div className="session-info">
            <strong>Apprentice workspace</strong>
            <span>Local practice session</span>
          </div>
          <div className="avatar" aria-label="Apprentice AK">
            AK
          </div>
          <ChevronDown size={14} className="avatar-chevron" />
        </div>
      </header>

      {/* Main Content Area */}
      <main id="playground" className="main-content">
        <div className="page-container">
          {/* Page Heading Row */}
          <div className="page-heading">
            <div className="heading-copy">
              <div className="eyebrow">MECHANICAL FOUNDATIONS <span>/</span> MODULE 01</div>
              <h1>Bearing assembly</h1>
            </div>
            <button
              className="button secondary restart"
              aria-label="Restart exercise"
              onClick={() => setReset({ scenario: attempt.scenarioId, mode: attempt.mode })}
            >
              <RotateCcw size={15} />
              <span>Restart exercise</span>
            </button>
          </div>

          {/* Top Controls Row: Selectors + Progress Banner */}
          <div className="workspace-widgets">
            <div className="scenario-bar">
              {/* Scenario Selector Card */}
              <div className="selector-card">
                <div className="selector-icon">
                  <BookOpen size={18} />
                </div>
                <div className="selector-copy">
                  <span className="selector-label">Your scenario</span>
                  <strong className="selector-title">{scenario.title}</strong>
                </div>
                <ChevronDown size={16} className="selector-chevron" />
                <select
                  aria-label="Scenario"
                  className="selector-select"
                  value={attempt.scenarioId}
                  onChange={e => setReset({ scenario: e.target.value as ScenarioId, mode: attempt.mode })}
                >
                  <option value="standard">01 · A clean assembly</option>
                  <option value="uncertain">02 · The uncertain fit</option>
                </select>
              </div>

              {/* Learning Mode Selector Card */}
              <div className="selector-card">
                <div className="selector-icon">
                  <Target size={18} />
                </div>
                <div className="selector-copy">
                  <span className="selector-label">Learning mode</span>
                  <strong className="selector-title">
                    {attempt.mode === 'guided' ? 'Guided practice' : 'Assessment'}
                  </strong>
                </div>
                <ChevronDown size={16} className="selector-chevron" />
                <select
                  aria-label="Learning mode"
                  className="selector-select"
                  value={attempt.mode}
                  onChange={e => setReset({ scenario: attempt.scenarioId, mode: e.target.value as Mode })}
                >
                  <option value="guided">Guided practice</option>
                  <option value="assessment">Assessment</option>
                </select>
              </div>
            </div>

            {/* Progress Card Banner */}
            <MissionBanner progress={progress} />
          </div>

          {/* Main 2-Column Workspace Grid */}
          <div className="workspace-grid">
            {/* Left Column: 3D Viewport + Bottom Dock */}
            <section className={`simulation-column ${attempt.observationRecorded ? 'building' : ''}`} aria-label="Assembly simulation">
              {/* 3D Scene Viewport Card */}
              <div className={`scene-card ${wide ? 'scene-wide' : ''}`}>
                <div className="scene-badge-top-left">
                  <span className="live-dot" />
                  <span>Interactive assembly</span>
                </div>
                <div className="scene-gizmo-top-right" aria-hidden="true">
                  <svg viewBox="0 0 60 60" width="60" height="60">
                    <line x1="30" y1="30" x2="30" y2="8" stroke="#2e7d32" strokeWidth="2.5" strokeLinecap="round" />
                    <text x="30" y="5" textAnchor="middle" fill="#2e7d32" fontSize="9" fontWeight="bold">Y</text>
                    <line x1="30" y1="30" x2="52" y2="30" stroke="#d32f2f" strokeWidth="2.5" strokeLinecap="round" />
                    <text x="56" y="33" textAnchor="start" fill="#d32f2f" fontSize="9" fontWeight="bold">X</text>
                    <line x1="30" y1="30" x2="14" y2="42" stroke="#1976d2" strokeWidth="2.5" strokeLinecap="round" />
                    <text x="9" y="47" textAnchor="middle" fill="#1976d2" fontSize="9" fontWeight="bold">Z</text>
                  </svg>
                </div>

                <div
                  className={`scene-viewport ${dragOver ? 'drag-over' : ''}`}
                  onDragOver={event => {
                    event.preventDefault();
                    if (attempt.observationRecorded && !attempt.workshop.completed) {
                      event.dataTransfer.dropEffect = 'move';
                      setDragOver(true);
                    }
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={event => {
                    event.preventDefault();
                    setDragOver(false);
                    dropPart(event.dataTransfer.getData('application/takumi-part'));
                  }}
                >
                  <Suspense
                    fallback={
                      <div className="scene-loading">
                        <Layers3 size={28} />
                        <span>Preparing your workbench…</span>
                      </div>
                    }
                  >
                    <AssemblyScene
                      selected={selected}
                      onSelect={setSelected}
                      stage={sceneStage}
                      exploded={exploded}
                      resetKey={resetKey}
                      workshop={attempt.workshop}
                      onWorkshopAction={workshopAct}
                    />
                  </Suspense>

                  {dragOver && <div className="drop-target-message">Drop to place on the assembly target</div>}

                  {/* Floating Toolbar docked inside bottom of 3D Scene */}
                  <div className="scene-toolbar-floating">
                    <button className="tool-pill active" aria-label="Orbit controls">
                      <Hand size={14} />
                      <span>Orbit</span>
                    </button>
                    <button className="tool-pill" aria-label="Zoom controls">
                      <Search size={14} />
                      <span>Zoom</span>
                    </button>
                    <button
                      aria-label="Exploded view"
                      aria-pressed={exploded}
                      className={`tool-pill ${exploded ? 'active' : ''}`}
                      onClick={() => setExploded(value => !value)}
                    >
                      <Box size={14} />
                      <span>Exploded view</span>
                    </button>
                    <button
                      aria-label="Reset camera"
                      className="tool-pill"
                      onClick={() => setResetKey(key => key + 1)}
                    >
                      <RotateCcw size={14} />
                      <span>Reset</span>
                    </button>
                    <button
                      aria-label={wide ? 'Close expanded view' : 'Expand viewport'}
                      className="tool-pill icon-only"
                      onClick={() => setWide(value => !value)}
                    >
                      {wide ? <X size={15} /> : <Maximize2 size={15} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Bottom Dock Row */}
              <div className="bottom-dock-row">
                {/* Left Card: Know your components */}
                <div className="components-card">
                  <div className="card-header">
                    <div className="header-title">
                      <BookOpen size={16} className="header-icon" />
                      <h2>Know your components</h2>
                    </div>
                    <div className="inspect-counter">
                      <span>{attempt.inspected.length} / 4 inspected</span>
                      <CheckCircle2
                        size={16}
                        className={attempt.inspected.length === 4 ? 'check-green' : 'check-muted'}
                      />
                    </div>
                  </div>
                  <div className="component-inspect-grid">
                    {parts.map(part => {
                      const isInspected = attempt.inspected.includes(part.id);
                      const isSelected = selected === part.id;
                      return (
                        <button
                          key={part.id}
                          className={`inspect-part-btn ${isSelected ? 'selected' : ''}`}
                          aria-label={`Select ${part.name}`}
                          aria-pressed={isSelected}
                          onClick={() => setSelected(part.id)}
                        >
                          {isInspected && (
                            <span className="inspected-badge" aria-hidden="true">
                              <Check size={11} />
                            </span>
                          )}
                          <div className="part-illustration">
                            <PartArtwork id={part.id} />
                          </div>
                          <span className="part-name-label">{part.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Right Card: Component Tray & Tool Rack */}
                <WorkshopTray
                  state={attempt.workshop}
                  enabled={attempt.observationRecorded && !terminal}
                  onAction={workshopAct}
                  selectedPart={selected}
                  onSelectPart={setSelected}
                />
              </div>
            </section>

            {/* Right Column: Learning Panel */}
            <section className="learning-card" aria-label="Learning panel">
              {/* Header Tabs */}
              <div className="tabs-header" role="tablist" aria-label="Learning views">
                {[
                  { name: 'Practice', icon: Wrench },
                  { name: 'Knowledge check', icon: CircleHelp },
                  { name: 'Insights', icon: Lightbulb },
                ].map(({ name, icon: Icon }) => (
                  <button
                    role="tab"
                    id={`tab-${name.replaceAll(' ', '-')}`}
                    aria-controls="learning-view"
                    aria-selected={tab === name}
                    tabIndex={tab === name ? 0 : -1}
                    key={name}
                    className={`tab-btn ${tab === name ? 'active' : ''}`}
                    onClick={() => setTab(name)}
                  >
                    <Icon size={15} />
                    <span>{name}</span>
                  </button>
                ))}
              </div>

              <div
                id="learning-view"
                role="tabpanel"
                tabIndex={0}
                aria-labelledby={`tab-${tab.replaceAll(' ', '-')}`}
                className="tab-body"
              >
                {tab === 'Practice' && (
                  <div className="practice-content">
                    {/* Soft Mint Instruction Banner */}
                    <div className="task-instruction-banner">
                      <ListChecks size={20} className="banner-icon" />
                      <p>
                        Assemble the bearing using the correct components in a logical order. Look for fit, alignment and clearance. Complete all checkpoints to unlock the next step.
                      </p>
                    </div>

                    {/* Pre-observation Inspection Action Area */}
                    {!terminal && !attempt.observationRecorded && (
                      <div className="inspection-action-panel">
                        <h2>01. Inspect the components</h2>
                        <div className="inspection-picker" aria-label="Inspection progress">
                          {parts.map(part => (
                            <button
                              key={part.id}
                              aria-label={`Focus ${part.name}`}
                              aria-pressed={selected === part.id}
                              className={`focus-btn ${selected === part.id ? 'active' : ''}`}
                              onClick={() => setSelected(part.id)}
                            >
                              {attempt.inspected.includes(part.id) ? (
                                <CheckCircle2 size={14} className="text-green" />
                              ) : (
                                <span>{part.code}</span>
                              )}
                              <span>{part.name}</span>
                            </button>
                          ))}
                        </div>

                        <div className="selected-detail-card">
                          <div className="detail-top">
                            <Box size={16} />
                            <strong>{parts.find(p => p.id === selected)!.name}</strong>
                            {inspected && <CheckCircle2 size={16} className="text-green" />}
                          </div>
                          <p>{componentInfo[selected].description}</p>
                          <button
                            className="button primary full"
                            disabled={inspected}
                            onClick={() => act(`inspect-${selected}`)}
                          >
                            <Eye size={15} />
                            <span>{inspected ? 'Inspection recorded' : 'Inspect component'}</span>
                            {!inspected && <ArrowRight size={14} />}
                          </button>
                        </div>
                        <div className="operation-actions">
                          <button
                            className="button secondary full"
                            disabled={attempt.observationRecorded || attempt.inspected.length < 4}
                            onClick={() => act('record-observation')}
                          >
                            <ClipboardCheck size={15} />
                            <span>{attempt.observationRecorded ? 'Observation recorded' : 'Request observation'}</span>
                            {attempt.observationRecorded && <Check size={14} />}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Active Workshop Task Controls */}
                    {attempt.observationRecorded && !terminal && !attempt.workshop.completed && (
                      <WorkshopTask state={attempt.workshop} enabled={true} onAction={workshopAct} />
                    )}

                    {attempt.workshop.completed && !decisionReady && !terminal && (
                      <div className="workshop-completed-cta">
                        <button
                          className="button primary full knowledge-cta"
                          onClick={() => setTab('Knowledge check')}
                        >
                          <span>Complete knowledge check</span>
                          <ArrowRight size={14} />
                        </button>
                      </div>
                    )}

                    {attempt.observationRecorded && (
                      <div className="observation-card">
                        <span className="tiny-label">
                          <Eye size={12} /> OBSERVATION CARD
                        </span>
                        <p>{attempt.verified ? scenario.verification : scenario.observation}</p>
                      </div>
                    )}

                    {/* Terminal Result Card or Commit a Decision */}
                    {terminal ? (
                      <div className={`result-card ${attempt.criticalError ? 'critical' : ''}`} role="status">
                        <ShieldCheck size={26} />
                        <h3>
                          {attempt.criticalError
                            ? 'A decision to revisit'
                            : attempt.phase === 'escalated'
                            ? 'Review requested'
                            : 'Assembly released'}
                        </h3>
                        <p>{attempt.outcome}</p>
                        <div className="scores">
                          <div>
                            <strong>{attempt.scores.procedure}%</strong>
                            <span>Procedure</span>
                          </div>
                          <div>
                            <strong>{attempt.scores.judgment}%</strong>
                            <span>Judgment</span>
                          </div>
                          <div>
                            <strong>{attempt.scores.knowledge}%</strong>
                            <span>Knowledge</span>
                          </div>
                        </div>
                        <button className="button secondary full" onClick={() => setTab('Knowledge check')}>
                          Review knowledge check <ArrowRight size={15} />
                        </button>
                        <small>Exercise result only. Supervised practical assessment is still required.</small>
                      </div>
                    ) : (
                      <div className="decision-section">
                        <span className="section-eyebrow">COMMIT A DECISION</span>
                        <div className="decision-buttons">
                          <button
                            className="button release"
                            disabled={!decisionReady}
                            onClick={() => act('continue')}
                          >
                            <span>Release assembly</span>
                            <ArrowRight size={14} />
                          </button>
                          <button
                            className="button secondary escalate"
                            disabled={!decisionReady}
                            onClick={() => act('escalate')}
                          >
                            Escalate for review
                          </button>
                        </div>
                        <p className="decision-caption">
                          {decisionReady
                            ? 'The final checkpoint requires a supported decision.'
                            : 'Complete all build checkpoints and answer three questions to unlock.'}
                        </p>
                      </div>
                    )}

                    {/* Workshop Insight Golden Card */}
                    {showFeedback && !terminal && (
                      <div className="mentor-note-card">
                        <div className="mentor-header">
                          <Lightbulb size={15} className="insight-bulb" />
                          <span>WORKSHOP INSIGHT</span>
                        </div>
                        <p>
                          A good assembly starts with observation. Looking closely and recording evidence are two different steps.
                        </p>
                        <button className="insight-link" onClick={() => setTab('Insights')}>
                          <span>Explore the reasoning</span>
                          <ArrowRight size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {tab === 'Knowledge check' && (
                  <div className="knowledge-content">
                    <span className="tiny-label">THINK THROUGH THE WHY</span>
                    <h2>Check your understanding</h2>
                    <p className="panel-description">
                      Three fixed questions about evidence and assembly decisions. Answer before committing your final decision.
                    </p>
                    {questions.map((question, index) => {
                      const answer = attempt.questionAnswers[question.id];
                      return (
                        <fieldset key={question.id} className="question" disabled={!!answer || terminal}>
                          <legend>
                            <span>0{index + 1}</span>
                            {question.title}
                          </legend>
                          <p>{question.prompt}</p>
                          {question.options.map(option => (
                            <button
                              key={option.id}
                              aria-pressed={answer === option.id}
                              className={`answer ${answer === option.id ? 'chosen' : ''}`}
                              onClick={() => act(`answer:${question.id}:${option.id}`)}
                            >
                              <span>{option.id.toUpperCase()}</span>
                              {option.label}
                              {answer === option.id && <Check size={14} />}
                            </button>
                          ))}
                          {answer && showFeedback && (
                            <div className="answer-feedback">
                              <strong>
                                {answer === question.correctOptionId ? 'Correct reasoning' : 'Consider the evidence'}
                              </strong>
                              <p>{question.feedback}</p>
                            </div>
                          )}
                          {answer && !showFeedback && (
                            <small className="answer-saved">
                              Answer recorded. Feedback appears after your final decision.
                            </small>
                          )}
                          {!answer && terminal && (
                            <small>Not answered during this attempt. Restart to practise this question.</small>
                          )}
                        </fieldset>
                      );
                    })}
                  </div>
                )}

                {tab === 'Insights' && (
                  <div className="insights-content">
                    <span className="tiny-label">THE REASONING BEHIND THE STEPS</span>
                    <h2>Workshop field notes</h2>
                    <p className="panel-description">
                      Authored explanations for this demonstration. No live AI or expert source is connected.
                    </p>
                    {showFeedback ? (
                      insights.map((insight, index) => (
                        <article className="insight" key={insight.id}>
                          <span className="insight-number">0{index + 1}</span>
                          <h3>{insight.title}</h3>
                          <p>{insight.body}</p>
                          <button onClick={() => setEvidence(insight.id)}>
                            <BookOpen size={13} />
                            {insight.evidence}
                            <ArrowRight size={13} />
                          </button>
                        </article>
                      ))
                    ) : (
                      <div className="assessment-lock">
                        <ShieldCheck size={28} />
                        <h3>Reason first. Review after.</h3>
                        <p>Explanatory notes and feedback unlock when you commit your assessment decision.</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Mission Checkpoints Accordion */}
              <MissionChecklist progress={progress} />
            </section>
          </div>

          {/* Bottom Status Footer (Region) */}
          <section className="workspace-status" role="region" aria-label="Workspace status and messages">
            <div className="status-summary">
              <div className="status-left">
                <CheckCircle2 size={16} className="text-green" />
                <strong className="status-title">
                  {terminal
                    ? progress.complete
                      ? 'Mission complete'
                      : 'Attempt ended - restart to review your decision'
                    : 'Your progress is saved locally'}
                </strong>
                <span className="status-divider">|</span>
                <span className="status-actions">{attempt.log.length} recorded actions</span>
              </div>
              <div className="status-right">
                <span>Demo bundle v2</span>
                <span className="dot-sep">·</span>
                <span>Revision {attempt.revision}</span>
                <span className="dot-sep">·</span>
                <div className="disclaimer-note">
                  <ShieldCheck size={14} />
                  <span>Authored practice simulation. Notes are illustrative and await instructor review.</span>
                </div>
              </div>
            </div>

            {/* Status Messages & Feedback inside workspace-status region */}
            <div className="status-messages">
              {showFeedback && lastEvent && !terminal && (
                <div className="event-feedback" role="status">
                  <CheckCircle2 size={14} />
                  <p>{lastEvent.detail}</p>
                </div>
              )}
              {reward && (
                <div className="checkpoint-reward" aria-live="polite">
                  <CheckCircle2 size={14} />
                  {reward}
                </div>
              )}
              {storageWarning && (
                <p role="alert" className="warning">
                  Browser storage is unavailable. This attempt will not survive a reload.
                </p>
              )}
              {error && (
                <p role="alert" className="warning game-error">
                  {error}
                </p>
              )}
            </div>
          </section>
        </div>
      </main>

      {/* Restart Exercise Confirmation Modal */}
      {reset && (
        <div className="modal-backdrop">
          <section className="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title">
            <RotateCcw size={26} />
            <h2 id="reset-title">Start a fresh exercise?</h2>
            <p>
              This replaces your current local attempt with{' '}
              {scenarios.find(s => s.id === reset.scenario)!.title.toLowerCase()} in{' '}
              {reset.mode === 'guided' ? 'guided practice' : 'assessment'} mode.
            </p>
            <div>
              <button className="button secondary" onClick={() => setReset(null)}>
                Cancel
              </button>
              <button className="button primary" onClick={startFresh}>
                Start fresh <ArrowRight size={14} />
              </button>
            </div>
          </section>
        </div>
      )}

      {/* Source Evidence Modal */}
      {evidence && (
        <div className="modal-backdrop">
          <section className="modal evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title">
            <button className="close-modal" aria-label="Close note" onClick={() => setEvidence(null)}>
              <X size={20} />
            </button>
            <BookOpen size={26} />
            <span className="tiny-label">ILLUSTRATIVE SOURCE NOTE</span>
            <h2 id="evidence-title">{insights.find(i => i.id === evidence)!.title}</h2>
            <p>{insights.find(i => i.id === evidence)!.body}</p>
            <div className="source-meta">
              {insights.find(i => i.id === evidence)!.evidence}
              <br />
              Authored demo content · Instructor review pending
              <br />
              No recording or expert attribution is claimed.
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
