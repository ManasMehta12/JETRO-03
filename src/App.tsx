import { lazy, Suspense, useEffect, useState } from 'react';
import { ArrowDownRight, ArrowRight, BookOpen, Box, Check, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, Crosshair, Expand, Eye, Layers3, Lightbulb, Maximize2, MousePointer2, RotateCcw, ShieldCheck, Sparkles, Target, Wrench, X } from 'lucide-react';
import { availableActions, componentInfo, createAttempt, insights, isTerminal, questions, scenarios, transition } from './simulation';
import type { ComponentId, Mode, ScenarioId } from './simulation';
import { MissionBanner, MissionChecklist, WorkshopTask, WorkshopTray } from './components/WorkshopUI';
import { getMissionProgress } from './mission';
import { getWorkshopObjective } from './workshop';
import { restoreAttempt, serializeAttempt, STORAGE_KEY } from './persistence';

const AssemblyScene = lazy(() => import('./components/AssemblyScene'));
const parts: { id: ComponentId; name: string; subtitle: string; code: string }[] = [
  { id: 'base', name: 'Base plate', subtitle: 'Reference & support', code: '01' },
  { id: 'housing', name: 'Bearing housing', subtitle: 'Outer ring support', code: '02' },
  { id: 'shaft', name: 'Drive shaft', subtitle: 'Rotating element', code: '03' },
  { id: 'bearing', name: 'Ball bearing', subtitle: 'Rolling element assembly', code: '04' },
];
const steps = ['Inspect', 'Build', 'Seat', 'Test', 'Decide'];
function readInitial() { try { return restoreAttempt(localStorage.getItem(STORAGE_KEY)); } catch { return createAttempt(); } }

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
  const objective = getWorkshopObjective(attempt.workshop);
  const stepIndex = terminal ? 5 : attempt.verified ? 4 : attempt.seated ? 3 : attempt.aligned ? 2 : attempt.observationRecorded ? 1 : 0;
  const sceneStage = terminal && attempt.verified ? 6 : attempt.verified ? 5 : attempt.seated ? 4 : attempt.aligned ? 3 : attempt.observationRecorded ? 2 : attempt.inspected.length ? 1 : 0;
  const inspected = attempt.inspected.includes(selected);
  const lastEvent = attempt.log.at(-1);

  useEffect(() => {
    if (!reward) return;
    const timer = window.setTimeout(() => setReward(''), 4000);
    return () => window.clearTimeout(timer);
  }, [reward, attempt.revision]);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, serializeAttempt(attempt)); setStorageWarning(false); }
    catch { setStorageWarning(true); }
  }, [attempt]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') { setEvidence(null); setReset(null); setWide(false); } };
    window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler);
  }, []);
  useEffect(() => {
    if (!reset && !evidence) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const controls = dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], select, [tabindex="0"]');
    controls?.[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', trap);
    return () => { document.removeEventListener('keydown', trap); previous?.focus(); };
  }, [reset, evidence]);

  function act(id: string) {
    try {
      const next = transition(attempt, id);
      const gained = getMissionProgress(next).xp - progress.xp;
      setAttempt(next); setError(''); setReward(gained > 0 ? `Checkpoint complete · +${gained} XP` : '');
      if (id === 'workshop:verify') setExploded(false);
    }
    catch (err) { setReward(''); setError(err instanceof Error ? err.message : 'Unable to apply action.'); }
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
    if (!parts.some(item => item.id === part)) { setError('Choose a component from the tray.'); return; }
    try {
      let next = attempt;
      if (next.workshop.heldPart !== part) next = transition(next, `workshop:pick:${part}`);
      next = transition(next, `workshop:place:${part}`);
      const gained = getMissionProgress(next).xp - progress.xp;
      setAttempt(next); setSelected(part as ComponentId); setError(''); setReward(gained ? `Checkpoint complete · +${gained} XP` : '');
    } catch (err) { setReward(''); setError(err instanceof Error ? err.message : 'That part cannot be placed here yet.'); }
  }
  function startFresh() {
    if (!reset) return;
    setAttempt(createAttempt(reset.scenario, reset.mode)); setSelected('bearing'); setTab('Practice'); setExploded(true); setResetKey(key => key + 1); setReset(null); setError(''); setReward('');
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" aria-label="Takumi home"><span className="brand-symbol"><Layers3 size={22} /></span>takumi<span className="brand-period">.</span></a>
      <div className="workspace-label">LEARNING WORKSPACE</div>
      <nav aria-label="Workspace">{[
        { name: 'Practice', label: 'Playground', icon: Box },
        { name: 'Knowledge check', label: 'Knowledge check', icon: ClipboardCheck },
        { name: 'Insights', label: 'Field notes', icon: BookOpen },
      ].map(({ name, label, icon: Icon }) => <button key={name} className={`nav-item ${tab === name ? 'current' : ''}`} aria-label={label} aria-current={tab === name ? 'page' : undefined} onClick={() => setTab(name)}><Icon size={19}/>{label}{tab === name && <span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-course"><span className="tiny-label">YOUR LEARNING PATH</span><div className="course-icon"><Wrench size={20} /></div><h3>Mechanical foundations</h3><p>Small details.<br/>Better decisions.</p><div className="mini-progress"><span style={{ width: `${Math.round(progress.completed / progress.total * 100)}%` }} /></div><span className="course-progress">Module 01 of 03</span></div>
      <div className="sidebar-bottom"><div className="avatar">AK</div><div><strong>Apprentice workspace</strong><span>Local demo session</span></div><ShieldCheck size={16} /></div>
    </aside>

    <main id="playground">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14} /> Playground <ChevronRight size={14} /><strong>Mechanical assembly</strong></div><span className="demo-badge"><span /> Practice workspace</span></header>
      <div className="page-content">
        <div className="page-heading"><div><div className="eyebrow">LEARN BY DOING <span> / </span> MODULE 01</div><h1>Bearing assembly<span className="title-dot">.</span></h1><p>Get hands-on with the details that make an assembly work.</p></div><button className="button secondary restart" aria-label="Restart exercise" onClick={() => setReset({ scenario: attempt.scenarioId, mode: attempt.mode })}><RotateCcw size={15} /> Restart exercise</button></div>

        <div className="scenario-bar"><div className="scenario-icon"><Target size={20} /></div><div className="scenario-copy"><span className="tiny-label">YOUR SCENARIO</span><strong>{scenario.title}</strong></div><div className="scenario-selects"><label>Scenario<select aria-label="Scenario" value={attempt.scenarioId} onChange={e => setReset({ scenario: e.target.value as ScenarioId, mode: attempt.mode })}><option value="standard">01 · A clean assembly</option><option value="uncertain">02 · The uncertain fit</option></select></label><label>Learning mode<select aria-label="Learning mode" value={attempt.mode} onChange={e => setReset({ scenario: attempt.scenarioId, mode: e.target.value as Mode })}><option value="guided">Guided practice</option><option value="assessment">Assessment</option></select></label></div><div className="scenario-meta"><span><Layers3 size={14} /> {scenario.difficulty}</span><span>~ 5 min</span></div></div>

        <MissionBanner progress={progress}/>
        <div className="workspace-grid"><section className={`simulation-column ${attempt.observationRecorded ? "building" : ""}`} aria-label="Assembly simulation">
          <div className={`scene-card ${wide ? 'scene-wide' : ''}`}><div className="scene-top"><div><span className="live-dot" /> INTERACTIVE ASSEMBLY</div><span className="scene-model">SHAFT + BEARING / DEMO V1</span></div>
            <div className={`scene-viewport ${dragOver ? 'drag-over' : ''}`} onDragOver={event => { event.preventDefault(); if (attempt.observationRecorded && !attempt.workshop.completed) { event.dataTransfer.dropEffect = 'move'; setDragOver(true); } }} onDragLeave={() => setDragOver(false)} onDrop={event => { event.preventDefault(); setDragOver(false); dropPart(event.dataTransfer.getData('application/takumi-part')); }}><Suspense fallback={<div className="scene-loading"><Layers3 size={28} /><span>Preparing your workbench…</span></div>}><AssemblyScene selected={selected} onSelect={setSelected} stage={sceneStage} exploded={exploded} resetKey={resetKey} workshop={attempt.workshop} onWorkshopAction={workshopAct}/></Suspense>{dragOver && <div className="drop-target-message">Drop to place on the assembly target</div>}<span className="view-label"><span /> PERSPECTIVE VIEW</span><div className="scene-axis"><span className="axis-y">Y</span><span className="axis-z">Z</span><span className="axis-x">X</span></div><div className="part-callout"><span className="callout-dot"/><div><span>SELECTED COMPONENT</span><strong>{parts.find(p => p.id === selected)!.name}</strong></div></div></div>
            <div className="scene-toolbar"><span className="orbit-hint"><MousePointer2 size={14} /> Drag to orbit <i/> Scroll to zoom</span><div><button aria-label="Exploded view" aria-pressed={exploded} className={exploded ? 'tool active' : 'tool'} onClick={() => setExploded(value => !value)}><Expand size={15} /><span>Exploded view</span></button><button aria-label="Reset camera" className="tool" onClick={() => setResetKey(key => key + 1)}><Crosshair size={16} /></button><button aria-label={wide ? 'Close expanded view' : 'Expand viewport'} className="tool" onClick={() => setWide(value => !value)}>{wide ? <X size={16}/> : <Maximize2 size={15}/>}</button></div></div>
          </div>
          <div className="components-card"><div className="section-caption"><h2>Know your components</h2><span>{attempt.inspected.length} / 4 inspected</span></div><div className="component-list">{parts.map(part => <button key={part.id} className={`component ${selected === part.id ? 'selected' : ''}`} aria-label={`Select ${part.name}`} aria-pressed={selected === part.id} onClick={() => setSelected(part.id)}><span className={`part-glyph ${part.id}`}><span/></span><strong>{part.name}</strong><span className="part-subtitle">{part.subtitle}</span><span className="part-number">{attempt.inspected.includes(part.id) ? <CheckCircle2 size={14}/> : part.code}</span></button>)}</div></div>
          <WorkshopTray state={attempt.workshop} enabled={attempt.observationRecorded && !terminal} onAction={workshopAct}/>
          <div className="demo-note"><ShieldCheck size={16}/><p><strong>A practice space for better judgment.</strong> Authored simulation, not a physics solver. Notes are illustrative and await instructor review.</p><span>FIXED CONTENT · V1</span></div>
        </section>

        <section className="learning-card" aria-label="Learning panel"><div className="tabs" role="tablist" aria-label="Learning views">{['Practice', 'Knowledge check', 'Insights'].map(name => <button role="tab" id={`tab-${name.replaceAll(" ", "-")}`} aria-controls="learning-view" aria-selected={tab === name} key={name} onClick={() => setTab(name)}>{name === 'Practice' ? <Wrench size={14}/> : name === 'Insights' ? <Lightbulb size={14}/> : <CircleHelp size={14}/>}<span>{name}</span></button>)}</div>
          <div id="learning-view" role="tabpanel" aria-labelledby={`tab-${tab.replaceAll(' ', '-')}`}>
          {tab === 'Practice'  && <div className="practice-content"><div className="panel-heading"><span className="tiny-label">YOUR NEXT MOVE</span><span className="step-count">{Math.min(stepIndex + 1, 5)} of 5</span></div><h2>{terminal ? (progress.complete ? 'Mission complete' : 'Review your attempt') : !attempt.observationRecorded ? '01. Inspect the components' : !attempt.workshop.completed ? objective.title : !decisionReady ? 'Complete your knowledge check' : 'Make your decision'}</h2><p className="panel-description">{terminal ? 'Review your completed checkpoints and the evidence behind your decision.' : !attempt.observationRecorded ? 'Inspect all four components, then request the observation card to unlock the workbench.' : !attempt.workshop.completed ? 'Pick parts from the tray, equip tools, and interact with the highlighted assembly targets.' : !decisionReady ? 'Your build is verified. Answer all three fixed questions to unlock the final decision.' : 'All prerequisites are complete. Use the recorded check to release or escalate.'}</p>
            <div className="stepper">{steps.map((step, i) => <div key={step} className={i < stepIndex ? 'done' : i === stepIndex ? 'now' : ''}><span>{i < stepIndex ? <Check size={11}/> : i + 1}</span><small>{step}</small></div>)}</div>
            {!terminal && !attempt.observationRecorded && <><div className="inspection-picker" aria-label="Inspection progress">{parts.map(part => <button key={part.id} aria-label={`Focus ${part.name}`} aria-pressed={selected === part.id} className={selected === part.id ? 'active' : ''} onClick={() => setSelected(part.id)}>{attempt.inspected.includes(part.id) ? <CheckCircle2 size={15}/> : <span>{part.code}</span>}<span>{part.name}</span></button>)}</div><div className="selected-detail"><div className="detail-top"><Box size={17}/><strong>{parts.find(p => p.id === selected)!.name}</strong>{inspected && <CheckCircle2 size={16}/>}</div><p>{componentInfo[selected].description}</p><button className="button primary full" disabled={inspected} onClick={() => act(`inspect-${selected}`)}><Eye size={15}/>{inspected ? 'Inspection recorded' : 'Inspect component'}{!inspected && <ArrowRight size={15}/>}</button></div>
              <div className="operation-actions"><button className="button secondary full" disabled={attempt.observationRecorded || attempt.inspected.length < 4} onClick={() => act('record-observation')}><ClipboardCheck size={15}/>{attempt.observationRecorded ? 'Observation recorded' : 'Request observation'}{attempt.observationRecorded && <Check size={14}/>}</button></div></>}
            {attempt.observationRecorded && !terminal && !attempt.workshop.completed && <WorkshopTask state={attempt.workshop} enabled={true} onAction={workshopAct}/>}
            {attempt.workshop.completed && !decisionReady && !terminal && <button className="button primary full knowledge-cta" onClick={() => setTab('Knowledge check')}>Complete knowledge check <ArrowRight size={14}/></button>}
            {attempt.observationRecorded && <div className="observation"><span className="tiny-label"><Eye size={12}/> OBSERVATION CARD</span><p>{attempt.verified ? scenario.verification : scenario.observation}</p></div>}
            {terminal ? <div className={`result-card ${attempt.criticalError ? 'critical' : ''}`} role="status"><ShieldCheck size={23}/><h3>{attempt.criticalError ? 'A decision to revisit' : attempt.phase === 'escalated' ? 'Review requested' : 'Assembly released'}</h3><p>{attempt.outcome}</p><div className="scores"><div><strong>{attempt.scores.procedure}%</strong><span>Procedure</span></div><div><strong>{attempt.scores.judgment}%</strong><span>Judgment</span></div><div><strong>{attempt.scores.knowledge}%</strong><span>Knowledge</span></div></div><button className="button secondary full" onClick={() => setTab('Knowledge check')}>Review knowledge check <ArrowRight size={15}/></button><small>Exercise result only. Supervised practical assessment is still required.</small></div> : <div className="decision-section"><span className="tiny-label">COMMIT A DECISION</span><div><button className="button release" disabled={!decisionReady} onClick={() => act('continue')}>Release assembly <ArrowRight size={14}/></button><button className="button secondary" disabled={!decisionReady} onClick={() => act('escalate')}>Escalate for review</button></div><p>{decisionReady ? 'The final checkpoint requires a supported decision.' : 'Complete all build checkpoints and answer three questions to unlock.'}</p></div>}
            {showFeedback && lastEvent && !terminal && <div className="event-feedback" role="status"><CheckCircle2 size={15}/><p>{lastEvent.detail}</p></div>}
            {showFeedback && !terminal && <div className="mentor-note"><span><Sparkles size={15}/> WORKSHOP INSIGHT</span><p>{stepIndex < 2 ? 'A good assembly starts with observation. Looking closely and recording evidence are two different steps.' : 'The model shows a sequence. Your decision should follow the recorded check, not how convincing the animation looks.'}</p><button onClick={() => setTab('Insights')}>Explore the reasoning <ArrowDownRight size={14}/></button></div>}
          </div>}
          {tab === 'Knowledge check' && <div className="knowledge-content"><span className="tiny-label">THINK THROUGH THE WHY</span><h2>Check your understanding</h2><p className="panel-description">Three fixed questions about evidence and assembly decisions. Answer before committing your final decision.</p>{questions.map((question, index) => { const answer = attempt.questionAnswers[question.id]; return <fieldset key={question.id} className="question" disabled={!!answer || terminal}><legend><span>0{index + 1}</span>{question.title}</legend><p>{question.prompt}</p>{question.options.map(option => <button key={option.id} aria-pressed={answer === option.id} className={`answer ${answer === option.id ? 'chosen' : ''}`} onClick={() => act(`answer:${question.id}:${option.id}`)}><span>{option.id.toUpperCase()}</span>{option.label}{answer === option.id && <Check size={14}/>}</button>)}{answer && showFeedback && <div className="answer-feedback"><strong>{answer === question.correctOptionId ? 'Correct reasoning' : 'Consider the evidence'}</strong><p>{question.feedback}</p></div>}{answer && !showFeedback && <small className="answer-saved">Answer recorded. Feedback appears after your final decision.</small>}{!answer && terminal && <small>Not answered during this attempt. Restart to practise this question.</small>}</fieldset>; })}</div>}
          {tab === 'Insights' && <div className="insights-content"><span className="tiny-label">THE REASONING BEHIND THE STEPS</span><h2>Workshop field notes</h2><p className="panel-description">Authored explanations for this demonstration. No live AI or expert source is connected.</p>{showFeedback ? insights.map((insight, index) => <article className="insight" key={insight.id}><span className="insight-number">0{index + 1}</span><h3>{insight.title}</h3><p>{insight.body}</p><button onClick={() => setEvidence(insight.id)}><BookOpen size={13}/>{insight.evidence}<ArrowRight size={13}/></button></article>) : <div className="assessment-lock"><ShieldCheck size={28}/><h3>Reason first. Review after.</h3><p>Explanatory notes and feedback unlock when you commit your assessment decision.</p></div>}</div>}
          </div>
          <MissionChecklist progress={progress}/>
        </section></div>
        <div className="activity-bar"><span className="activity-indicator"/><strong>{terminal ? (progress.complete ? 'Mission complete' : 'Attempt ended - restart to review your decision') : 'Your progress is saved locally'}</strong><span>{attempt.log.length} recorded actions</span><span className="activity-version">Demo bundle v2 <i/> Revision {attempt.revision}</span></div>
        {reward && <div className="checkpoint-reward" aria-live="polite"><CheckCircle2 size={17}/>{reward}</div>}
        {storageWarning && <p role="alert" className="warning">Browser storage is unavailable. This attempt will not survive a reload.</p>}{error && <p role="alert" className="warning game-error">{error}</p>}
      </div><footer><span>TAKUMI <span className="footer-separator">/</span> Craft becomes knowledge.</span><span>Frontend demo · Fixed scenarios · No backend connected</span></footer>
    </main>
    {reset && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title"><RotateCcw size={26}/><h2 id="reset-title">Start a fresh exercise?</h2><p>This replaces your current local attempt with {scenarios.find(s => s.id === reset.scenario)!.title.toLowerCase()} in {reset.mode === 'guided' ? 'guided practice' : 'assessment'} mode.</p><div><button className="button secondary" onClick={() => setReset(null)}>Cancel</button><button className="button primary" onClick={startFresh}>Start fresh <ArrowRight size={14}/></button></div></section></div>}
    {evidence && <div className="modal-backdrop"><section className="modal evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title"><button className="close-modal" aria-label="Close note" onClick={() => setEvidence(null)}><X size={20}/></button><BookOpen size={26}/><span className="tiny-label">ILLUSTRATIVE SOURCE NOTE</span><h2 id="evidence-title">{insights.find(i => i.id === evidence)!.title}</h2><p>{insights.find(i => i.id === evidence)!.body}</p><div className="source-meta">{insights.find(i => i.id === evidence)!.evidence}<br/>Authored demo content · Instructor review pending<br/>No recording or expert attribution is claimed.</div></section></div>}
  </div>;
}
