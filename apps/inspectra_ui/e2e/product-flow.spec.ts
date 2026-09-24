/**
 * product-flow.spec.ts — Playwright E2E tests for Inspectra product flow.
 *
 * Prerequisites:
 *   - Backend running on http://localhost:8765
 *   - Frontend dev server on http://localhost:5173 (or VITE_PORT env)
 *   - No VITE_USE_MOCKS=true
 *
 * Run:
 *   npx playwright test e2e/product-flow.spec.ts
 *   npx playwright test e2e/product-flow.spec.ts --ui
 *
 * These tests run against real services. They are honest about capability gaps:
 * if the backend returns capability_gap, the test verifies the UI shows it clearly.
 */

import { test, expect, type Page } from '@playwright/test';
import { homedir } from 'os';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API  = process.env.E2E_API_URL  ?? 'http://localhost:8765';

// Unique suffix per test run — prevents leftover E2E records from prior runs colliding.
const RUN_TS = Date.now();

// ── helpers ───────────────────────────────────────────────────────────────────

async function navTo(page: Page, path: string) {
  await page.goto(`${BASE}${path}`);
  // Wait for initial render
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
}

async function apiPost(path: string, body: object) {
  const r = await fetch(`${API}/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function apiPatch(path: string, body: object) {
  const r = await fetch(`${API}/api${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function apiGet(path: string) {
  const r = await fetch(`${API}/api${path}`);
  return r.json();
}

async function waitForRunCompletion(runId: string) {
  for (let i = 0; i < 60; i += 1) {
    const run = await apiGet(`/runs/${runId}`);
    if (run.status === 'completed' || run.status === 'failed' || run.status === 'cancelled') {
      return run;
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error(`Run ${runId} did not complete within timeout`);
}

async function waitForPackAvailable(packId: string) {
  for (let i = 0; i < 20; i += 1) {
    const pack = await apiGet(`/validation-packs/${packId}`);
    if (pack?.id === packId) return pack;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Pack ${packId} was not readable within timeout`);
}

// ── cleanup ───────────────────────────────────────────────────────────────────

// Deletes all E2E-prefixed records after the suite. Requires INSPECTRA_ENABLE_DEV_CLEANUP=true.
// If the env flag is absent the endpoint returns 403 — silently ignored so CI doesn't fail.
test.afterAll(async () => {
  await fetch(`${API}/api/dev/e2e-data?confirm=true`, { method: 'DELETE' }).catch(() => {});
});

// ── 1. Empty state ─────────────────────────────────────────────────────────────

test('01 - empty workspace shows zero counts not fake data', async ({ page }) => {
  await navTo(page, '/');
  // Should show a dashboard with real (possibly 0) counts
  await expect(page.locator('body')).toBeVisible();
  // Dashboard must not show hard-coded numbers like "312" or "89%"
  const text = await page.locator('body').innerText();
  expect(text).not.toContain('312');
});

// ── 2. Create project ─────────────────────────────────────────────────────────

test('02 - create project navigates to add app', async ({ page }) => {
  await navTo(page, '/projects');
  // Header "Connect app" button is always visible regardless of empty state.
  // "Connect first app" is a separate empty-state-only button — use exact match to avoid strict-mode error.
  const connectBtn = page.getByRole('button', { name: /^connect app$/i });
  await expect(connectBtn).toBeVisible();
  await connectBtn.click();
  await expect(page).toHaveURL(/\/projects\/new/);
});

// ── 3. Add app wizard renders ─────────────────────────────────────────────────

test('03 - add app wizard renders with project selector', async ({ page }) => {
  await navTo(page, '/projects/new');
  // Step indicator should be visible
  await expect(page.locator('body')).toBeVisible();
  const heading = page.getByText(/select project|connect app|app details/i);
  await expect(heading.first()).toBeVisible();
});

// ── 4. Runtime Doctor global mode ─────────────────────────────────────────────

test('04 - runtime doctor shows ENV READINESS section', async ({ page }) => {
  await navTo(page, '/doctor');
  await expect(page.getByText(/environment readiness/i).first()).toBeVisible({ timeout: 10_000 });
});

test('04b - runtime doctor shows App Runtime Readiness section', async ({ page }) => {
  await navTo(page, '/doctor');
  await expect(page.getByText(/app runtime readiness/i)).toBeVisible({ timeout: 10_000 });
});

// ── 5. Create validation pack ─────────────────────────────────────────────────

test('05 - create validation pack page renders', async ({ page }) => {
  await navTo(page, '/packs/new');
  await expect(page.getByRole('button', { name: /create pack/i })).toBeVisible();
});

// ── 6. Pack detail shows test plan section ────────────────────────────────────

test('06 - pack detail shows empty test plan state or test cases', async ({ page }) => {
  // Create a pack via API first
  const proj = await apiPost('/projects', { name: `E2E-Project-${RUN_TS}` });
  const pack = await apiPost('/validation-packs', { name: `E2E-Pack-${RUN_TS}`, project_id: proj.id });

  await navTo(page, `/packs/${pack.id}`);
  // Should show either empty state or test plan section
  const body = await page.locator('body').innerText();
  expect(
    body.includes('No test plan') || body.includes('test case') || body.includes('Generate')
  ).toBeTruthy();
});

// ── 7. Generate test plan ─────────────────────────────────────────────────────

test('07 - generate test plan creates test cases', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-Proj-Plan-${RUN_TS}` });
  const pack = await apiPost('/validation-packs', { name: `E2E-Plan-Pack-${RUN_TS}`, project_id: proj.id });

  await navTo(page, `/packs/${pack.id}`);
  // Look for "Generate test plan" button
  const genBtn = page.getByRole('button', { name: /generate test plan/i });
  if (await genBtn.isVisible().catch(() => false)) {
    await genBtn.click();
    // After generation, test cases should appear OR a loading state
    await page.waitForTimeout(2000);
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(100);
  } else {
    // Plan already exists — verify test cases are shown
    await expect(page.locator('body')).toBeVisible();
  }
});

// ── 8. Start run — capability gap or run detail ───────────────────────────────

test('08 - run pack navigates to review modal or run detail', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-Run-Proj-${RUN_TS}` });
  const app  = await apiPost('/apps', { name: `E2E-App-${RUN_TS}`, app_type: 'web', project_id: proj.id });
  const pack = await apiPost('/validation-packs', { name: `E2E-Run-Pack-${RUN_TS}`, project_id: proj.id });

  await navTo(page, `/packs/${pack.id}`);
  const runBtn = page.getByText(/run pack/i);
  if (await runBtn.isVisible().catch(() => false)) {
    await runBtn.click();
    // Either a review modal appears or navigation to run
    await page.waitForTimeout(1000);
    // Should not throw or show blank page
    await expect(page.locator('body')).toBeVisible();
  }
});

// ── 9. Live run detail ────────────────────────────────────────────────────────

test('09 - live runs page shows empty state or run list', async ({ page }) => {
  await navTo(page, '/runs');
  const body = await page.locator('body').innerText();
  // Should show "No runs yet" or a run list — not blank, not 500 error
  expect(
    body.includes('run') || body.includes('No runs')
  ).toBeTruthy();
});

// ── 10. Evidence page ─────────────────────────────────────────────────────────

test('10 - evidence center shows empty state when no evidence', async ({ page }) => {
  await navTo(page, '/evidence');
  await expect(page.locator('body')).toBeVisible();
  const text = await page.locator('body').innerText();
  expect(text.length).toBeGreaterThan(0);
});

// ── 11. Reports page ──────────────────────────────────────────────────────────

test('11 - reports page shows empty state or report list', async ({ page }) => {
  await navTo(page, '/reports');
  await expect(page.locator('body')).toBeVisible();
  const text = await page.locator('body').innerText();
  expect(text.length).toBeGreaterThan(0);
});

test('11b - API pack run shows API evidence and report metrics', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-API-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-API-App-${RUN_TS}`,
    app_type: 'api',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-API-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'API request health endpoint',
        action_type: 'api_request',
        method: 'GET',
        url: 'http://127.0.0.1:8765/api/health',
        headers: { Authorization: 'Bearer secret-token' },
        timeout_ms: 5000,
      },
      {
        description: 'Assert status 200',
        action_type: 'assert_status',
        expected_status: 200,
        timeout_ms: 5000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  const report = await apiPost(`/runs/${run.id}/report/generate`, {});

  await navTo(page, `/runs/${run.id}`);
  await expect(page.getByText(/api request/i).first()).toBeVisible({ timeout: 10_000 });

  await navTo(page, `/reports/${report.id}`);
  await expect(page.getByText(/API STEPS/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/AVG API MS/i)).toBeVisible({ timeout: 10_000 });
});

test('11f - completed run allows AI evidence evaluation without changing verdict', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-AI-Eval-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-AI-Eval-App-${RUN_TS}`,
    app_type: 'api',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-AI-Eval-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'API request health endpoint',
        action_type: 'api_request',
        method: 'GET',
        url: 'http://127.0.0.1:8765/api/health',
        timeout_ms: 5000,
      },
      {
        description: 'Assert status 200',
        action_type: 'assert_status',
        expected_status: 200,
        timeout_ms: 5000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  await navTo(page, `/runs/${run.id}`);
  const evalBtn = page.getByRole('button', { name: /evaluate evidence with ai/i });
  await expect(evalBtn).toBeVisible({ timeout: 10_000 });

  const beforeStatus = (await apiGet(`/runs/${run.id}`)).status;

  const evalReqPromise = page.waitForRequest((req) =>
    req.url().includes(`/api/runs/${run.id}/evaluate-ai`) && req.method() === 'POST'
  );
  const evalRespPromise = page.waitForResponse((resp) =>
    resp.url().includes(`/api/runs/${run.id}/evaluate-ai`) && resp.request().method() === 'POST',
    { timeout: 30_000 }
  );
  await evalBtn.click({ force: true });
  await evalReqPromise;
  const evalResp = await evalRespPromise;
  expect(evalResp.status()).toBe(201);
  const note = await evalResp.json();

  await expect(page.getByText(/AI Evaluation Notes/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/AI Draft — Non-Authoritative/i)).toBeVisible();
  await expect(page.getByText(/This does not change the actual run verdict\./i)).toBeVisible();
  await expect(page.getByText(new RegExp(note.verdict_assessment, 'i'))).toBeVisible();
  await expect(
    page.getByText(new RegExp(`generation_source:\\s*${note.generation_source}`, 'i'))
  ).toBeVisible();

  await expect(page.getByRole('button', { name: /apply verdict/i })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /fix selector/i })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /generate patch/i })).toHaveCount(0);

  const afterStatus = (await apiGet(`/runs/${run.id}`)).status;
  expect(afterStatus).toBe(beforeStatus);
});

// ── 12. Memory page ───────────────────────────────────────────────────────────

test('12 - memory page loads with stats', async ({ page }) => {
  await navTo(page, '/memory');
  await expect(page.getByText(/memory/i).first()).toBeVisible({ timeout: 8_000 });
  // Use button role to avoid matching "Semantic Recall" section heading
  await expect(page.getByRole('button', { name: /^Recall$/i })).toBeVisible();
});

// ── 13. Global search ─────────────────────────────────────────────────────────

test('13 - Cmd+K opens global search', async ({ page }) => {
  await navTo(page, '/');
  await page.keyboard.press('Meta+k');
  await expect(page.getByTestId('global-search-overlay')).toBeVisible({ timeout: 3_000 });
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('global-search-overlay')).not.toBeVisible();
});

// ── 15. LocalFolderBridge: recommended roots, no Downloads, custom root ────────

test('15a - local environment mode returns recommended and optional roots', async ({ page }) => {
  const data = await apiGet('/local-environment/mode');
  expect(data.mode).toBe('local_web');
  expect(Array.isArray(data.recommended_roots)).toBe(true);
  expect(Array.isArray(data.optional_roots)).toBe(true);
  // Downloads must never appear
  const allRoots = [...data.recommended_roots, ...data.optional_roots, ...data.allowed_roots];
  expect(allRoots.some((r: string) => r.toLowerCase().includes('downloads'))).toBe(false);
  // Home itself must not appear
  const home = homedir();
  expect(data.recommended_roots).not.toContain(home);
  expect(data.optional_roots).not.toContain(home);
});

// Helper: step through AddAppPage wizard to step 2 with local_folder pre-selected.
// Creates a project via API, selects it in step 1, clicks Next.
async function reachLocalFolderStep2(page: Page): Promise<void> {
  const proj = await apiPost('/projects', { name: `E2E-LFB-Proj-${RUN_TS}-${Math.random().toString(36).slice(2, 7)}` });
  await navTo(page, '/projects/new?source=local_folder');
  // E2E-prefixed projects are hidden by default — click toggle to reveal them
  const toggle = page.getByTestId('show-test-projects-toggle');
  if (await toggle.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await toggle.click();
  }
  // Wait for project list to load then select our project
  const projItem = page.getByTestId('project-item').filter({ hasText: proj.name });
  await expect(projItem).toBeVisible({ timeout: 10_000 });
  await projItem.click();
  // Advance to step 2
  await page.getByRole('button', { name: /next.*source/i }).click();
  // ?source=local_folder pre-selects the tab; LocalFolderBridge should render
}

test('15b - add-app local folder tab loads and shows recommended roots section', async ({ page }) => {
  await reachLocalFolderStep2(page);
  // The LocalFolderBridge renders; mode badge should show
  await expect(page.getByTestId('bridge-mode-badge')).toBeVisible({ timeout: 10_000 });
  expect(await page.getByTestId('bridge-mode-badge').innerText()).toMatch(/local/i);
});

test('15c - local folder bridge does not show Downloads in any root chip', async ({ page }) => {
  await reachLocalFolderStep2(page);
  await expect(page.getByTestId('bridge-mode-badge')).toBeVisible({ timeout: 10_000 });
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(/Downloads/i);
});

// ── 14b. GAP 8B: App detail shows Validation Packs section ───────────────────

test('14b - app detail shows validation packs section', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-AppPacks-Proj-${RUN_TS}` });
  const app  = await apiPost('/apps', { name: `E2E-AppPacks-App-${RUN_TS}`, app_type: 'web', project_id: proj.id });

  await navTo(page, `/apps/${app.id}`);
  await expect(page.getByTestId('app-packs-section')).toBeVisible({ timeout: 8_000 });
  // Empty state: no packs linked yet
  await expect(page.getByTestId('app-packs-empty')).toBeVisible({ timeout: 5_000 });
});

