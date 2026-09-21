import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, timeout: 90000,
  expect: { timeout: 15000 },
  use: { baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173', browserName: 'chromium', headless: true,
    viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['json', { outputFile: '../artifacts/test-results/browser.json' }]],
});
