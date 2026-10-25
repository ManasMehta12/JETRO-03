import type { StudioEvidence, StudioUnit, TacitField } from '../studio-api';

export default function StudioFieldProvenance({ unit, field, evidence }: { unit: StudioUnit; field: TacitField; evidence: StudioEvidence[] }) {
  const ids = unit.field_evidence?.[field] ?? [];
  const sources = evidence.filter(item => ids.includes(item.id));
  return <small className="studio-field-provenance">{!unit[field] ? 'Unknown — no value recorded' : !sources.length ? 'No field-level source recorded' : sources.every(item => item.source_label === 'illustrative') ? 'Illustrative source — requires expert verification' : `Supported by ${sources.length} source${sources.length === 1 ? '' : 's'}`}
    {sources.length > 0 && <details><summary>Field sources</summary>{sources.map(source => <p key={source.id}>{source.source_label} · {source.author} · {source.id}<br/>{source.content ?? 'Recording evidence'}</p>)}</details>}
  </small>;
}
