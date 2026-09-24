import { expect, test, type Page } from '@playwright/test';

const API = process.env.E2E_API_URL ?? 'http://127.0.0.1:8765';
const RUN_TS = Date.now();

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: object): Promise<T> {
  return apiJson<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

async function patch<T>(path: string, body: object): Promise<T> {
  return apiJson<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}

async function waitForTerminalRun(runId: string) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const run = await apiJson<Record<string, unknown>>(`/runs/${runId}`);
    if (['completed', 'failed', 'cancelled'].includes(String(run.status))) return run;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`Run ${runId} did not become terminal`);
}

test.afterAll(async () => {
  await fetch(`${API}/api/dev/e2e-data?confirm=true`, { method: 'DELETE' }).catch(() => {});
});

test('failed run generates one advisory RCA only after explicit click and persists on refresh', async ({ page }) => {
  const project = await post<{ id: string }>('/projects', {
    name: `E2E-RCA-Project-${RUN_TS}`,
    description: 'Disposable RCA browser verification',
  });
  const app = await post<{ id: string }>('/apps', {
    project_id: project.id,
    name: `E2E-RCA-App-${RUN_TS}`,
    app_type: 'api',
    base_url: API,
  });
  const pack = await post<{ id: string }>('/validation-packs', {
    project_id: project.id,
    app_id: app.id,
    name: `E2E-RCA-Pack-${RUN_TS}`,
    description: 'Deterministic failing API assertion',
  });
  await patch(`/validation-packs/${pack.id}`, {
    steps: [
      {
        step_id: 'rca-request',
        order: 1,
        description: 'Request backend health',
        action_type: 'api_request',
        method: 'GET',
        url: `${API}/api/health`,
        timeout_seconds: 5,
      },
      {
        step_id: 'rca-failing-assertion',
        order: 2,
        description: 'Deliberately expect status 201',
        action_type: 'assert_status',
        expected_status: 201,
        timeout_seconds: 5,
      },
    ],
  });

  const started = await post<{ id: string }>(`/validation-packs/${pack.id}/run`, {
    app_target_id: app.id,
  });
  const before = await waitForTerminalRun(started.id);
  expect(before.status).toBe('failed');

  const rcaRequests: Array<{ method: string; url: string }> = [];
  page.on('request', request => {
    if (request.url().includes(`/api/runs/${started.id}/root-cause-ai`)) {
      rcaRequests.push({ method: request.method(), url: request.url() });
    }
  });

  await page.goto(`/runs/${started.id}`);
  await expect(page.getByText('AI Possible Causes', { exact: true })).toBeVisible();
  await expect(page.getByText('AI Evaluation Notes', { exact: true })).toBeVisible();
  await expect(page.getByText('This is a hypothesis. It does not change the run verdict or fix the app.')).toBeVisible();
  await expect(page.getByText('Non-authoritative', { exact: true })).toBeVisible();
  expect(rcaRequests.filter(request => request.method === 'POST')).toHaveLength(0);

  const generationResponse = page.waitForResponse(response => (
    response.request().method() === 'POST'
    && response.url().includes(`/api/runs/${started.id}/root-cause-ai`)
  ));
  await page.getByRole('button', { name: 'Suggest possible causes' }).click();
  expect((await generationResponse).status()).toBe(201);

  await expect(page.getByText(/Possible cause:/i).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/confidence:/i).first()).toBeVisible();
  await expect(page.getByText(/generation:/i).first()).toBeVisible();
  expect(rcaRequests.filter(request => request.method === 'POST')).toHaveLength(1);

  for (const forbidden of [
    'Apply Fix', 'Apply Verdict', 'Fix Selector', 'Auto Heal', 'Rerun',
    'Generate Patch', 'Update Test', 'Modify Step',
  ]) {
    await expect(page.getByRole('button', { name: new RegExp(forbidden, 'i') })).toHaveCount(0);
  }

  const afterGeneration = await apiJson<Record<string, unknown>>(`/runs/${started.id}`);
  expect(afterGeneration.status).toEqual(before.status);
  expect(afterGeneration.error).toEqual(before.error);
  expect(afterGeneration.step_results).toEqual(before.step_results);

  rcaRequests.length = 0;
  await page.reload();
  await expect(page.getByText(/Possible cause:/i).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('button', { name: 'Suggest possible causes' })).toHaveCount(0);
  expect(rcaRequests.some(request => request.method === 'GET')).toBe(true);
  expect(rcaRequests.filter(request => request.method === 'POST')).toHaveLength(0);

  const afterRefresh = await apiJson<Record<string, unknown>>(`/runs/${started.id}`);
  expect(afterRefresh.status).toEqual(before.status);
  expect(afterRefresh.error).toEqual(before.error);
  expect(afterRefresh.step_results).toEqual(before.step_results);
});