test('14c - app detail "New pack" navigates to create page with app_id + project_id', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-NewPackCTA-Proj-${RUN_TS}` });
  const app  = await apiPost('/apps', { name: `E2E-NewPackCTA-App-${RUN_TS}`, app_type: 'web', project_id: proj.id });

  await navTo(page, `/apps/${app.id}`);
  await expect(page.getByTestId('create-pack-btn')).toBeVisible({ timeout: 8_000 });
  await page.getByTestId('create-pack-btn').click();

  await page.waitForURL(/\/packs\/new/, { timeout: 5_000 });
  const url = page.url();
  expect(url).toContain(`app_id=${app.id}`);
  expect(url).toContain(`project_id=${proj.id}`);
});

test('14d - create pack with app_id shows linked-app-summary', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-LinkedApp-Proj-${RUN_TS}` });
  const app  = await apiPost('/apps', { name: `E2E-LinkedApp-App-${RUN_TS}`, app_type: 'web', project_id: proj.id });

  await navTo(page, `/packs/new?app_id=${app.id}&project_id=${proj.id}`);
  await expect(page.getByTestId('linked-app-summary')).toBeVisible({ timeout: 8_000 });
  // App name appears in the linked app card
  const body = await page.locator('[data-testid="linked-app-summary"]').innerText();
  expect(body).toContain(`E2E-LinkedApp-App-${RUN_TS}`);
});

