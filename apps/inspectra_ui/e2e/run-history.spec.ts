import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = process.env.E2E_PYTHON ?? resolve(repo, 'venv/bin/python');
const helper = resolve(repo, 'apps/inspectra_ui/e2e/fixtures/run_history.py');

function fixture(command: string, directory: string, api?: string) {
  return JSON.parse(execFileSync(python, [helper, command, directory, ...(api ? [api] : [])], {
    cwd: repo, encoding: 'utf8', timeout: 30_000,
  }));
}

async function unusedPort(): Promise<number> {
  const server = createServer();
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('No local port assigned');
  await new Promise<void>((done, reject) => server.close(error => error ? reject(error) : done()));
  return address.port;
}

test('historical context shows cited deterministic facts without mutating product data', async ({ page, request }, testInfo) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  let backend: ChildProcess | undefined;
  let backendLog = '';
  const externalDirectory = process.env.E2E_HISTORY_FIXTURE_DIR;
  const directory = externalDirectory ?? mkdtempSync(resolve(tmpdir(), 'inspectra-history-18a-'));
  const api = externalDirectory
    ? (process.env.E2E_API_URL ?? 'http://127.0.0.1:8765')
    : `http://127.0.0.1:${await unusedPort()}`;
  const mutations: string[] = [];
  try {
    if (!externalDirectory) {
      fixture('seed', directory);
      backend = spawn(python, ['-m', 'uvicorn', 'qa_ai.product_backend.server:create_product_app', '--factory', '--host', '127.0.0.1', '--port', new URL(api).port], {
        cwd: repo, env: { ...process.env, INSPECTRA_ARTIFACTS_DIR: directory }, stdio: ['ignore', 'pipe', 'pipe'],
      });
      backend.stdout?.on('data', data => { backendLog += String(data); });
      backend.stderr?.on('data', data => { backendLog += String(data); });
    }
    await expect.poll(async () => {
      try { return (await request.get(`${api}/api/health`)).status(); } catch { return 0; }
    }, { timeout: 20_000 }).toBe(200);
    // Exact fixtures + all-table snapshots verify that this API uses our disposable DB.
    const verification = fixture('verify', directory, api);
    expect(verification.history.failure_rate).toMatchObject({ failed: 3, total: 6, value: 0.5 });
    const before = fixture('snapshot', directory);
    await testInfo.attach('api-verification', { body: JSON.stringify(verification, null, 2), contentType: 'application/json' });

    // Relay to the isolated live backend; no mocked historical response.
    await page.route(url => url.pathname.startsWith('/api/'), async route => {
      const incoming = route.request();
      if (!['GET', 'HEAD'].includes(incoming.method())) {
        mutations.push(`${incoming.method()} ${new URL(incoming.url()).pathname}`);
        await route.abort();
        return;
      }
      const url = new URL(incoming.url());
      await route.fulfill({ response: await route.fetch({ url: `${api}${url.pathname}${url.search}` }) });
    });
    await page.goto('/runs/h18-current');
    const panel = page.getByRole('region', { name: 'Historical Context', exact: true });
    await expect(panel).toBeVisible();
    await expect(panel.getByText('3 of 6 comparable real executions failed.', { exact: true })).toBeVisible();
    await expect(panel.getByText('50%', { exact: true })).toBeVisible();
    await expect(panel.getByText('Last factual pass', { exact: true })).toBeVisible();
    await expect(panel.getByText('Last factual failure', { exact: true })).toBeVisible();
    await expect(panel.getByText(/configuration and base URL continuity cannot be verified/)).toBeVisible();
    await expect(panel.getByText('Same deterministic failure signature', { exact: true })).toBeVisible();
    await expect(panel.getByText('2 occurrences', { exact: true })).toBeVisible();
    await expect(panel.getByRole('region', { name: 'Manual observations', exact: true })).toBeVisible();
    await expect(panel.getByText('identity unavailable', { exact: true })).toBeVisible();
    await expect(panel.getByText('evidence h18-owned', { exact: true }).first()).toBeVisible();
    await expect(panel.getByRole('link', { name: /evidence/ })).toHaveCount(0);
    await expect(panel.getByText(/h18-wrong-step|h18-wrong-run|h18-missing-evidence/)).toHaveCount(0);
    await expect(panel.getByRole('button', { name: /retest|retry|heal|fix|update test|generate/i })).toHaveCount(0);
    await expect(panel.getByText(/same root cause|recurring bug|proven regression|same environment|same app version/)).toHaveCount(0);
    expect(await panel.innerText()).not.toMatch(/\/Users\/|\/private\/|file:\/\//);
    await page.screenshot({ path: testInfo.outputPath('run-detail.png') });
    await panel.evaluate(element => element.scrollIntoView({ block: 'start' }));
    await page.screenshot({ path: testInfo.outputPath('history-populated.png') });
    await panel.getByRole('button', { name: 'Open run h18-pass', exact: true }).first().click();
    await expect(page).toHaveURL(/\/runs\/h18-pass$/);
    await expect(page.getByRole('region', { name: 'Historical Context', exact: true })).toBeVisible();
    await expect(page.getByText('Current fixture failure', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Failure details', exact: true })).toHaveCount(0);

    // Exercise response states without changing product code or persisted records.
    for (const [runId, copy, state] of [
      ['h18-empty-current', 'No comparable historical runs were found.', 'empty'],
      ['h18-thin-current', 'Not enough comparable real-execution history is available to establish a reliable pattern. Exact observations remain visible below.', 'insufficient'],
      ['h18-nonreal-current', 'No comparable automated real-execution history is available. Manual and excluded observations remain separate below.', 'manual-nonreal'],
    ]) {
      await page.goto(`/runs/${runId}`);
      await expect(panel.getByText(copy, { exact: true })).toBeVisible();
      await panel.screenshot({ path: testInfo.outputPath(`history-${state}.png`) });
    }
    const historyUrl = '**/api/runs/h18-current/history?*';
    let releaseHistory!: () => void;
    const delayed = new Promise<void>(done => { releaseHistory = done; });
    await page.route(historyUrl, async route => {
      await delayed;
      await route.fallback();
    });
    await page.goto('/runs/h18-current');
    try {
      await expect(panel.getByText('Loading historical context…', { exact: true })).toBeVisible();
      await panel.screenshot({ path: testInfo.outputPath('history-loading.png') });
    } finally { releaseHistory(); }
    await expect(panel.getByText('50%', { exact: true })).toBeVisible();
    await page.unroute(historyUrl);
    await page.route(historyUrl, route => route.fulfill({ status: 500, json: { detail: 'Injected history transport failure' } }));
    await page.reload();
    await expect(panel.getByText('Run history could not be loaded.', { exact: true })).toBeVisible();
    await panel.screenshot({ path: testInfo.outputPath('history-error.png') });
    await page.unroute(historyUrl);
    const demoRequests: string[] = [];
    page.on('request', outgoing => {
      if (new URL(outgoing.url()).pathname.startsWith('/api/')) demoRequests.push(outgoing.url());
    });
    await page.goto('/demo/runs/run-001');
    await expect(panel.getByText('Historical context is unavailable in the demo workspace.', { exact: true })).toBeVisible();
    await panel.screenshot({ path: testInfo.outputPath('history-demo.png') });
    expect(demoRequests).toEqual([]);
    expect(mutations).toEqual([]);
    expect(fixture('snapshot', directory)).toEqual(before);
  } finally {
    // Stop only the process this test started; preserve fixtures for inspection.
    if (backend && backend.exitCode === null) {
      backend.kill('SIGTERM');
      await new Promise<void>(done => backend!.once('exit', () => done()));
    }
    await testInfo.attach('fixture-directory', { body: directory, contentType: 'text/plain' });
    if (backendLog) await testInfo.attach('backend-log', { body: backendLog, contentType: 'text/plain' });
  }
});
