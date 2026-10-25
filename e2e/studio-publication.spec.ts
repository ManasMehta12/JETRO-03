import { test, expect, type APIRequestContext } from '@playwright/test';

async function resetDemo(request: APIRequestContext) {
  const login = await request.post('/api/v1/auth/demo-login', { data: { demo_user: 'reviewer' } });
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const reset = await request.post('/api/v1/demo/reset', { headers, data: { scope: 'full_demo', state: 'approved_baseline', confirm: 'RESET_DEMO_DATA' } });
  expect(reset.ok()).toBe(true);
}

test('admin loads server workspace and defaults to live AI without an automatic fixture fallback', async ({ page }) => {
  await page.route('**/api/v1/studio/workspace', async route => {
    const response = await route.fetch();
    const workspace = await response.json();
    workspace.overview.task.title = 'Current instructor course';
    workspace.overview.task.id = 'current_server_task';
    workspace.analysis.source_notes = 'The instructor source currently stored on the server.';
    await route.fulfill({ json: workspace });
  });
  await page.goto('/studio/admin');
  await expect(page.getByRole('heading', { name: 'Tutor administration', exact: true })).toBeVisible();
  await expect(page.getByText('Current instructor course - connected course', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Expert source notes', exact: true })).toHaveValue('The instructor source currently stored on the server.');
  await expect(page.getByRole('combobox', { name: 'Analysis mode' })).toHaveValue('live');
  await expect(page.getByRole('button', { name: 'Run AI diagnosis', exact: true })).toBeDisabled();
  await expect(page.getByText('Configuration required', { exact: true })).toBeVisible();
  await expect(page.locator('.studio-role')).toContainText('Demo Tutor Administrator');
  await expect(page.locator('.studio-proposal')).toHaveCount(0);
});

test('admin renders patches and evaluation returned by the live agent API', async ({ page }) => {
  let revision = 0;
  const source = 'Request clarification from the instructor for this recorded condition.';
  await page.route('**/api/v1/studio/workspace', async route => {
    const workspace = await (await route.fetch()).json();
    workspace.latest_run = null;
    revision = workspace.overview.draft.revision;
    workspace.analysis.mode = 'live';
    workspace.analysis.source_notes = source;
    await route.fulfill({ json: workspace });
  });
  await page.route('**/api/v1/studio/tasks/*/analysis', async route => {
    expect(route.request().postDataJSON().mode).toBe('live');
    expect(route.request().postDataJSON().source_notes).toBe(source);
    await route.fulfill({ json: {
      id: 'live_agent_result', task_id: 'task_001', revision, mode: 'live',
      status: 'ready', stage: 'ready_for_review', source_notes: source,
      proposals: [{ id: 'dynamic_proposal', knowledge_unit_id: 'ku_003', field: 'decision',
        before: null, after: source, source_quote: source, rationale: 'Extracted from current instructor notes.' }],
      evaluation: { passed: true, issues: [], summary: 'Independent agent found direct source support.' },
      error: null, release_id: null,
    } });
  });
  await page.goto('/studio/admin');
  await page.getByRole('button', { name: 'Run AI diagnosis', exact: true }).click();
  await expect(page.locator('.studio-diff')).toContainText(source);
  await expect(page.getByText('Independent agent found direct source support.', { exact: true })).toBeVisible();
  await expect(page.locator('.studio-run-state')).toContainText('AI agent run');
  await expect(page.locator('.studio-proposal')).toHaveCount(1);
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await page.locator('.studio-unit').nth(2).click();
  await expect(page.getByLabel('Extracted proposals for selected unit')).toContainText(source);
  await expect(page.getByLabel('Extracted proposals for selected unit')).toContainText('Extracted from current instructor notes.');
});

test('review saves extracted fields with provenance and audit records without publishing', async ({ page }) => {
  await resetDemo(page.request);
  await page.goto('/studio');
  await page.getByRole('combobox', { name: 'Analysis mode' }).selectOption('rehearsal');
  await page.getByRole('button', { name: 'Run illustrative rehearsal', exact: true }).click();
  await expect(page.getByText('Patch evaluation passed', { exact: true })).toBeVisible();
  const proposed = await page.locator('.studio-diff > div').last().locator('p').textContent();
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await page.locator('.studio-unit').nth(1).click();
  const review = page.getByLabel('Extracted proposals for selected unit');
  await expect(review).toContainText(proposed!);
  await expect(page.getByRole('textbox', { name: 'Exception / limits', exact: true })).not.toHaveValue(proposed!);
  await page.getByRole('textbox', { name: 'AI review note', exact: true }).fill('Reviewed this exact source quote before updating the draft.');
  await page.getByRole('button', { name: /Save .* selected extracted change.* to draft/ }).click();
  await expect(page.getByLabel('Studio status')).toContainText('Reviewed extracted fields saved to draft');
  await expect(page.getByRole('textbox', { name: 'Exception / limits', exact: true })).toHaveValue(proposed!);
  await expect(page.getByText('Version 1', { exact: true })).toBeVisible();
  await expect(page.locator('.studio-field-provenance').last()).toContainText('Illustrative source');
  await page.getByRole('button', { name: 'Publication audit', exact: true }).click();
  const history = page.getByLabel('Diagnosis history');
  await history.locator('.studio-history-run > summary').first().click();
  await expect(history).toContainText('applied');
  await expect(history).toContainText(proposed!);
  await expect(history).toContainText('Authored rehearsal: source checks passed. Expert review required.');
  await expect(page.getByRole('cell', { name: 'analysis saved to draft', exact: true })).toBeVisible();
  await expect(page.getByRole('table')).toContainText('Reviewed this exact source quote before updating the draft.');
  await page.screenshot({ path: 'test-results/extracted-review-audit.png', fullPage: true });
});

test('one diagnosis action proposes evaluated patches; approval updates apprentice course and viva without an admin grant', async ({ page, context }) => {
  await resetDemo(page.request);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const apprentice = await context.newPage();
  await apprentice.goto('/');
  await expect(apprentice.getByText('0 of 3 stages complete', { exact: true })).toBeVisible();
  await page.goto('/studio');
  await page.getByRole('combobox', { name: 'Analysis mode' }).selectOption('rehearsal');
  await page.getByRole('button', { name: 'Run illustrative rehearsal', exact: true }).click();
  await expect(page.getByText('Patch evaluation passed', { exact: true })).toBeVisible();
  const proposed = await page.locator('.studio-diff > div').last().locator('p').textContent();
  expect(proposed).toBeTruthy();
  await expect(page.getByRole('button', { name: 'Approve & publish changes', exact: true })).toBeDisabled();
  await expect(page.getByText('Version 1', { exact: true })).toBeVisible();
  await page.getByRole('checkbox', { name: /Keep .* unanswered expert prompts/ }).check();
  const source = page.getByRole('textbox', { name: 'Expert source notes', exact: true });
  const originalNotes = await source.inputValue();
  await source.fill(originalNotes + '\nChanged since diagnosis.');
  await expect(page.getByRole('button', { name: 'Approve & publish changes', exact: true })).toBeDisabled();
  await source.fill(originalNotes);
  await page.getByRole('textbox', { name: 'Publication note', exact: true }).fill('Reviewed the proposed source-supported guidance.');
  await expect(page.getByRole('button', { name: 'Approve & publish changes', exact: true })).toBeEnabled();
  await page.screenshot({ path: 'test-results/diagnosis-proposals.png', fullPage: true });
  await page.getByRole('button', { name: 'Approve & publish changes', exact: true }).click();
  await expect(page.getByLabel('Studio status')).toContainText('Changes published');
  await expect(page.getByText('Version 2', { exact: true })).toBeVisible();
  await apprentice.bringToFront();
  await expect(apprentice.getByRole('heading', { name: 'Course content', level: 1, exact: true })).toBeVisible();
  await expect(apprentice.getByText(proposed!, { exact: false })).toBeVisible();
  await apprentice.getByRole('button', { name: 'Mark section complete', exact: true }).click();
  const modules = apprentice.getByRole('navigation', { name: 'Course modules' });
  await modules.getByRole('button', { name: 'Simulation playground', exact: true }).click();
  await apprentice.getByRole('button', { name: 'Mark section complete', exact: true }).click();
  await modules.getByRole('button', { name: 'Virtual interview', exact: true }).click();
  await apprentice.getByRole('button', { name: 'Start virtual interview', exact: true }).click();
  await apprentice.getByText('Review approved course evidence', { exact: true }).click();
  await expect(apprentice.locator('.learning-script-source')).toContainText(proposed!);
  for (const [index, choice] of ['b', 'b', 'c'].entries()) {
    await expect(apprentice.getByText(`QUESTION ${index + 1}`, { exact: true })).toBeVisible();
    await apprentice.locator(`input[type="radio"][value="${choice}"]`).check();
    await apprentice.getByRole('button', { name: 'Submit response', exact: true }).click();
  }
  await expect(apprentice.getByText('6 / 6', { exact: true })).toBeVisible();
  const download = apprentice.waitForEvent('download');
  await apprentice.getByRole('button', { name: 'Download evaluation report', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('takumi-learning-report.md');
  await page.bringToFront();
  await page.getByRole('button', { name: 'Publication audit', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'analysis approved published', exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/diagnosis-audit.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('a clarification response explicitly updates its selected tacit field', async ({ page }) => {
  await resetDemo(page.request);
  await page.goto('/studio');
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await page.locator('.studio-unit').nth(1).click();
  const clarification = page.locator('.studio-clarification').first();
  await clarification.getByRole('textbox', { name: 'Clarification answer' }).fill('Keep the observation pending an instructor review.');
  await clarification.getByRole('combobox', { name: 'Clarification target field' }).selectOption('decision');
  await clarification.getByRole('button', { name: 'Record expert response' }).click();
  await expect(page.getByRole('textbox', { name: 'Decision', exact: true })).toHaveValue('Keep the observation pending an instructor review.');
  await expect(page.getByLabel('Studio status')).toContainText('Expert response recorded');
});

test('Expert reset requires confirmation and leaves all three panels empty after reload', async ({ page }) => {
  await resetDemo(page.request);
  await page.goto('/studio');
  await page.getByRole('combobox', { name: 'Analysis mode' }).selectOption('rehearsal');
  await page.getByRole('button', { name: 'Run illustrative rehearsal', exact: true }).click();
  await expect(page.getByText('Patch evaluation passed', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reset Expert data', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Reset all Expert panel data?' });
  await expect(dialog).toContainText('All published releases');
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.studio-proposal')).toHaveCount(1);
  await expect(page.getByText('Version 1', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await page.getByRole('textbox', { name: 'Action', exact: true }).fill('Unsaved edit to discard on reset.');
  await page.getByRole('button', { name: 'Reset Expert data', exact: true }).click();
  await dialog.getByRole('button', { name: 'Reset all data', exact: true }).click();
  await expect(page.getByLabel('Studio status')).toContainText('Expert panel data reset');
  await expect(page.getByRole('textbox', { name: 'Course script', exact: true })).toHaveValue('');
  await expect(page.locator('.studio-proposal')).toHaveCount(0);
  await expect(page.getByText('Unpublished', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Course script', exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await expect(page.locator('.studio-unit')).toHaveCount(0);
  await expect(page.getByText('No knowledge units yet.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Publication audit', exact: true }).click();
  await expect(page.getByText('No diagnosis runs recorded for this task.', { exact: true })).toBeVisible();
  await expect(page.getByText('No workflow events recorded for this task.', { exact: true })).toBeVisible();
  await expect(page.getByText('No release published.', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/expert-reset-empty.png', fullPage: true });
});

test('course source UI uses uploaded video and script automatically and includes review notes on request (mocked agents and media)', async ({ page }) => {
  await resetDemo(page.request);
  const script = 'Record the visible condition before making a decision.';
  const notes = 'Ask the expert to explain the reason for the pause.';
  let uploadedVideo: null | { id: string; filename: string; duration_ms: number; sha256: string } = null;
  let hashes = { with_review_notes: '', without_review_notes: '' };
  let revision = 2;
  let calls = 0;
  await page.route('**/api/v1/tasks/*/media', async route => {
    expect(route.request().headers()['content-type']).toContain('multipart/form-data');
    expect(route.request().postDataBuffer()?.toString()).toContain('course.mp4');
    uploadedVideo = { id: 'uploaded_course_video', filename: 'course.mp4', duration_ms: 3000, sha256: 'test-video-hash' };
    await route.fulfill({ json: { media_id: uploadedVideo.id } });
  });
  await page.route('**/api/v1/studio/workspace', async route => {
    const workspace = await (await route.fetch()).json();
    workspace.analysis.mode = 'live';
    workspace.analysis.media_upload_enabled = true;
    workspace.analysis.course_content.video = uploadedVideo;
    workspace.analysis.course_content.available ||= !!uploadedVideo;
    hashes = workspace.analysis.course_source_hashes;
    revision = workspace.overview.draft.revision;
    await route.fulfill({ json: workspace });
  });
  await page.route('**/api/v1/studio/tasks/*/analysis', async route => {
    const request = route.request().postDataJSON();
    expect(request.use_course_content).toBe(true);
    expect(request.source_notes).toBeUndefined();
    calls++;
    await route.fulfill({ json: {
      id: `course_extraction_${calls}`, task_id: 'task_001', revision, mode: 'live',
      status: 'ready', stage: 'ready_for_review', model: 'test-multimodal-agent',
      source_notes: `${script}\n${request.include_review_notes ? notes : ''}`,
      proposals: [{ id: 'course_action', knowledge_unit_id: 'extracted_course_unit', field: 'action',
        before: null, after: script, source_quote: script, rationale: 'Extracted from the saved course script.',
        video_evidence: { media_id: uploadedVideo!.id, start_ms: 100, end_ms: 800, modality: 'visual' } }],
      evaluation: { passed: true, issues: [], summary: request.include_review_notes ? 'Video, script and expert notes reviewed.' : 'Video and script reviewed; expert notes excluded.', replace_draft: true,
        source_manifest: { input_hash: request.include_review_notes ? hashes.with_review_notes : hashes.without_review_notes, include_review_notes: request.include_review_notes, video: uploadedVideo, script_filename: 'course-script.txt' } },
      error: null, release_id: null,
    } });
  });
  await page.goto('/studio');
  await page.getByLabel('Upload course video', { exact: true }).setInputFiles({ name: 'course.mp4', mimeType: 'video/mp4', buffer: Buffer.from('mocked-media-transport') });
  await expect(page.getByText('course.mp4 · 3.0 seconds', { exact: true })).toBeVisible();
  await page.getByLabel('Upload course script', { exact: true }).setInputFiles({ name: 'course-script.txt', mimeType: 'text/plain', buffer: Buffer.from(script) });
  await expect(page.getByText('Saved script: course-script.txt', { exact: true })).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Use uploaded course video and script automatically' })).toBeChecked();
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await page.getByRole('textbox', { name: 'Expert review notes', exact: true }).fill(notes);
  await page.getByRole('button', { name: 'Save expert notes', exact: true }).click();
  await expect(page.getByLabel('Studio status')).toContainText('Expert notes saved');
  await page.getByRole('button', { name: 'Review course extraction options', exact: true }).click();
  await page.getByRole('button', { name: 'Run AI diagnosis', exact: true }).click();
  await expect(page.getByText('Video, script and expert notes reviewed.', { exact: true })).toBeVisible();
  await expect(page.locator('.studio-proposal')).toContainText('Video evidence: 0.1');
  await page.getByRole('button', { name: 'Expert review', exact: true }).click();
  await expect(page.locator('.studio-unit')).toHaveCount(1);
  await expect(page.getByRole('textbox', { name: 'Action', exact: true })).toHaveValue(script);
  await expect(page.getByRole('textbox', { name: 'Action', exact: true })).not.toBeEditable();
  await expect(page.getByRole('textbox', { name: 'Expert review notes', exact: true })).toHaveValue(notes);
  await page.getByRole('textbox', { name: 'AI review note', exact: true }).fill('Checked the sources.');
  const save = page.getByRole('button', { name: /Save .* selected extracted change.* to draft/ });
  await expect(save).toBeEnabled();
  await page.screenshot({ path: 'test-results/course-extraction-review.png', fullPage: true });
  await page.getByRole('checkbox', { name: 'Include saved expert review notes in course extraction' }).uncheck();
  await expect(save).toBeDisabled();
  await page.getByRole('button', { name: 'Review course extraction options', exact: true }).click();
  await page.getByRole('button', { name: 'Run AI diagnosis', exact: true }).click();
  await expect(page.getByText('Video and script reviewed; expert notes excluded.', { exact: true })).toBeVisible();
  expect(calls).toBe(2);
});