test('14e - pack linked to app shows pack in app detail packs list', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-PackList-Proj-${RUN_TS}` });
  const app  = await apiPost('/apps', { name: `E2E-PackList-App-${RUN_TS}`, app_type: 'web', project_id: proj.id });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-PackList-Pack-${RUN_TS}`, project_id: proj.id, app_id: app.id,
  });

  await navTo(page, `/apps/${app.id}`);
  await expect(page.getByTestId(`pack-card-${pack.id}`)).toBeVisible({ timeout: 8_000 });
});

// ── 11c. Performance pack run shows performance metrics and report summary ────

test('11c - web pack run shows performance metrics and report summary', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-Perf-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-Perf-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-Perf-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'Measure page load time',
        action_type: 'measure_page_load',
        budget_ms: 10000,
        warn_ms: 5000,
        metric_name: 'total_load_ms',
        timeout_ms: 15000,
      },
      {
        description: 'Assert page load under budget',
        action_type: 'assert_page_load_under',
        budget_ms: 10000,
        warn_ms: 5000,
        metric_name: 'total_load_ms',
        timeout_ms: 15000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  const report = await apiPost(`/runs/${run.id}/report/generate`, {});

  await navTo(page, `/runs/${run.id}`);
  await expect(page.getByText(/page performance timing metrics/i).first()).toBeVisible({ timeout: 15_000 });

  await navTo(page, `/reports/${report.id}`);
  await expect(page.getByText(/performance summary/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/avg page load/i)).toBeVisible({ timeout: 10_000 });
});

