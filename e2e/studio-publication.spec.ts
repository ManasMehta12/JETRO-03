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
