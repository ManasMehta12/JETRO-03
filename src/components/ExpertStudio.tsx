import { useEffect, useState } from 'react';
import { studioApi, type StudioOverview, type StudioRole, type StudioUnit, type TacitField } from '../studio-api';
import '../studio.css';

const fields: { key: TacitField; label: string; hint: string }[] = [
  { key: 'action', label: 'Action', hint: 'What the expert does' },
  { key: 'cue', label: 'Observed cue', hint: 'What the expert notices' },
  { key: 'interpretation', label: 'Interpretation', hint: 'What that observation means' },
  { key: 'decision', label: 'Decision', hint: 'How the expert responds' },
  { key: 'exception', label: 'Exception / limits', hint: 'When this guidance does not apply' },
];
const time = (value: string) => new Date(value).toLocaleString();

export default function ExpertStudio() {
  const [role, setRole] = useState<StudioRole>('expert');
  const [taskId, setTaskId] = useState('task_001');
  const [tasks, setTasks] = useState<{ id: string; title: string }[]>([]);
  const [data, setData] = useState<StudioOverview | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [edit, setEdit] = useState<StudioUnit | null>(null);
  const [note, setNote] = useState('');
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Select a knowledge unit to review its tacit reasoning and supporting evidence.');
  const [error, setError] = useState(false);
  const [view, setView] = useState<'knowledge' | 'audit'>('knowledge');

  useEffect(() => {
    let cancelled = false;
    setData(null); setBusy(true);
    Promise.all([studioApi.tasks(role), studioApi.overview(role, taskId)])
      .then(([list, overview]) => { if (!cancelled) { setTasks(list.items); setData(overview); setError(false); } })
      .catch((e: unknown) => { if (!cancelled) { setMessage(e instanceof Error ? e.message : 'Could not load Expert Studio.'); setError(true); } })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [role, taskId]);
  useEffect(() => {
    if (!data) return;
    const next = data.draft.knowledge_units.find(unit => unit.id === selectedId) ?? data.draft.knowledge_units[0];
    setEdit(next ? { ...next } : null);
    if (next) setSelectedId(next.id);
  }, [data, selectedId]);

  async function act(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(false);
    try { await action(); setData(await studioApi.overview(role, taskId)); setMessage(success); }
    catch (e) { setMessage(e instanceof Error ? e.message : 'The action could not be completed.'); setError(true); }
    finally { setBusy(false); }
  }
  function save() {
    if (!data || !edit) return;
    const original = data.draft.knowledge_units.find(unit => unit.id === edit.id)!;
    const changes: Partial<Record<TacitField, string | null>> = {};
    fields.forEach(({ key }) => { const value = edit[key]?.trim() || null; if (value !== original[key]) changes[key] = value; });
    if (!Object.keys(changes).length) { setMessage('No content changes to save.'); return; }
    void act(() => studioApi.save(role, taskId, data.draft.revision, edit, changes), 'Tacit changes saved as a new draft revision. Evaluate this revision before authorization.');
  }
  const evaluated = !!data?.evaluation?.passed && data.evaluation.revision === data.draft.revision;
  const authorized = evaluated && data?.authorization?.status === 'authorized' && data.authorization.revision === data.draft.revision;
  const published = data?.authorization?.status === 'published';
  const unitEvidence = data?.evidence.filter(item => edit?.evidence_ids.includes(item.id)) ?? [];
  const pending = data?.draft.clarifications.filter(item => item.status === 'pending' && item.knowledge_unit_id === selectedId) ?? [];
  const dirty = !!edit && !!data && fields.some(({ key }) => (edit[key] || null) !== (data.draft.knowledge_units.find(unit => unit.id === edit.id)?.[key] || null));

  return <div className="studio-shell">
    <header className="studio-header">
      <a className="studio-brand" href="/">T<span>Takumi</span></a>
      <nav aria-label="Studio modules"><button className={view === 'knowledge' ? 'active' : ''} onClick={() => setView('knowledge')}>Expert Studio</button><button className={view === 'audit' ? 'active' : ''} onClick={() => setView('audit')}>Publication audit</button><a href="/">Apprentice workspace ↗</a></nav>
      <label className="studio-role">Demo workspace<select aria-label="Demo studio role" value={role} disabled={busy} onChange={event => { setRole(event.target.value as StudioRole); setNote(''); }}><option value="expert">Expert</option><option value="admin">Tutor administrator</option></select></label>
    </header>
    <main className="studio-main">
      <div className="studio-heading"><div><span className="studio-eyebrow">KNOWLEDGE GOVERNANCE</span><h1>{role === 'admin' ? 'Tutor administration' : 'Expert Studio'}</h1></div><label>Current exercise<select aria-label="Current exercise" value={taskId} disabled={busy} onChange={event => setTaskId(event.target.value)}>{tasks.length ? tasks.map(task => <option value={task.id} key={task.id}>{task.title}</option>) : <option value="task_001">Ball bearing exercise</option>}</select></label></div>
      {data ? <>
        <section className="studio-summary" aria-label="Release workflow"><div><small>Draft revision</small><strong>r{data.draft.revision}</strong><span>{data.task.source_label} source</span></div><div><small>1 · Evaluation</small><strong>{evaluated ? 'Passed' : 'Required'}</strong><span>{data.evaluation ? `Evaluated revision ${data.evaluation.revision}` : 'Evidence and completeness checks'}</span></div><div><small>2 · Admin authorization</small><strong>{authorized ? 'Authorized' : published ? 'Published' : 'Pending'}</strong><span>Revision and expert specific</span></div><div><small>3 · Apprentice release</small><strong>{data.active_release ? `Version ${data.active_release.version}` : 'Unpublished'}</strong><span>Course and interview source</span></div></section>
        {view === 'knowledge' ? <div className="studio-workbench">
          <section className="studio-panel studio-units"><div className="studio-panel-title"><h2>Knowledge units</h2><span>{data.draft.knowledge_units.length}</span></div><div className="studio-scroll">{data.draft.knowledge_units.map((unit, index) => <button key={unit.id} className={`studio-unit ${selectedId === unit.id ? 'selected' : ''}`} onClick={() => { setSelectedId(unit.id); setAnswer(''); }}><small>{String(index + 1).padStart(2, '0')} · {unit.review_status}</small><strong>{unit.action}</strong><span>{unit.evidence_ids.length} evidence references</span></button>)}</div></section>
          <section className="studio-panel studio-editor"><div className="studio-panel-title"><h2>Tacit knowledge review</h2><span>{edit?.id}</span></div><div className="studio-scroll">{edit ? <><div className="studio-field-grid">{fields.map(({ key, label, hint }) => <label className={key === 'action' ? 'studio-field-wide' : ''} key={key}><span>{label}</span><small>{hint}</small><textarea aria-label={label} disabled={busy || role === 'admin'} value={edit[key] ?? ''} onChange={event => setEdit({ ...edit, [key]: event.target.value })} rows={key === 'action' ? 2 : 3} /></label>)}</div>{pending.map(item => <div className="studio-clarification" key={item.id}><strong>Expert clarification</strong><p>{item.question}</p><textarea aria-label="Clarification answer" value={answer} disabled={busy || role === 'admin'} onChange={event => setAnswer(event.target.value)} placeholder="Document the expert's reasoning and source context"/><button disabled={busy || role !== 'expert' || !answer.trim()} onClick={() => void act(() => studioApi.clarify(role, item.id, data.draft.revision, answer.trim()), 'Expert response recorded as evidence. Review and evaluate the resulting draft.')}>Record expert response</button></div>)}</> : <p>No draft knowledge units are available.</p>}</div><div className="studio-panel-actions"><span>{dirty ? 'Unsaved changes' : 'Changes remain draft until published'}</span><button className="studio-primary" disabled={busy || role !== 'expert' || !dirty} onClick={save}>Save draft changes</button></div></section>
          <aside className="studio-right"><section className="studio-panel studio-evidence"><div className="studio-panel-title"><h2>Source evidence</h2><span>{unitEvidence.length}</span></div><div className="studio-scroll">{unitEvidence.map(item => <article className="studio-evidence-item" key={item.id}><div><strong>{item.type.replaceAll('_', ' ')}</strong><span>{item.source_label}</span></div><p>{item.content || (item.start_ms !== null ? `Recording segment ${item.start_ms / 1000}s – ${(item.end_ms ?? item.start_ms) / 1000}s` : 'Recording evidence')}</p><small>{item.author} · {item.id}</small></article>)}{!unitEvidence.length && <p>No evidence references are attached to this unit.</p>}</div></section>
          <section className="studio-panel studio-approval"><div className="studio-panel-title"><h2>{role === 'admin' ? 'Authorize publication' : 'Evaluate & publish'}</h2></div><div className="studio-scroll"><button disabled={busy || dirty} onClick={() => void act(() => studioApi.evaluate(role, taskId, data.draft.revision), 'Draft evaluated. Review the result before requesting authorization.')}>Evaluate current revision</button>{data.evaluation && <div className="studio-check-result"><strong>{evaluated ? 'Evaluation passed' : 'Evaluation needs attention'}</strong>{data.evaluation.issues.map((issue, index) => <p key={index}>{issue.knowledge_unit_id}: {issue.problem}</p>)}</div>}<label className="studio-note">{role === 'admin' ? 'Authorization note' : 'Publication note'}<textarea value={note} onChange={event => setNote(event.target.value)} disabled={busy} placeholder={role === 'admin' ? 'Why this evaluated revision may be published' : 'Summarize the approved change for the audit record'} maxLength={1000}/></label>{role === 'admin' ? <button className="studio-primary" disabled={busy || !evaluated || !note.trim()} onClick={() => void act(() => studioApi.authorize(role, taskId, data.evaluation!.id, note.trim()), 'This evaluated revision is authorized for expert publication.')}>Authorize expert to publish</button> : <button className="studio-primary" disabled={busy || dirty || !authorized || !note.trim()} onClick={() => void act(() => studioApi.publish(role, taskId, data.draft.revision, note.trim()), 'Release published. Apprentice course content and newly generated interview sessions use this approved release.')}>Approve & publish release</button>}</div></section></aside>
        </div> : <div className="studio-audit-layout"><section className="studio-panel"><div className="studio-panel-title"><h2>Governance history</h2><span>{data.audit.length} events</span></div><div className="studio-scroll"><table><thead><tr><th>Event</th><th>Actor</th><th>Time</th><th>Details</th></tr></thead><tbody>{data.audit.map(event => <tr key={event.id}><td>{event.action.replaceAll('_', ' ')}</td><td>{event.actor_id}</td><td>{time(event.created_at)}</td><td><pre>{JSON.stringify(event.details, null, 2)}</pre></td></tr>)}</tbody></table>{!data.audit.length && <p>No studio governance events have been recorded.</p>}</div></section><section className="studio-panel"><div className="studio-panel-title"><h2>Active apprentice release</h2></div><div className="studio-scroll">{data.active_release ? <dl><dt>Release</dt><dd>{data.active_release.id}</dd><dt>Version</dt><dd>{data.active_release.version}</dd><dt>Approved by</dt><dd>{data.active_release.approved_by}</dd><dt>Published</dt><dd>{time(data.active_release.approved_at)}</dd><dt>Publication note</dt><dd>{data.active_release.approval_note}</dd><dt>Content fingerprint</dt><dd className="studio-hash">{data.active_release.content_hash}</dd></dl> : <p>No release is currently published.</p>}</div></section></div>}
      </> : <div className="studio-empty"><h2>{busy ? 'Loading Expert Studio…' : 'Studio could not load'}</h2>{!busy && <button onClick={() => window.location.reload()}>Reconnect</button>}</div>}
    </main><footer className={`studio-status ${error ? 'error' : ''}`} aria-label="Studio status"><span role={error ? 'alert' : 'status'}>{busy ? 'Working…' : message}</span><span>Demo role switching · approvals enforced by the server</span></footer>
  </div>;
}
