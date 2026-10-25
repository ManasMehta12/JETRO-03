import { useEffect, useRef } from 'react';
import type { StudioOverview } from '../studio-api';

export default function StudioResetDialog({ data, busy, onCancel, onConfirm }: { data: StudioOverview; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} className="studio-reset-dialog" aria-labelledby="studio-reset-title" aria-describedby="studio-reset-description" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="studio-reset-title">Reset all Expert panel data?</h2>
    <p id="studio-reset-description">This permanently clears the connected task, “{data.task.title}”, across AI diagnosis, Expert review, and Publication audit. Unsaved edits will also be discarded.</p>
    <ul><li>{data.draft.knowledge_units.length} draft knowledge units and their revision history</li><li>{data.evidence.length} evidence records, uploaded media, and processing results</li><li>{data.draft.clarifications.length} clarifications and responses</li><li>{data.analysis_runs?.length ?? 0} diagnosis runs, evaluations, and audit history</li><li>All published releases for this task and current learner progress linked to those releases</li></ul>
    <p>You will start with empty source notes and an empty draft. Enter new expert source notes and run live AI to extract new knowledge. Task details and AI settings are kept.</p>
    <div className="studio-reset-actions"><button autoFocus disabled={busy} onClick={onCancel}>Cancel</button><button className="studio-danger" disabled={busy} onClick={onConfirm}>{busy ? 'Resetting…' : 'Reset all data'}</button></div>
  </dialog>;
}
