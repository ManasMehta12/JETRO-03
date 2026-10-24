import { test, expect } from '@playwright/test';
import { mockLearning } from './learning-fixtures';

test('reset student knowledge resets progress, locks modules, and clears attempt records', async ({ page }) => {
  await mockLearning(page, false);
  await page.goto('/');

  const modules = page.getByRole('navigation', { name: 'Course modules' });
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeDisabled();

  // 1. Manually complete course to unlock playground
  await modules.getByRole('button', { name: 'Course content', exact: true }).click();
  await page.getByRole('button', { name: 'Mark section complete', exact: true }).click();
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeEnabled();

  // 2. Open confirmation modal and cancel
  const resetBtn = page.getByRole('button', { name: 'Reset all student knowledge' });
  await expect(resetBtn).toBeVisible();
  await resetBtn.click();

  const modal = page.locator('.learning-modal-dialog');
  await expect(modal).toBeVisible();
  await expect(modal.getByRole('heading', { name: 'Reset all student knowledge?' })).toBeVisible();
  await modal.getByRole('button', { name: 'Cancel' }).click();
  await expect(modal).toBeHidden();
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeEnabled();

  // 3. Confirm reset
  await resetBtn.click();
  await expect(modal).toBeVisible();
  await modal.getByRole('button', { name: 'Confirm reset' }).click();
  await expect(modal).toBeHidden();

  // 4. Verify everything returned to baseline
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeDisabled();
  await expect(modules.getByRole('button', { name: 'Virtual interview', exact: true })).toBeDisabled();
  await expect(page.getByText('0 of 3 stages complete', { exact: true })).toBeVisible();
  await expect(page.getByRole('contentinfo', { name: 'Learning status' })).toContainText('Your watch progress, simulation result and interview have been reset.');
});
