import type { AnalysisProposal, AnalysisRun } from '../studio-api';

export default function StudioProposalSources({ run, proposals }: { run: AnalysisRun; proposals: AnalysisProposal[] }) {
  const manifest = run.evaluation?.source_manifest;
  return <div className="studio-proposal-sources">
    <p>Proposed source references. Evidence records are created when you save reviewed extracts.</p>
    {manifest && <p>Video: {manifest.video?.filename ?? 'None'}<br/>Script: {manifest.script_filename || 'None'}<br/>Expert notes: {manifest.include_review_notes ? 'Included' : 'Excluded'}</p>}
    {proposals.map(proposal => <article className="studio-evidence-item" key={proposal.id}>
      <strong>{proposal.field}</strong>
      {proposal.video_evidence && <p>Video interval: {(proposal.video_evidence.start_ms / 1000).toFixed(1)}–{(proposal.video_evidence.end_ms / 1000).toFixed(1)} seconds ({proposal.video_evidence.modality})</p>}
      <blockquote>{proposal.source_quote}</blockquote>
    </article>)}
    <details><summary>Analyzed source snapshot</summary><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{run.source_notes}</p></details>
  </div>;
}
