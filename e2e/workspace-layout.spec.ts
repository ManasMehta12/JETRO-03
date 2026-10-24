import { test, expect } from '@playwright/test';
import { mockLearning, openPlayground } from './learning-fixtures';

for (const viewport of [{ width: 1440, height: 900 }, { width: 1366, height: 768 }]) {
  test(`dashboard panels align within ${viewport.width} x ${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mockLearning(page, false);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Your learning workspace' })).toBeVisible();
    const modules = page.getByRole('navigation', { name: 'Course modules' });
    await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeDisabled();
    await expect(modules.getByRole('button', { name: 'Virtual interview', exact: true })).toBeDisabled();
    const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight }));
    expect(dimensions.width).toBeLessThanOrEqual(viewport.width);
    expect(dimensions.height).toBeLessThanOrEqual(viewport.height);
    const bounds = await page.locator('.learning-dashboard > .learning-panel').evaluateAll(items => items.map(item => { const b = item.getBoundingClientRect(); return { y: b.y, height: b.height }; }));
    expect(bounds).toHaveLength(4);
    expect(bounds[0].y).toBe(bounds[1].y);
    expect(bounds[0].height).toBe(bounds[1].height);
    expect(bounds[2].y).toBe(bounds[3].y);
    expect(bounds[2].height).toBe(bounds[3].height);
    await expect(page.getByRole('contentinfo', { name: 'Learning status' })).toBeVisible();
    await page.screenshot({ path: `test-results/dashboard-${viewport.width}.png`, fullPage: true });
  });

  test(`embedded playground uses one header and status at ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await openPlayground(page);
    await expect(page.locator('.learning-header')).toHaveCount(1);
    await expect(page.locator('.playground-embedded > .app-header')).toHaveCount(0);
    await expect(page.locator('.playground-embedded .workspace-status')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Select Ball bearing', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Inspect component', exact: true }).click();
    await expect(page.getByRole('contentinfo', { name: 'Learning status' })).toContainText('The bearing rings are identified.');
    const footerBounds = await page.getByRole('contentinfo', { name: 'Learning status' }).boundingBox();
    for (const selector of ['.scene-card', '.components-card', '.workshop-tray', '.workspace-grid > .learning-card']) {
      const bounds = await page.locator(selector).boundingBox();
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(footerBounds!.y);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    await page.screenshot({ path: `test-results/embedded-playground-${viewport.width}.png`, fullPage: true });
  });
}

test('manual course completion is available in the interface on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockLearning(page, false);
  await page.goto('/');
  const modules = page.getByRole('navigation', { name: 'Course modules' });
  await modules.getByRole('button', { name: 'Course content', exact: true }).click();
  await page.getByRole('button', { name: 'Mark section complete', exact: true }).click();
  await expect(modules.getByRole('button', { name: 'Simulation playground', exact: true })).toBeEnabled();
  await expect(page.getByText('Manually completed', { exact: true })).toBeVisible();
  await expect(page.getByText('0:00 watched / 0:06', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: 'test-results/course-mobile.png', fullPage: true });
});
