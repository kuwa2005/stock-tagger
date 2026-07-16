import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Stock Image Auto Tagger WebUI', () => {
  test('health check returns ok', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.ok()).toBeTruthy();
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  test('home page renders', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Stock Image Auto Tagger' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Manage blocked keywords' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Clear' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Generate tags' })).toHaveCount(0);
    await expect(page.locator('#preview')).toHaveCount(0);

    const actions = page.locator('.topActions');
    await expect(actions).toBeVisible();
    const boxDrop = await page.locator('#dropZone').boundingBox();
    const boxActions = await actions.boundingBox();
    expect(boxDrop && boxActions).toBeTruthy();
    expect(boxActions!.y).toBeGreaterThan(boxDrop!.y);
  });

  test('choosing files starts processing immediately', async ({ page }) => {
    await page.goto('/');
    const fixture = path.join(__dirname, 'fixtures', 'sample.jpg');
    await page.locator('#fileInput').setInputFiles(fixture);
    await expect(page.locator('#processingBar.show, .resultItem').first()).toBeVisible({ timeout: 60_000 });
    // Progress UI exists (text and bar); may finish quickly on warm GPU
    await expect(page.locator('#processingText, .resultItem').first()).toBeVisible();
  });

  test('blocked keywords can be added and removed', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.reload();

    await page.getByRole('button', { name: 'Manage blocked keywords' }).click();
    await expect(page.getByRole('heading', { name: 'Blocked keywords' })).toBeVisible();

    await page.locator('#ngInput').fill('watermark');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page.locator('#ngList')).toContainText('watermark');

    await page.locator('#ngList .removeBtn').click();
    await expect(page.locator('#ngList li')).toHaveCount(0);
  });
});
