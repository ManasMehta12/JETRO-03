import { test, expect } from '@playwright/test';

test('real backend tracks in-page video, manual unlocks and a persisted interview evaluation', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  const modules = page.getByRole('navigation', { name: 'Course modules' });
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeDisabled();
  await expect(modules.getByRole('button', { name: 'Virtual interview', exact: true })).toBeDisabled();
  await modules.getByRole('button', { name: 'Course content', exact: true }).click();
  const video = page.locator('video');
  await expect(video).toBeVisible();
  await video.evaluate(async (element: HTMLVideoElement) => {
    if (element.readyState < 1) await new Promise<void>(resolve => element.addEventListener('loadedmetadata', () => resolve(), { once: true }));
    element.currentTime = 5;
  });
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeLessThan(1);
  await video.evaluate((element: HTMLVideoElement) => element.play());
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeEnabled({ timeout: 25_000 });
  await page.screenshot({ path: 'test-results/course-video-completed.png', fullPage: true });
  await modules.getByRole('button', { name: 'Simulation playground', exact: true }).click();
  await expect(modules.getByRole('button', { name: 'Virtual interview', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Mark section complete', exact: true }).click();
  await expect(modules.getByRole('button', { name: 'Virtual interview', exact: true })).toBeEnabled();
  await page.reload();
  await modules.getByRole('button', { name: 'Virtual interview', exact: true }).click();
  await expect(page.getByText('No simulation attempt was assessed.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Start virtual interview', exact: true }).click();
  for (const answer of ['b', 'b', 'c']) {
    await page.locator(`input[type="radio"][value="${answer}"]`).check();
    await page.getByRole('button', { name: 'Submit response', exact: true }).click();
  }
  await expect(page.getByRole('heading', { name: 'Course evaluation', exact: true })).toBeVisible();
  await expect(page.getByText('6 / 6', { exact: true })).toBeVisible();
  await expect(page.getByText('No simulation result', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/course-evaluation.png', fullPage: true });
  await page.reload();
  await expect(page.getByText('3 of 3 stages complete', { exact: true })).toBeVisible();
  await modules.getByRole('button', { name: 'Virtual interview', exact: true }).click();
  await expect(page.getByText('6 / 6', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('manual course completion can unlock the next section without faking a watch record', async ({ page }) => {
  // The endpoint is also covered with an unconfigured recording in backend tests.
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Your learning workspace' })).toBeVisible();
  const credentials = await page.evaluate(() => JSON.parse(sessionStorage.getItem('takumi-learning-session') || '{}'));
  const response = await page.request.post('/api/v1/learning/complete', {
    headers: { Authorization: `Bearer ${credentials.access_token}` }, data: { stage: 'course' },
  });
  expect(response.ok()).toBe(true);
  const progress = await response.json();
  expect(progress.manual_completion.course).toBeTruthy();
  expect(progress.playground_unlocked).toBe(true);
  await page.reload();
  await page.getByRole('navigation', { name: 'Course modules' }).getByRole('button', { name: 'Course content', exact: true }).click();
  await expect(page.getByText('Manually completed', { exact: true })).toBeVisible();
});