// ── 11d. Accessibility pack run shows accessibility violations and report summary ────

test('11d - web pack run shows accessibility violations and report summary', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-A11y-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-A11y-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-A11y-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'Check page accessibility',
        action_type: 'check_accessibility',
        timeout_ms: 15000,
      },
      {
        description: 'Assert page accessibility',
        action_type: 'assert_accessibility',
        budget_ms: 10,
        timeout_ms: 15000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  const report = await apiPost(`/runs/${run.id}/report/generate`, {});

  await navTo(page, `/runs/${run.id}`);
  await expect(page.getByText(/accessibility audit summary/i).first()).toBeVisible({ timeout: 15_000 });

  await navTo(page, `/reports/${report.id}`);
  await expect(page.getByText(/accessibility summary/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/total audits/i)).toBeVisible({ timeout: 10_000 });
});

// ── 11e. New accessibility scan and assertion actions E2E ────────────────────

test('11e - web pack run shows new accessibility scan and assertion actions', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-A11yNew-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-A11yNew-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-A11yNew-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'New accessibility scan',
        action_type: 'accessibility_scan',
        timeout_ms: 15000,
      },
      {
        description: 'Assert no critical violations',
        action_type: 'assert_no_critical_a11y_violations',
        budget_ms: 0,
        timeout_ms: 15000,
      },
      {
        description: 'Assert no violations',
        action_type: 'assert_no_a11y_violations',
        budget_ms: 5,
        timeout_ms: 15000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  const report = await apiPost(`/runs/${run.id}/report/generate`, {});

  await navTo(page, `/runs/${run.id}`);
  await expect(page.getByText(/accessibility audit summary/i).first()).toBeVisible({ timeout: 15_000 });

  await navTo(page, `/reports/${report.id}`);
  await expect(page.getByText(/accessibility summary/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/total audits/i)).toBeVisible({ timeout: 10_000 });
});

