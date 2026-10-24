import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

async function inspectAll(page: Page) {
  for (const name of ['Base plate', 'Bearing housing', 'Drive shaft', 'Ball bearing']) {
    await page.getByRole('button', { name: `Select ${name}`, exact: true }).click();
    await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Inspection recorded', exact: true })).toBeDisabled();
  }
  await expect(page.getByText('4 / 4 inspected', { exact: true })).toBeVisible();
}

async function answerQuestions(page: Page) {
  await page.getByRole('tab', { name: 'Knowledge check', exact: true }).click();
  for (const answer of ['Use the explicit inspection action', 'The authored seating step is complete; verification is still required', 'Stop release and escalate the unresolved evidence']) {
    const button = page.getByRole('button', { name: answer, exact: false });
    if (await button.isEnabled()) await button.click();
  }
  await page.getByRole('tab', { name: 'Practice', exact: true }).click();
}

async function assembleWorkshop(page: Page) {
  await page.getByRole('button', { name: 'Pick up Base plate', exact: true }).click();
  await page.getByRole('button', { name: 'Mount base', exact: true }).click();
  await page.getByRole('button', { name: 'Pick up Bearing housing', exact: true }).click();
  await page.getByRole('button', { name: 'Mount housing', exact: true }).click();
  await page.getByRole('button', { name: 'Use Alignment jig', exact: true }).click();
  await page.getByRole('button', { name: 'Nudge left', exact: true }).click({ clickCount: 1 });
  await page.getByRole('button', { name: 'Nudge left', exact: true }).click({ clickCount: 1 });
  await page.getByRole('button', { name: 'Pick up Drive shaft', exact: true }).click();
  await page.getByRole('button', { name: 'Insert shaft', exact: true }).click();
  await page.getByRole('button', { name: 'Use Bearing sleeve', exact: true }).click();
  await page.getByRole('button', { name: 'Pick up Ball bearing', exact: true }).click();
  await page.getByRole('button', { name: 'Place bearing', exact: true }).click();
  for (let step = 0; step < 3; step++) await page.getByRole('button', { name: 'Press bearing', exact: true }).click();
  await page.getByRole('button', { name: 'Use Hex key', exact: true }).click();
  for (const bolt of ['A', 'C', 'B', 'D']) await page.getByRole('button', { name: `Tighten bolt ${bolt}`, exact: true }).click();
  await page.getByRole('button', { name: 'Use Handwheel', exact: true }).click();
  for (let turn = 0; turn < 3; turn++) await page.getByRole('button', { name: 'Turn shaft', exact: true }).click();
  await page.getByRole('button', { name: 'Verify assembly', exact: true }).click();
}

async function completeChecks(page: Page, withQuiz = true) {
  await inspectAll(page);
  await page.getByRole('button', { name: 'Request observation', exact: true }).click();
  await assembleWorkshop(page);
  if (withQuiz) await answerQuestions(page);
}

test.beforeEach(async ({ page }) => { await page.goto('/'); });

