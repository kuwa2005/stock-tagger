import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * GPU inference E2E.
 * First run may take several minutes for model load.
 * Run: npm run test:gpu
 */
const FIXTURE = path.join(__dirname, 'fixtures', 'sample.jpg');
const FIXTURE_B = path.join(__dirname, 'fixtures', 'sample-b.jpg');

/** Allow cold start (Florence-2 + RAM++) */
const INFERENCE_TIMEOUT_MS = 10 * 60 * 1000;

test.describe('Tag generation (GPU inference) @gpu', () => {
  test.describe.configure({ timeout: INFERENCE_TIMEOUT_MS });

  test('API: POST /tag returns title / caption / keywords', async ({ request }) => {
    const res = await request.post('/tag', {
      multipart: {
        files: {
          name: 'sample.jpg',
          mimeType: 'image/jpeg',
          buffer: fs.readFileSync(FIXTURE),
        },
      },
      timeout: INFERENCE_TIMEOUT_MS,
    });

    expect(res.ok(), `status=${res.status()} body=${await res.text().catch(() => '')}`).toBeTruthy();
    const data = await res.json();

    expect(data.title, 'title is empty').toBeTruthy();
    expect(String(data.title).trim().length).toBeGreaterThan(0);

    expect(data.caption, 'caption is empty').toBeTruthy();
    expect(String(data.caption).trim().length).toBeGreaterThan(0);

    expect(Array.isArray(data.keywords), 'keywords is not an array').toBeTruthy();
    expect(data.keywords.length, 'keywords is empty').toBeGreaterThan(0);
    for (const kw of data.keywords) {
      expect(String(kw).trim().length).toBeGreaterThan(0);
    }
  });

  test('WebUI: file upload shows results and supports Clear / blocking', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('stock-tagger-ng-keywords'));
    await page.locator('#fileInput').setInputFiles(FIXTURE);

    const resultItem = page.locator('.resultItem').first();
    await expect(resultItem).toBeVisible({ timeout: INFERENCE_TIMEOUT_MS });
    await expect(page.getByRole('button', { name: 'Clear' })).toBeEnabled();

    await expect(resultItem.getByText('Title:')).toBeVisible();
    const titleText = await resultItem.locator('p').filter({ hasText: 'Title:' }).innerText();
    expect(titleText.replace('Title:', '').trim().length, 'title is empty').toBeGreaterThan(0);

    await expect(resultItem.getByText('Caption:')).toBeVisible();
    const captionText = await resultItem.locator('p').filter({ hasText: 'Caption:' }).innerText();
    expect(captionText.replace('Caption:', '').trim().length, 'caption is empty').toBeGreaterThan(0);

    await expect(resultItem.locator('.keyword').first()).toBeVisible();
    await expect(page.locator('#csvLink')).toBeVisible();
    await expect(page.locator('#zipLink')).toBeVisible();

    // Prefer File System Access save dialog; fall back to download event
    const outPath = path.join('/tmp', `stock-tagger-export-test-${Date.now()}.zip`);
    const downloadPromise = page.waitForEvent('download', { timeout: 60_000 }).catch(() => null);
    const chooserPromise = page.waitForEvent('filechooser', { timeout: 5_000 }).catch(() => null);
    await page.locator('#zipLink').click();
    const chooser = await chooserPromise;
    if (chooser) {
      await chooser.setFiles(outPath);
      await expect.poll(async () => {
        try {
          return fs.statSync(outPath).size;
        } catch {
          return 0;
        }
      }, { timeout: 60_000 }).toBeGreaterThan(100);
    } else {
      const download = await downloadPromise;
      expect(download, 'expected download or save dialog').toBeTruthy();
      expect(download!.suggestedFilename()).toMatch(/^stock-tagger-export_\d{14}\.zip$/i);
    }

    await page.locator('.resultThumb img.thumb').first().click();
    await expect(page.locator('#lightbox')).toHaveClass(/show/);
    await expect(page.locator('#lightboxTitle')).not.toBeEmpty();
    await expect(page.locator('#lightboxCaptionText')).not.toBeEmpty();
    await expect(page.locator('#lightboxKeywords .keyword').first()).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#lightbox')).not.toHaveClass(/show/);

    const firstKeyword = resultItem.locator('.keyword').first();
    const blockedText = (await firstKeyword.getAttribute('data-keyword')) || (await firstKeyword.innerText()).trim().toLowerCase();
    await page.locator('label.toggleRow').click();
    await expect(page.locator('#blockModeBanner')).toHaveClass(/show/);
    await firstKeyword.click();
    await expect(firstKeyword).toHaveClass(/pending-block/);
    await page.locator('#blockApplyBtn').click();
    await expect(resultItem.locator(`.keyword[data-keyword="${blockedText}"]`)).toHaveCount(0);

    await page.getByRole('button', { name: 'Clear' }).click();
    await expect(page.locator('.resultItem')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Clear' })).toBeDisabled();
  });

  test('WebUI: additional upload prepends new results', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('stock-tagger-ng-keywords'));

    await page.locator('#fileInput').setInputFiles(FIXTURE);
    await expect(page.locator('.resultItem')).toHaveCount(1, { timeout: INFERENCE_TIMEOUT_MS });
    const firstName = await page.locator('.resultItem').first().locator('h3').innerText();

    await page.locator('#fileInput').setInputFiles(FIXTURE_B);
    await expect(page.locator('.resultItem')).toHaveCount(2, { timeout: INFERENCE_TIMEOUT_MS });
    const topName = await page.locator('.resultItem').first().locator('h3').innerText();
    expect(topName).toContain('sample-b');
    expect(await page.locator('.resultItem').nth(1).locator('h3').innerText()).toBe(firstName);
  });

  test('WebUI: Blocking mode marks matching keywords across images', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('stock-tagger-ng-keywords'));
    await page.locator('#fileInput').setInputFiles([FIXTURE, FIXTURE_B]);

    const items = page.locator('.resultItem');
    await expect(items).toHaveCount(2, { timeout: INFERENCE_TIMEOUT_MS });

    const key = await items.nth(0).locator('.keyword').first().getAttribute('data-keyword');
    expect(key).toBeTruthy();

    await page.locator('label.toggleRow').click();
    await items.nth(0).locator(`.keyword[data-keyword="${key}"]`).click();

    const marked = items.locator(`.keyword[data-keyword="${key}"].pending-block`);
    const total = items.locator(`.keyword[data-keyword="${key}"]`);
    await expect(marked).toHaveCount(await total.count());
    expect(await marked.count()).toBeGreaterThan(0);
  });

  test('WebUI: lightbox shows meta and navigates between images', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.removeItem('stock-tagger-ng-keywords'));
    await page.locator('#fileInput').setInputFiles([FIXTURE, FIXTURE_B]);
    await expect(page.locator('.resultItem')).toHaveCount(2, { timeout: INFERENCE_TIMEOUT_MS });

    await page.locator('.resultThumb img.thumb').nth(0).click();
    await expect(page.locator('#lightbox')).toHaveClass(/show/);
    await expect(page.locator('#lightboxCounter')).toHaveText('1 / 2');
    const firstFile = await page.locator('#lightboxFilename').innerText();

    await page.locator('#lightboxNext').hover();
    await page.locator('#lightboxNext').click({ force: true });
    await expect(page.locator('#lightboxCounter')).toHaveText('2 / 2');
    const secondFile = await page.locator('#lightboxFilename').innerText();
    expect(secondFile).not.toBe(firstFile);
    await expect(page.locator('#lightboxTitle')).not.toBeEmpty();
    await expect(page.locator('#lightboxKeywords .keyword').first()).toBeVisible();

    await page.keyboard.press('ArrowLeft');
    await expect(page.locator('#lightboxCounter')).toHaveText('1 / 2');
    await expect(page.locator('#lightboxFilename')).toHaveText(firstFile);
  });
});
