import { test, expect } from '@playwright/test';
import { mockLearning } from './learning-fixtures';

test('failed reset preserves learner record and scoped browser storage', async ({ page }) => {
  await mockLearning(page);
  await page.route('**/api/v1/learning/reset', route => route.fulfill({ status: 503, json: { error: { code: 'SERVICE_UNAVAILABLE', message: 'Reset could not be saved. Retry.' } } }));
  await page.goto('/');
  await expect(page.getByText('1 of 3 stages complete', { exact: true })).toBeVisible();
  await page.evaluate(() => { localStorage.setItem('takumi-course-attempt:preserve', 'test'); localStorage.setItem('unrelated-attempt', 'keep'); });
  await page.getByRole('button', { name: 'Reset all student knowledge', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm reset', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Reset could not be saved');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByText('1 of 3 stages complete', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('takumi-course-attempt:preserve'))).toBe('test');
  await page.reload();
  await expect(page.getByText('1 of 3 stages complete', { exact: true })).toBeVisible();
});

test('successful reset clears only app attempt keys and stays cleared on reload', async ({ page }) => {
  await mockLearning(page);
  await page.goto('/');
  await expect(page.getByText('1 of 3 stages complete', { exact: true })).toBeVisible();
  await page.evaluate(() => { localStorage.setItem('takumi-course-attempt:clear', 'test'); localStorage.setItem('unrelated-attempt', 'keep'); });
  await page.getByRole('button', { name: 'Reset all student knowledge', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm reset', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.getByText('0 of 3 stages complete', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('takumi-course-attempt:clear'))).toBeNull();
  expect(await page.evaluate(() => localStorage.getItem('unrelated-attempt'))).toBe('keep');
  await page.reload();
  await expect(page.getByText('0 of 3 stages complete', { exact: true })).toBeVisible();
});
