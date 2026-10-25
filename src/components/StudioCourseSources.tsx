import { useEffect, useState } from 'react';
import { studioApi, type AnalysisConfig, type StudioRole } from '../studio-api';

export default function StudioCourseSources({ config, taskId, role, working, includeNotes, setIncludeNotes, onSaved, onError, onBusy, onDirty, review = false }: {
  config: AnalysisConfig; taskId: string; role: StudioRole; working: boolean;
  includeNotes: boolean; setIncludeNotes: (value: boolean) => void;
  onSaved: () => Promise<unknown>; onError: (message: string) => void; review?: boolean;
  onBusy: (value: boolean) => void; onDirty: (value: boolean) => void;
}) {
  const content = config.course_content;
  const [script, setScript] = useState(content?.script_text ?? '');
  const [filename, setFilename] = useState(content?.script_filename ?? '');
  const [notes, setNotes] = useState(content?.review_notes ?? '');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setScript(content?.script_text ?? ''); setFilename(content?.script_filename ?? '');
    setNotes(content?.review_notes ?? '');
  }, [taskId, content?.version]);
  useEffect(() => { onDirty(review ? notes !== (content?.review_notes ?? '') : script !== (content?.script_text ?? '')); }, [notes, script, content?.version, review, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  const disabled = working || saving;
  async function perform(action: () => Promise<unknown>) {
    setSaving(true); onBusy(true);
    try { await action(); await onSaved(); }
    catch (error) { onError(error instanceof Error ? error.message : 'Course content could not be saved.'); }
    finally { setSaving(false); onBusy(false); }
  }
  async function readScript(file: File) {
    if (file.size > 100000) { onError('Upload a UTF-8 text script of at most 20,000 characters.'); return; }
    try {
      const text = await file.text();
      if (text.length > 20000 || text.includes('\u0000')) throw new Error('Use a plain UTF-8 text script of at most 20,000 characters.');
      setScript(text); setFilename(file.name);
      await perform(() => studioApi.saveCourseContent(role, taskId, content?.version ?? 0, { script_text: text, script_filename: file.name }));
    } catch (error) { onError(error instanceof Error ? error.message : 'The script could not be read.'); }
  }
  if (!content) return null;
  return <section className="studio-course-sources" aria-label={review ? 'Expert review notes' : 'Uploaded course content'}>
    <h3>{review ? 'Expert notes for tacit extraction' : 'Course video & script'}</h3>
    {review ? <>
      <p>Add observations, reasoning, or corrections for the next extraction. Saved notes are included when the option below is selected.</p>
      <textarea aria-label="Expert review notes" value={notes} disabled={disabled} maxLength={10000} onChange={event => setNotes(event.target.value)} placeholder="Explain an observed cue, decision, or exception…"/>
      <button disabled={disabled || notes === content.review_notes} onClick={() => void perform(() => studioApi.saveCourseContent(role, taskId, content.version, { review_notes: notes }))}>{saving ? 'Saving notes…' : 'Save expert notes'}</button>
    </> : <>
      <p>The latest uploaded video and saved script for this course are selected automatically.</p>
      <div className="studio-source-file"><strong>Video</strong><span>{content.video ? `${content.video.filename} · ${(content.video.duration_ms / 1000).toFixed(1)} seconds` : 'No course video uploaded'}</span></div>
      <label>Upload course video (MP4)<input aria-label="Upload course video" type="file" accept="video/mp4,.mp4" disabled={disabled || !config.media_upload_enabled} onChange={event => { const file = event.target.files?.[0]; if (file) void perform(() => studioApi.uploadVideo(role, taskId, file)); event.target.value = ''; }}/></label>
      {!config.media_upload_enabled && <p>Video upload is disabled in the backend configuration.</p>}
      <label>Upload course script (.txt, .md, .srt, .vtt)<input aria-label="Upload course script" type="file" accept=".txt,.md,.srt,.vtt,text/plain" disabled={disabled} onChange={event => { const file = event.target.files?.[0]; if (file) void readScript(file); event.target.value = ''; }}/></label>
      <label>Course script<textarea aria-label="Course script" value={script} disabled={disabled} maxLength={20000} onChange={event => setScript(event.target.value)} placeholder="Upload or paste the course narration / transcript…"/></label>
      {content.script_filename && <small>Saved script: {content.script_filename}</small>}
      <button disabled={disabled || script === content.script_text} onClick={() => void perform(() => studioApi.saveCourseContent(role, taskId, content.version, { script_text: script, script_filename: filename || 'Course script' }))}>{saving ? 'Saving source…' : 'Save course script'}</button>
    </>}
    {(review ? notes !== content.review_notes : script !== content.script_text) && <button disabled={disabled} onClick={() => { setNotes(content.review_notes); setScript(content.script_text); setFilename(content.script_filename); }}>Discard {review ? 'note' : 'script'} edits</button>}
    <label className="studio-defer"><input type="checkbox" checked={includeNotes} disabled={disabled} onChange={event => setIncludeNotes(event.target.checked)}/>Include saved expert review notes in course extraction</label>
    {!review && content.review_notes && <details><summary>Saved expert notes</summary><p>{content.review_notes}</p></details>}
  </section>;
}
