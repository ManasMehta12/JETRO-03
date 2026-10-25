import type { AnalysisRun } from '../studio-api';

export default function StudioAnalysisHistory({ runs }: { runs: AnalysisRun[] }) {
  return <section className="studio-analysis-history" aria-label="Diagnosis history">
    <h3>Diagnosis history</h3>
    {!runs.length && <p>No diagnosis runs recorded for this task.</p>}
    {runs.map(run => <details key={run.id} className="studio-history-run">
      <summary>{run.mode === 'live' ? 'AI diagnosis' : 'Illustrative rehearsal'} · {run.status} · revision {run.revision}{run.created_at ? ` · ${new Date(run.created_at).toLocaleString()}` : ''}</summary>
      <dl><dt>Run</dt><dd>{run.id}</dd><dt>Model</dt><dd>{run.model ?? 'Not recorded'}</dd><dt>Source</dt><dd>{run.source_label ?? 'Not recorded'}</dd><dt>Requested by</dt><dd>{run.requested_by ?? 'Not recorded'}</dd><dt>Stage</dt><dd>{run.stage.replaceAll('_', ' ')}</dd></dl>
      {run.evaluation?.source_manifest && <div><strong>Course inputs</strong><p>Video: {run.evaluation.source_manifest.video?.filename ?? 'None'}<br/>Script: {run.evaluation.source_manifest.script_filename || 'None'}<br/>Expert review notes: {run.evaluation.source_manifest.include_review_notes ? 'Included' : 'Excluded'}</p></div>}
      {run.error && <p role="status">{run.error.code}: {run.error.message}</p>}
      {run.evaluation && <div><strong>{run.evaluation.passed ? 'Source evaluation passed' : 'Source evaluation needs attention'}</strong><p>{run.evaluation.summary}</p>{run.evaluation.issues.map((issue, index) => <p key={index}>{issue}</p>)}</div>}
      <details><summary>Analyzed source material</summary><pre>{run.source_notes}</pre></details>
      {run.proposals.map(proposal => <article className="studio-history-proposal" key={proposal.id}>
        <strong>{proposal.knowledge_unit_id} · {proposal.field}</strong>
        <p>Previous value: {proposal.before ?? 'Unknown'}</p><p>Extracted proposal: {proposal.after}</p>
        <blockquote>{proposal.source_quote}</blockquote><p>{proposal.rationale}</p>
      </article>)}
      {!run.proposals.length && <p>No proposed changes recorded.</p>}
      {run.release_id && <p>Published release: {run.release_id}</p>}
    </details>)}
  </section>;
}
