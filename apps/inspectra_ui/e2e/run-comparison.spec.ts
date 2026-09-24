import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = resolve(repo, 'venv/bin/python');
const helper = resolve(repo, 'apps/inspectra_ui/e2e/fixtures/run_comparison.py');
function fixture(command: string, directory: string, api?: string) {
  return JSON.parse(execFileSync(python, [helper, command, directory, ...(api ? [api] : [])], { cwd: repo, encoding: 'utf8', timeout: 30_000 }));
}
async function port() {
  const server = createServer();
  await new Promise<void>((done, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', done); });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('No local port');
  await new Promise<void>(done => server.close(() => done()));
  return address.port;
}

test('explicit comparison renders persisted facts and preserves all fixture state', async ({ page, request }, info) => {
  test.setTimeout(60_000);
  const external = process.env.E2E_COMPARISON_FIXTURE_DIR;
  const directory = external ?? mkdtempSync(resolve(tmpdir(), 'inspectra-history-18a-comparison-'));
  const api = external ? process.env.E2E_API_URL! : `http://127.0.0.1:${await port()}`;
  let backend: ChildProcess | undefined;
  const mutations: string[] = [];
  const comparisons: string[] = [];
  try {
    if (!external) {
      fixture('seed', directory);
      backend = spawn(python, ['-m', 'uvicorn', 'qa_ai.product_backend.server:create_product_app', '--factory', '--host', '127.0.0.1', '--port', new URL(api).port], {
        cwd: repo, env: { ...process.env, INSPECTRA_ARTIFACTS_DIR: directory }, stdio: 'ignore',
      });
    }
    await expect.poll(async () => { try { return (await request.get(`${api}/api/health`)).status(); } catch { return 0; } }, { timeout: 20_000 }).toBe(200);
    const verification = fixture('verify', directory, api);
    await info.attach('api-verification', { body: JSON.stringify(verification), contentType: 'application/json' });
    const before = fixture('snapshot', directory);
    await page.route(url => url.pathname.startsWith('/api/'), async route => {
      const req = route.request();
      if (!['GET', 'HEAD'].includes(req.method())) { mutations.push(req.method()); await route.abort(); return; }
      const url = new URL(req.url());
      if (url.pathname.endsWith('/compare')) comparisons.push(url.search);
      await route.fulfill({ response: await route.fetch({ url: `${api}${url.pathname}${url.search}` }) });
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/runs/c18-current');
    const panel = page.getByRole('region', { name: 'Run Comparison', exact: true });
    const select = panel.getByRole('combobox');
    await expect(select.locator('option[value="c18-base"]')).toHaveCount(1);
    expect(comparisons).toEqual([]);
    for (const id of ['c18-current', 'h18-other-target', 'h18-other-pack', 'h18-active', 'h18-pending']) {
      await expect(select.locator(`option[value="${id}"]`)).toHaveCount(0);
    }
    await select.selectOption('c18-base');
    await expect(panel.getByText('Forward comparison', { exact: true })).toBeVisible();
    expect(comparisons).toEqual(['?baseline_run_id=c18-base']);
    await expect(panel.getByLabel('Passed → Failed count', { exact: true })).toHaveText('1');
    await expect(panel.getByLabel('Failed → Passed count', { exact: true })).toHaveText('1');
    await expect(panel.getByText('Execution configuration continuity between these runs cannot be fully verified.', { exact: true })).toBeVisible();
    const row = panel.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'pf Matched', exact: true }) });
    await expect(row).toContainText('Passed → Failed');
    await expect(row).toContainText('+20 ms');
    await expect(row).toContainText('200 → 500');
    await expect(row).toContainText('Delta: Unavailable');
    await expect(panel.getByText('Matching failure signatures do not prove the same root cause.', { exact: true })).toBeVisible();
    await expect(panel.getByRole('button', { name: /retest|retry|run again|fix|heal|apply|update test|generate ai|recommend|promote/i })).toHaveCount(0);
    expect(await panel.innerText()).not.toMatch(/\bRegression\b|\bFixed\b|\bBroken\b|Added test|Removed test|\/Users\/|file:\/\//);
    await panel.screenshot({ path: info.outputPath('comparison-forward.png') });
    await select.selectOption('c18-newer');
    await expect(panel.getByText('Reverse chronological comparison', { exact: true })).toBeVisible();
    await expect(panel.getByText('This reference run is newer than the current run. Comparison direction remains reference → current.', { exact: true })).toBeVisible();
    await panel.screenshot({ path: info.outputPath('comparison-reverse.png') });
    await panel.getByRole('button', { name: 'Open run c18-newer', exact: true }).first().click();
    await expect(page).toHaveURL(/\/runs\/c18-newer$/);
    await expect(select).toHaveValue('');
    await expect(panel.getByLabel('Comparison direction')).toHaveCount(0);
    await page.reload();
    await expect(select).toHaveValue('');
    expect(comparisons).toHaveLength(2);
    expect(mutations).toEqual([]);
    expect(fixture('snapshot', directory)).toEqual(before);
  } finally {
    if (backend && backend.exitCode === null) {
      backend.kill('SIGTERM');
      await new Promise<void>(done => backend!.once('exit', () => done()));
    }
    await info.attach('fixture-directory', { body: directory, contentType: 'text/plain' });
  }
});