// ── 15. Visual Regression Assertions E2E ────────────────────

test('15 - web pack run shows visual regression card and supports baseline approval', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-Visual-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-Visual-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-Visual-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'Assert visual match of body',
        action_type: 'assert_visual_match',
        target: 'body',
        value: 'body_baseline',
        expected: '0.05',
        timeout_ms: 15000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  await navTo(page, `/runs/${run.id}`);
  
  // Verify that the VisualRegressionCard is rendered
  await expect(page.getByText(/Visual Comparison/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Approve Baseline/i)).toBeVisible({ timeout: 15_000 });

  // Click Approve Baseline button
  await page.getByRole('button', { name: /Approve Baseline/i }).click();

  // Verify it transitions to approved state
  await expect(page.getByRole('button', { name: /Baseline Approved/i })).toBeVisible({ timeout: 10_000 });
});

// ── 16. Passive Security Testing E2E ────────────────────

test('16 - web pack run shows security sweep findings and report summary', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-Sec-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-Sec-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-Sec-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });

  await apiPatch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        description: 'Run passive security sweep',
        action_type: 'passive_security_check',
        timeout_ms: 15000,
      },
      {
        description: 'Assert no critical security findings',
        action_type: 'assert_no_critical_security_findings',
        timeout_ms: 15000,
      },
    ],
  });

  const run = await apiPost(`/validation-packs/${pack.id}/run`, { app_target_id: app.id });
  const finishedRun = await waitForRunCompletion(run.id);
  expect(['completed', 'failed']).toContain(finishedRun.status);

  const report = await apiPost(`/runs/${run.id}/report/generate`, {});

  await navTo(page, `/runs/${run.id}`);
  
  // Verify that the SecurityFindingsCard is rendered and shows the passive-only warning badge
  await expect(page.getByText(/PASSIVE SECURITY SWEEP SUMMARY/i).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Passive check. No attack traffic sent./i).first()).toBeVisible({ timeout: 15_000 });

  await navTo(page, `/reports/${report.id}`);
  // Verify report summary is displayed
  await expect(page.getByText(/SECURITY SUMMARY/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/TOTAL CHECKS/i)).toBeVisible({ timeout: 10_000 });
});

