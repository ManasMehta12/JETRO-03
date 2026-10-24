import { useEffect, useState } from 'react';
import { studioApi, type AnalysisConfig, type AnalysisRun, type StudioOverview, type StudioUnit, type TacitField } from '../studio-api';
import '../studio.css';

const fields: { key: TacitField; label: string }[] = [{ key: 'action', label: 'Action' }, { key: 'cue', label: 'Observed cue' }, { key: 'interpretation', label: 'Interpretation' }, { key: 'decision', label: 'Decision' }, { key: 'exception', label: 'Exception / limits' }];
const errorText = (e: unknown) => e instanceof Error ? e.message : 'The action could not be completed.';

export default function ExpertStudio({ administration = false }: { administration?: boolean }) {
  const role = administration ? 'admin' : 'expert';
  const [data, setData] = useState<StudioOverview | null>(null);
  const [config, setConfig] = useState<AnalysisConfig | null>(null);
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [sourceNotes, setSourceNotes] = useState('');
  const [requestMode, setRequestMode] = useState<'live' | 'rehearsal'>('live');
  const [identity, setIdentity] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [edit, setEdit] = useState<StudioUnit | null>(null);
  const [note, setNote] = useState('');
  const [answer, setAnswer] = useState('');
  const [deferUnanswered, setDeferUnanswered] = useState(false);
  const [answerField, setAnswerField] = useState<TacitField | ''>('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Run a diagnosis, review the proposed changes, then approve publication to the apprentice course.');
  const [error, setError] = useState(false);
  const [view, setView] = useState<'diagnosis' | 'knowledge' | 'audit'>('diagnosis');
  const original = data?.draft.knowledge_units.find(unit => unit.id === edit?.id);
  const dirty = !!edit && !!original && fields.some(({ key }) => (edit[key] || null) !== (original[key] || null));
  const pending = data?.draft.clarifications.filter(item => item.status === 'pending') ?? [];
  const taskId = data?.task.id ?? '';
  const working = busy || run?.status === 'running';
  const unsaved = dirty || !!answer.trim();

  useEffect(() => {
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [unsaved]);

  async function refresh() {
    const { overview, analysis: settings, latest_run: latest, user } = await studioApi.workspace(role);
    setData(overview); setConfig(settings); setRun(latest?.mode === requestMode ? latest : null);
    setIdentity(user.display_name);
    setEdit(previous => overview.draft.knowledge_units.find(unit => unit.id === previous?.id) ?? overview.draft.knowledge_units[0] ?? null);
    return settings;
  }
  useEffect(() => {
    let alive = true;
    setBusy(true);
    studioApi.workspace(role)
      .then(({ overview, analysis: settings, latest_run: latest, user }) => { if (alive) { setData(overview); setEdit(overview.draft.knowledge_units[0] ?? null); setConfig(settings); setSourceNotes(latest?.mode === 'live' ? latest.source_notes : settings.source_notes); setIdentity(user.display_name); setRun(latest?.mode === 'live' ? latest : null); setSelected(latest?.mode === 'live' ? latest.proposals.map(item => item.id) : []); } })
      .catch(e => { if (alive) { setMessage(errorText(e)); setError(true); } }).finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [role]);
  useEffect(() => {
    if (run?.status !== 'running') return;
    let alive = true;
    const timer = window.setInterval(() => { void studioApi.latestAnalysis(role, taskId).then(latest => { if (alive && latest) { setRun(latest); if (latest.status === 'ready') setSelected(latest.proposals.map(item => item.id)); } }).catch(e => { if (alive) { setMessage(errorText(e)); setError(true); } }); }, 1200);
    return () => { alive = false; window.clearInterval(timer); };
  }, [run?.status]);
  async function act(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(false);
    try { await action(); await refresh(); setMessage(success); }
    catch (e) { setMessage(errorText(e)); setError(true); }
    finally { setBusy(false); }
  }
  function guard(action: () => void) {
    if (unsaved) { setMessage('Save or discard your current edits and clarification response before changing views.'); setError(true); return; }
    action();
  }
  function publication() {
    try { localStorage.setItem('takumi-publication', JSON.stringify({ task_id: taskId, at: Date.now() })); } catch { /* The apprentice also checks for updates periodically. */ }
    window.dispatchEvent(new Event('takumi-publication'));
  }
  async function diagnose() {
    if (!data || unsaved) return;
    setBusy(true); setError(false); setMessage('Diagnosis requested. Source analysis, extraction and patch evaluation run on the server.');
    const timer = window.setInterval(() => { void studioApi.latestAnalysis(role, taskId).then(latest => { if (latest) setRun(latest); }).catch(() => {}); }, 1200);
    try {
      const result = await studioApi.analyze(role, taskId, data.draft.revision, sourceNotes, requestMode);
      setRun(result); setSelected(result.proposals.map(item => item.id));
      setMessage(result.status === 'failed' ? result.error?.message ?? 'Diagnosis failed. No changes were published.' : 'Diagnosis complete. Review source quotes, patches and evaluation before approving publication.');
      setError(result.status === 'failed');
    } catch (e) { setMessage(errorText(e)); setError(true); await studioApi.latestAnalysis(role, taskId).then(setRun).catch(() => {}); }
    finally { window.clearInterval(timer); setBusy(false); }
  }
  function save() {
    if (!data || !edit || !original) return;
    const changes: Partial<Record<TacitField, string | null>> = {};
    fields.forEach(({ key }) => { const value = edit[key]?.trim() || null; if (value !== original[key]) changes[key] = value; });
    void act(() => studioApi.save(role, taskId, data.draft.revision, edit, changes), 'Draft saved. Evaluate the new revision before publishing.');
  }
  const evaluated = !!data?.evaluation?.passed && data.evaluation.revision === data.draft.revision && !data.evaluation.stale;
  const current = run?.revision === data?.draft.revision;
  const canPublish = run?.status === 'ready' && run.mode === requestMode && run.evaluation?.passed && current && sourceNotes === run.source_notes && selected.length > 0 && (!pending.length || deferUnanswered);
  const evidence = data?.evidence.filter(item => edit?.evidence_ids.includes(item.id)) ?? [];
  const publishedUnit = data?.active_release?.knowledge_units.find(unit => unit.id === edit?.id);

  return <div className="studio-shell">
    <header className="studio-header"><a className="studio-brand" href="/">T<span>Takumi</span></a><nav aria-label="Studio modules">{(['diagnosis', 'knowledge', 'audit'] as const).map(item => <button key={item} className={view === item ? 'active' : ''} onClick={() => guard(() => setView(item))}>{item === 'diagnosis' ? 'AI diagnosis' : item === 'knowledge' ? 'Expert review' : 'Publication audit'}</button>)}<a href="/">Apprentice workspace ↗</a></nav><span className="studio-role">{identity || 'Connecting...'}</span></header>
    <main className="studio-main"><div className="studio-heading"><div><span className="studio-eyebrow">EXPERT KNOWLEDGE CAPTURE</span><h1>{administration ? 'Tutor administration' : 'Expert Studio'}</h1></div><div className="studio-heading-actions"><span className="studio-connected">{data ? `${data.task.title} - connected course` : 'Loading connected course'}</span><button disabled={working || unsaved} onClick={() => void act(async () => { await refresh(); }, 'Latest draft and publication state loaded.')}>Refresh</button></div></div>
      {data ? <><section className="studio-summary" aria-label="Release workflow"><div><small>Current draft</small><strong>Revision {data.draft.revision}</strong><span>{data.task.source_label} source</span></div><div><small>Diagnosis mode</small><strong>{requestMode === 'rehearsal' ? 'Explicit rehearsal' : config?.mode === 'live' ? 'Live AI agents' : 'Configuration required'}</strong><span>{requestMode === 'rehearsal' ? 'Authored illustrative proposals' : config?.model}</span></div><div><small>Expert review</small><strong>{pending.length} pending clarification{pending.length === 1 ? '' : 's'}</strong><span>Review source and technical accuracy</span></div><div><small>Apprentice release</small><strong>{data.active_release ? `Version ${data.active_release.version}` : 'Unpublished'}</strong><span>Course and new interview scripts</span></div></section>
      {view === 'diagnosis' ? <div className="studio-diagnosis-layout">
        <section className="studio-panel studio-source"><div className="studio-panel-title"><h2>Expert source notes</h2><span>{requestMode === 'rehearsal' ? 'illustrative fixture' : config?.source_label}</span></div><div className="studio-scroll"><label className="studio-analysis-mode">Analysis mode<select aria-label="Analysis mode" value={requestMode} disabled={working} onChange={event => { const mode = event.target.value as 'live' | 'rehearsal'; setRequestMode(mode); setSourceNotes(mode === 'rehearsal' ? config?.rehearsal_source_notes ?? '' : config?.source_notes ?? ''); setRun(null); setSelected([]); setDeferUnanswered(false); }}><option value="live">Live AI agents</option>{config?.rehearsal_available && <option value="rehearsal">Illustrative rehearsal (no AI call)</option>}</select></label><p>{requestMode === 'rehearsal' ? 'This explicitly selected rehearsal uses authored fixture data.' : 'Source material is loaded from the connected task evidence. Add expert notes for the agents to analyze.'}</p><label className="studio-source-label">Source material<textarea aria-label="Expert source notes" value={sourceNotes} disabled={working} onChange={event => setSourceNotes(event.target.value)}/></label><p className="studio-mode-notice">{requestMode === 'rehearsal' ? 'Illustrative rehearsal: authored proposals; no AI service will be called.' : config?.notice}</p><ol className="studio-agent-steps">{config?.agent_roles.map(agent => <li key={agent.stage} aria-current={run?.stage === agent.stage ? 'step' : undefined}>{agent.label}{run?.stage === agent.stage ? ' - running' : ''}</li>)}</ol></div><div className="studio-panel-actions"><button className="studio-primary" disabled={working || !config?.enabled || (requestMode === 'live' && config.mode !== 'live') || !sourceNotes.trim() || unsaved} onClick={() => void diagnose()}>{working ? 'Diagnosis in progress…' : requestMode === 'live' ? 'Run AI diagnosis' : 'Run illustrative rehearsal'}</button></div></section>
        <section className="studio-panel studio-proposals"><div className="studio-panel-title"><h2>Proposed tacit changes</h2><span>{run?.proposals.length ?? 0} patches</span></div><div className="studio-scroll">{run ? <><div className="studio-run-state" role="status"><strong>{run.mode === 'live' ? 'AI agent run' : 'Rehearsal run'} · {run.status}</strong><span>{run.stage.replaceAll('_', ' ')} · draft r{run.revision}</span></div>{run.error && <p>{run.error.message}</p>}{run.proposals.map(proposal => <article className="studio-proposal" key={proposal.id}><label className="studio-proposal-selection"><input type="checkbox" checked={selected.includes(proposal.id)} disabled={working || run.status !== 'ready'} onChange={event => setSelected(ids => event.target.checked ? [...ids, proposal.id] : ids.filter(id => id !== proposal.id))}/><strong>{fields.find(field => field.key === proposal.field)?.label} · {proposal.knowledge_unit_id}</strong></label><div className="studio-diff"><div><small>Current draft</small><p>{proposal.before || 'No guidance recorded'}</p></div><div><small>Proposed change</small><p>{proposal.after}</p></div></div><blockquote><strong>Source quote</strong><p>{proposal.source_quote}</p></blockquote><p className="studio-rationale">{proposal.rationale}</p></article>)}</> : <div className="studio-diagnosis-empty"><h3>Diagnose the current exercise</h3><p>One action runs source analysis, tacit extraction and patch evaluation. Reviewable changes appear here before publication.</p></div>}</div></section>
        <section className="studio-panel studio-publish"><div className="studio-panel-title"><h2>Evaluate & publish</h2></div><div className="studio-scroll">{run?.evaluation ? <div className="studio-check-result"><strong>{run.evaluation.passed ? 'Patch evaluation passed' : 'Patch evaluation needs attention'}</strong><p>{run.evaluation.summary}</p>{run.evaluation.issues.map((issue, index) => <p key={index}>{typeof issue === 'string' ? issue : JSON.stringify(issue)}</p>)}</div> : <p>Evaluation appears after the agents finish. Publication requires successful evaluation and your explicit approval.</p>}{run && !current && run.status !== 'published' && <p>This diagnosis belongs to an older revision. Run a new diagnosis.</p>}{run && sourceNotes !== run.source_notes && <p>Source notes changed. Run diagnosis again before approving these changes.</p>}{pending.length > 0 && <label className="studio-defer"><input type="checkbox" checked={deferUnanswered} disabled={working} onChange={event => setDeferUnanswered(event.target.checked)}/>Keep {pending.length} unanswered expert prompts as unknown and defer them for this demo</label>}<label className="studio-note">Publication note<textarea aria-label="Publication note" value={note} disabled={working} onChange={event => setNote(event.target.value)} maxLength={1000}/></label><p>Selected patches update the course and source for new interview sessions. Publication starts a fresh learning pathway for this release.</p><button className="studio-primary" disabled={working || !canPublish || !note.trim()} onClick={() => void act(async () => { await studioApi.publishAnalysis(role, taskId, run!.id, data.draft.revision, selected, note.trim(), deferUnanswered); publication(); }, 'Changes published. The apprentice course and new interview scripts now use this release.')}>Approve & publish changes</button>{run?.status === 'published' && <a className="studio-apprentice-cta" href="/">View updated apprentice course ↗</a>}</div></section>
      </div> : view === 'knowledge' ? <div className="studio-workbench">
        <section className="studio-panel studio-units"><div className="studio-panel-title"><h2>Knowledge units</h2><span>{data.draft.knowledge_units.length}</span></div><div className="studio-scroll">{data.draft.knowledge_units.map((unit, index) => <button key={unit.id} className={`studio-unit ${edit?.id === unit.id ? 'selected' : ''}`} onClick={() => guard(() => { setEdit({ ...unit }); setAnswer(''); setAnswerField(''); })}><small>{String(index + 1).padStart(2, '0')} · {unit.review_status}</small><strong>{unit.action}</strong><span>{unit.evidence_ids.length} evidence references</span></button>)}</div></section>
        <section className="studio-panel studio-editor"><div className="studio-panel-title"><h2>Tacit knowledge review</h2><span>{edit?.id}</span></div><div className="studio-scroll">{edit && <><div className="studio-field-grid">{fields.map(({ key, label }) => <label className={key === 'action' ? 'studio-field-wide' : ''} key={key}><span>{label}</span><textarea aria-label={label} disabled={working} value={edit[key] ?? ''} onChange={event => setEdit({ ...edit, [key]: event.target.value })} rows={key === 'action' ? 2 : 3}/>{publishedUnit && (publishedUnit[key] || null) !== (edit[key] || null) && <div className="studio-previous"><strong>Currently published</strong><p>{publishedUnit[key] || 'No guidance recorded'}</p></div>}</label>)}</div>{pending.filter(item => item.knowledge_unit_id === edit.id).map(item => <div className="studio-clarification" key={item.id}><strong>Expert clarification</strong><p>{item.question}</p><textarea aria-label="Clarification answer" value={answer} disabled={working} onChange={event => setAnswer(event.target.value)}/><label>Also apply answer to<select aria-label="Clarification target field" value={answerField} disabled={working} onChange={event => setAnswerField(event.target.value as TacitField | '')}><option value="">Evidence only — no field update</option>{fields.map(field => <option value={field.key} key={field.key}>{field.label}</option>)}</select></label><button disabled={working || dirty || !answer.trim()} onClick={() => void act(async () => { await studioApi.clarify(role, item.id, data.draft.revision, answer.trim(), 'answered', answerField ? { unitId: edit.id, field: answerField } : undefined); setAnswer(''); setAnswerField(''); }, 'Expert response recorded. Any selected field was updated explicitly; evaluate before publishing.')}>Record expert response</button></div>)}</>}</div><div className="studio-panel-actions"><span>{dirty ? 'Unsaved changes' : 'Changes require evaluation'}</span><button disabled={working || !unsaved} onClick={() => { setEdit(original ? { ...original } : null); setAnswer(''); setMessage('Unsaved edits discarded.'); }}>Discard edits</button><button className="studio-primary" disabled={working || !dirty} onClick={save}>Save draft changes</button></div></section>
        <aside className="studio-right"><section className="studio-panel"><div className="studio-panel-title"><h2>Source evidence</h2><span>{evidence.length}</span></div><div className="studio-scroll">{evidence.map(item => <article className="studio-evidence-item" key={item.id}><div><strong>{item.type.replaceAll('_', ' ')}</strong><span>{item.source_label}</span></div><p>{item.content || 'Recording evidence'}</p><small>{item.author} · {item.id}</small></article>)}</div></section><section className="studio-panel studio-approval"><div className="studio-panel-title"><h2>Manual revision review</h2></div><div className="studio-scroll"><button disabled={working || unsaved} onClick={() => void act(() => studioApi.evaluate(role, taskId, data.draft.revision), 'Revision evaluated. Review checks before publishing.')}>Evaluate current revision</button>{data.evaluation && <div className="studio-check-result"><strong>{evaluated ? 'Evaluation passed' : 'Evaluation needs attention'}</strong>{data.evaluation.issues.map((issue, index) => <p key={index}>{issue.knowledge_unit_id}: {issue.problem}</p>)}</div>}<label className="studio-note">Publication note<textarea aria-label="Manual publication note" value={note} onChange={event => setNote(event.target.value)} disabled={working}/></label><button className="studio-primary" disabled={working || unsaved || !evaluated || !note.trim()} onClick={() => void act(async () => { await studioApi.publish(role, taskId, data.draft.revision, note.trim()); publication(); }, 'Release published. Apprentice course and new interview scripts now use the reviewed guidance.')}>Approve & publish revision</button></div></section></aside>
      </div> : <div className="studio-audit-layout"><section className="studio-panel"><div className="studio-panel-title"><h2>Publication history</h2><span>{data.audit.length} events</span></div><div className="studio-scroll"><table><thead><tr><th>Event</th><th>Actor</th><th>Time</th><th>Details</th></tr></thead><tbody>{data.audit.map(event => <tr key={event.id}><td>{event.action.replaceAll('_', ' ')}</td><td>{event.actor_id}</td><td>{new Date(event.created_at).toLocaleString()}</td><td><pre>{JSON.stringify(event.details, null, 2)}</pre></td></tr>)}</tbody></table></div></section><section className="studio-panel"><div className="studio-panel-title"><h2>Active apprentice release</h2></div><div className="studio-scroll">{data.active_release ? <dl><dt>Release</dt><dd>{data.active_release.id}</dd><dt>Version</dt><dd>{data.active_release.version}</dd><dt>Approved by</dt><dd>{data.active_release.approved_by}</dd><dt>Published</dt><dd>{new Date(data.active_release.approved_at).toLocaleString()}</dd><dt>Publication note</dt><dd>{data.active_release.approval_note}</dd><dt>Content fingerprint</dt><dd className="studio-hash">{data.active_release.content_hash}</dd></dl> : <p>No release published.</p>}</div></section></div>}
      </> : <div className="studio-empty"><h2>{busy ? 'Loading Expert Studio…' : 'Studio could not load'}</h2>{!busy && <button onClick={() => window.location.reload()}>Reconnect</button>}</div>}
    </main><footer className={`studio-status ${error ? 'error' : ''}`} aria-label="Studio status"><span role={error ? 'alert' : 'status'}>{message}</span><span>Human approval before publication</span></footer>
  </div>;
}
