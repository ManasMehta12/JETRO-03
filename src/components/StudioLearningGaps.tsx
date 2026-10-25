import type { AnalysisRun } from '../studio-api';

const clock = (ms: number) => `${Math.floor(ms / 60000)}:${Math.floor(ms / 1000 % 60).toString().padStart(2, '0')}`;

export default function StudioLearningGaps({ run }: { run: AnalysisRun }) {
  const gaps = run.evaluation?.learning_gaps;
  if (!gaps) return null;
  return <section aria-label="Nuances and learning gaps" className="studio-learning-gaps">
    <h3>Nuances &amp; learning gaps</h3>
    <p>{gaps.length} insights · {gaps.filter(gap => gap.status === 'suggested_fix').length} proposed fixes · {gaps.filter(gap => gap.status === 'expert_required').length} expert questions</p>
    {!gaps.length && <p>No additional learning gaps reported. Review the extracted steps for completeness.</p>}
    {gaps.map(gap => <article className="studio-proposal" key={gap.id}>
      <strong>{gap.field === 'cue' ? 'What to observe' : gap.field === 'interpretation' ? 'Why it matters' : gap.field === 'decision' ? 'How to decide' : 'Exceptions and limits'}</strong>
      <p>{gap.missing_explanation}</p>
      {gap.video_evidence && <small>Video {clock(gap.video_evidence.start_ms)}–{clock(gap.video_evidence.end_ms)} · {gap.video_evidence.modality}</small>}
      <blockquote>{gap.source_quote}</blockquote>
      {gap.status === 'suggested_fix' ? <><strong>Suggested explanation</strong><p>{gap.suggested_fix}</p><small>Review the matching {gap.field} patch below to include this explanation in the apprentice course.</small></>
        : gap.status === 'already_covered' ? <p>The draft already contains this explanation.</p>
        : <><strong>Expert input needed</strong><p>{gap.expert_question}</p><small>Save the selected extracts to draft, then answer this question in Review. You can also add expert notes and rerun diagnosis.</small></>}
    </article>)}
    <p>Only selected, approved field patches are published. Unanswered questions remain unknown.</p>
  </section>;
}
