import { test, expect } from '@playwright/test';

for (const viewport of [{ width: 1440, height: 900 }, { width: 1366, height: 768 }]) {
  test(`desktop workspace stays within ${viewport.width} × ${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/');
    const navigation = page.getByRole('navigation', { name: 'Workspace' });
    await expect(navigation).toBeVisible();
    const navBounds = await navigation.boundingBox();
    expect(navBounds!.y).toBeLessThan(80);
    const dimensions = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    expect(dimensions.width).toBeLessThanOrEqual(viewport.width);
    expect(dimensions.height).toBeLessThanOrEqual(viewport.height);
    const scenario = await page.locator('.scenario-bar').boundingBox();
    const progress = await page.locator('.mission-banner').boundingBox();
    expect(Math.abs(scenario!.y - progress!.y)).toBeLessThan(2);
    expect(scenario!.width).toBeLessThan(viewport.width * 0.65);
    expect(progress!.width).toBeLessThan(viewport.width * 0.5);
    const status = page.getByRole('region', { name: 'Workspace status and messages' });
    await expect(status.getByText('Your progress is saved locally', { exact: true })).toBeVisible();
    await expect(status.getByText(/Authored practice simulation/)).toBeVisible();
    const workspaceBounds = await page.locator('.workspace-grid').boundingBox();
    const statusBounds = await status.boundingBox();
    expect(statusBounds!.y).toBeGreaterThanOrEqual(workspaceBounds!.y + workspaceBounds!.height);
    expect(Math.abs(statusBounds!.x - workspaceBounds!.x)).toBeLessThan(2);
    expect(Math.abs(statusBounds!.width - workspaceBounds!.width)).toBeLessThan(2);
    for (const selector of ['.scene-card', '.components-card', '.workshop-tray', '.learning-card']) {
      const bounds = await page.locator(selector).boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.y).toBeGreaterThanOrEqual(0);
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
    }
    await navigation.getByRole('button', { name: 'Knowledge check', exact: true }).click();
    const panel = page.getByRole('tabpanel');
    expect(await panel.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
    await page.getByRole('button', { name: /Stop release and escalate the unresolved evidence/ }).click();
    await expect(page.getByText('Correct reasoning', { exact: true })).toBeVisible();
    await expect(status.getByRole('status')).toBeVisible();
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
  });
}
