import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E config for Inspectra UI.
 *
 * Prerequisites:
 *   - Backend: http://localhost:8765
 *   - Frontend dev server: http://localhost:5173
 *
 * Run:
 *   npm run test:e2e          # headless
 *   npm run test:e2e:ui       # Playwright UI mode
 */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',

  /* Max time one test can run */
  timeout: 30_000,

  /* Fail fast on first failure in CI; run all locally */
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,

  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: BASE_URL,
    /* Keep screenshots/traces on failure */
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    video: 'off',
    /* Generous navigation timeout — dev server can be slow */
    navigationTimeout: 15_000,
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Start the Vite dev server automatically if not already running */
  webServer: {
    command: 'npm run start',
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
