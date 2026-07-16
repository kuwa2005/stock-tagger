import { defineConfig, devices } from '@playwright/test';

/**
 * stock-tagger WebUI E2E（Docker テスト環境向け）
 * 前提: docker compose up -d で http://localhost:7861 が起動済み
 */
const baseURL = process.env.BASE_URL || 'http://localhost:7861';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  // スモークは短い。GPU 推論テストは describe 側で延長する
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