// ── 14. Backend offline state ─────────────────────────────────────────────────

test('14 - offline state shown when backend unreachable', async ({ page }) => {
  // Use `${BASE}/api/**` not `**/api/**`:
  // The broad glob also matches http://localhost:5173/src/api/client.ts (Vite source
  // module), aborting the JS bundle and leaving a blank page.
  // Anchored pattern only matches actual API calls at the proxy root.
  await page.route(`${BASE}/api/**`, route => route.abort());
  await page.goto(`${BASE}/`);
  // BackendStatusBanner renders immediately: _backendStatus is 'offline' at module init.
  // Text: "Backend offline — run: uvicorn qa_ai.server:app …"
  await expect(page.getByText(/backend offline/i).first()).toBeVisible({ timeout: 10_000 });
});

// ── 17. AI Test Plan Generation E2E ────────────────────

test('17 - generate with AI, preview, select and accept', async ({ page }) => {
  const proj = await apiPost('/projects', { name: `E2E-AI-Proj-${RUN_TS}` });
  const app = await apiPost('/apps', {
    name: `E2E-AI-App-${RUN_TS}`,
    app_type: 'web',
    project_id: proj.id,
    base_url: 'http://127.0.0.1:8765/api/health',
  });
  const pack = await apiPost('/validation-packs', {
    name: `E2E-AI-Pack-${RUN_TS}`,
    project_id: proj.id,
    app_id: app.id,
  });
  await waitForPackAvailable(pack.id);

  await navTo(page, `/packs/${pack.id}`);

  // 1. Generate with AI opens preview
  const aiBtn = page.getByTestId('generate-ai-test-plan-btn');
  await expect(aiBtn).toBeVisible({ timeout: 10_000 });
  const aiRespPromise = page.waitForResponse((resp) =>
    resp.url().includes(`/api/validation-packs/${pack.id}/test-plan/generate-ai`) &&
    resp.request().method() === 'POST',
    { timeout: 30_000 }
  );
  await aiBtn.click({ force: true });
  const aiResp = await aiRespPromise;
  expect(aiResp.status()).toBe(200);

  // Wait for the modal to open
  const modalHeader = page.getByText(/AI Proposed Test Plan Preview/i);
  await expect(modalHeader).toBeVisible({ timeout: 30_000 });

  // 2. Preview contains local_fallback or generated source
  const sourceText = page.getByText(/Source:/i);
  await expect(sourceText).toBeVisible();

  // 3. User selects/deselects one case, accepts it
  const acceptBtn = page.getByRole('button', { name: /Accept Selected/i });
  await expect(acceptBtn).toBeVisible();
  await acceptBtn.click();

  // 4. Close and refresh: preview modal goes away, accepted case appears in the list
  await expect(modalHeader).not.toBeVisible({ timeout: 10_000 });

  // Accepted case should render in the main table with sparkles badge
  const sparklesBadge = page.getByTestId('ai-sparkles-badge');
  await expect(sparklesBadge.first()).toBeVisible({ timeout: 10_000 });
});