test('standard flow records all checks, correct quiz answers and supported release', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Bearing assembly' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Request observation', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toBeDisabled();
  await page.getByRole('tab', { name: 'Knowledge check', exact: true }).click();
  for (const answer of ['Use the explicit inspection action', 'The authored seating step is complete; verification is still required', 'Stop release and escalate the unresolved evidence']) {
    const button = page.getByRole('button', { name: answer, exact: false });
    await button.click();
    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute('aria-pressed', 'true');
  }
  await expect(page.getByText('Correct reasoning', { exact: true })).toHaveCount(3);
  await page.getByRole('tab', { name: 'Practice', exact: true }).click();
  await completeChecks(page);
  await page.getByRole('button', { name: 'Release assembly', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Assembly released', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Supported release.');
  await expect(page.getByRole('status').getByText('100%', { exact: true })).toHaveCount(3);
  await expect(page.getByText('12 / 12 checkpoints', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toHaveCount(0);
});

test('uncertain fit has fixed unresolved evidence and rewards escalation', async ({ page }) => {
  await page.getByLabel('Scenario', { exact: true }).selectOption('uncertain');
  await page.getByRole('button', { name: 'Start fresh', exact: true }).click();
  await completeChecks(page);
  await expect(page.getByText(/The scripted visual check is inconclusive/).first()).toBeVisible();
  await page.getByRole('button', { name: 'Escalate for review', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review requested', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Supported escalation.');
  await expect(page.getByRole('status').getByText('100%', { exact: true })).toHaveCount(3);
});

test('progress survives reload and reset requires explicit confirmation', async ({ page }) => {
  await page.getByRole('button', { name: 'Select Base plate', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
  await page.reload();
  await expect(page.getByText('1 / 4 inspected', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Select Base plate', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Inspection recorded', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Restart exercise', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByText('1 / 4 inspected', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restart exercise', exact: true }).click();
  await page.getByRole('button', { name: 'Start fresh', exact: true }).click();
  await expect(page.getByText('0 / 4 inspected', { exact: true })).toBeVisible();
  await expect(page.getByText('0 recorded actions', { exact: true })).toBeVisible();
});

test('assessment hides reasoning until the final decision', async ({ page }) => {
  await page.getByLabel('Learning mode', { exact: true }).selectOption('assessment');
  await page.getByRole('button', { name: 'Start fresh', exact: true }).click();
  await expect(page.getByText('WORKSHOP INSIGHT', { exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Knowledge check', exact: true }).click();
  await page.getByRole('button', { name: /Use the explicit inspection action/ }).click();
  await expect(page.getByText('Answer recorded. Feedback appears after your final decision.', { exact: true })).toBeVisible();
  await expect(page.getByText('Correct reasoning', { exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Insights', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reason first. Review after.', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Practice', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toBeDisabled();
  await completeChecks(page);
  await page.getByRole('button', { name: 'Release assembly', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Assembly released', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Knowledge check', exact: true }).click();
  await expect(page.getByText('Correct reasoning', { exact: true })).toHaveCount(3);
  await page.getByRole('tab', { name: 'Insights', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Observe before acting', exact: true })).toBeVisible();
});

test('3D viewport and controls render, and desktop screenshot is captured', async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on('pageerror', error => runtimeErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') runtimeErrors.push(message.text()); });
  await page.reload();
  await expect(page.locator('canvas')).toBeVisible({ timeout: 30_000 });
  const toggle = page.getByRole('button', { name: 'Exploded view', exact: true });
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: 'Reset camera', exact: true }).click();
  await page.getByRole('tab', { name: 'Insights', exact: true }).click();
  await page.getByRole('button', { name: /E-01/ }).click();
  await expect(page.getByRole('dialog')).toContainText('Instructor review pending');
  await page.getByRole('button', { name: 'Close note', exact: true }).click();
  await page.getByRole('tab', { name: 'Practice', exact: true }).click();
  await expect(page.locator('canvas')).toBeVisible();
  await page.screenshot({ path: 'test-results/bearing-assembly-desktop.png', fullPage: true });
  expect(runtimeErrors).toEqual([]);
});

test('mobile retains key controls without horizontal page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: 'Bearing assembly' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Select Ball bearing', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
  await expect(page.getByText('1 / 4 inspected', { exact: true })).toBeVisible();
  await expect(page.locator('canvas')).toBeVisible({ timeout: 30_000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/bearing-assembly-mobile.png', fullPage: true });
});

test('a device without WebGL retains the deterministic inspection workflow', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (...args: Parameters<typeof original>) {
      if (String(args[0]).startsWith('webgl')) return null;
      return original.apply(this, args);
    } as typeof original;
  });
  await page.reload();
  await expect(page.getByRole('img', { name: 'Bearing assembly schematic', exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
  await expect(page.getByText('1 / 4 inspected', { exact: true })).toBeVisible();
});

test('mission completion remains locked until the assembly and knowledge checkpoints are complete', async ({ page }) => {
  await completeChecks(page, false);
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Escalate for review', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toBeDisabled();
  await answerQuestions(page);
  await expect(page.getByRole('button', { name: 'Release assembly', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Release assembly', exact: true }).click();
  await expect(page.getByText('12 / 12 checkpoints', { exact: true })).toBeVisible();
});

test('wrong held part, wrong tool and wrong bolt order do not advance assembly checkpoints', async ({ page }) => {
  await inspectAll(page);
  await page.getByRole('button', { name: 'Request observation', exact: true }).click();
  await page.getByRole('button', { name: 'Pick up Bearing housing', exact: true }).click();
  await page.getByRole('button', { name: 'Mount base', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Pick up the base first.');
  await page.getByRole('button', { name: 'Pick up Base plate', exact: true }).click();
  await page.getByRole('button', { name: 'Mount base', exact: true }).click();
  await page.getByRole('button', { name: 'Pick up Bearing housing', exact: true }).click();
  await page.getByRole('button', { name: 'Mount housing', exact: true }).click();
  await page.getByRole('button', { name: 'Use Hex key', exact: true }).click();
  await page.getByRole('button', { name: 'Nudge left', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Select the alignment jig first.');
  await page.getByRole('button', { name: 'Use Alignment jig', exact: true }).click();
  await page.getByRole('button', { name: 'Nudge left', exact: true }).click();
  await page.reload();
  await page.getByRole('button', { name: 'Nudge left', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Insert shaft', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pick up Drive shaft', exact: true }).click();
  await page.getByRole('button', { name: 'Insert shaft', exact: true }).click();
  await page.getByRole('button', { name: 'Use Bearing sleeve', exact: true }).click();
  await page.getByRole('button', { name: 'Pick up Ball bearing', exact: true }).click();
  await page.getByRole('button', { name: 'Place bearing', exact: true }).click();
  for (let press = 0; press < 3; press++) await page.getByRole('button', { name: 'Press bearing', exact: true }).click();
  await page.getByRole('button', { name: 'Use Hex key', exact: true }).click();
  await page.getByRole('button', { name: 'Bolt B', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Follow the cross sequence: tighten bolt A next.');
  await expect(page.getByRole('button', { name: 'Tighten bolt A', exact: true })).toBeVisible();
});

test('drag placement and scene targets install actual components without duplicate XP', async ({ page }) => {
  await inspectAll(page);
  await page.getByRole('button', { name: 'Request observation', exact: true }).click();
  await expect(page.locator('canvas')).toBeVisible({ timeout: 30_000 });
  // Keep the tray and drop surface visible together before starting a native drag.
  await page.locator('.scene-card').evaluate(element => element.scrollIntoView({ block: 'start' }));
  await page.getByRole('button', { name: 'Pick up Base plate', exact: true }).dragTo(page.locator('.scene-viewport'));
  await expect(page.getByRole('button', { name: 'Pick up Base plate', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Mount housing', exact: true })).toBeVisible();
  await expect(page.getByText('3 / 12 checkpoints', { exact: true })).toBeVisible();
  await expect(page.locator('.mission-xp > strong')).toContainText('150');
  await page.getByRole('button', { name: 'Pick Split housing', exact: true }).click();
  await page.getByRole('button', { name: 'Place Split housing here', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pick up Bearing housing', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Nudge left', exact: true })).toBeVisible();
  await expect(page.getByText('4 / 12 checkpoints', { exact: true })).toBeVisible();
  await expect(page.locator('.mission-xp > strong')).toContainText('200');
  await page.screenshot({ path: 'test-results/bearing-assembly-in-progress.png', fullPage: true });
});

test('workspace navigation, inspection shortcuts and expandable checkpoints stay in sync', async ({ page }) => {
  const navigation = page.getByRole('navigation', { name: 'Workspace' });
  await navigation.getByRole('button', { name: 'Field notes', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Insights', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(navigation.getByRole('button', { name: 'Field notes', exact: true })).toHaveAttribute('aria-current', 'page');
  await navigation.getByRole('button', { name: 'Playground', exact: true }).click();
  await expect(page.getByRole('tabpanel')).toContainText('01. Inspect the components');
  await page.getByRole('button', { name: 'Focus Base plate', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Focus Base plate', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const checklist = page.locator('details.checkpoint-card');
  await expect(checklist).not.toHaveAttribute('open');
  await checklist.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(checklist).toHaveAttribute('open', '');
  await expect(checklist.getByRole('listitem')).toHaveCount(12);
  await page.keyboard.press('Enter');
  await expect(checklist).not.toHaveAttribute('open');
});
