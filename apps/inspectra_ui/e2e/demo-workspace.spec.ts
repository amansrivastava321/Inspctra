import { expect, test } from '@playwright/test';

const DEMO_MESSAGE = 'Demo Workspace — Sample data for exploration. No real tests are running.';
const READ_ONLY_TOOLTIP = 'Available in your real workspace. Leave demo to get started.';

test('offline real workspace can enter and leave an isolated read-only demo', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));

  await page.route(
    url => new URL(url).pathname.startsWith('/api/'),
    route => route.abort(),
  );
  await page.goto('/');
  expect(pageErrors).toEqual([]);

  await expect(page.getByText('Backend offline').first()).toBeVisible();
  await expect(page.locator('[data-testid="provenance-badge"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /retry connection/i }).first()).toBeVisible();
  await page.getByRole('button', { name: /try demo/i }).first().click();

  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByText(DEMO_MESSAGE)).toBeVisible();
  await expect(page.getByText('FlowBook').first()).toBeVisible();
  await expect(page.locator('[data-provenance-source="Dashboard health"]')).toHaveText('Demo');
  await expect(page.locator('[data-provenance-source="Dashboard metric"]')).toHaveCount(4);

  const startRun = page.getByRole('button', { name: /start live test/i });
  await expect(startRun).toBeDisabled();
  await expect(startRun).toHaveAttribute('title', READ_ONLY_TOOLTIP);

  await page.getByRole('button', { name: /^projects$/i }).click();
  await expect(page).toHaveURL(/\/demo\/projects$/);
  await expect(page.getByText(DEMO_MESSAGE)).toBeVisible();

  const connectApp = page.getByRole('button', { name: /^connect app$/i });
  await expect(connectApp).toBeDisabled();
  await expect(connectApp).toHaveAttribute('title', READ_ONLY_TOOLTIP);
  await expect(page.locator('[data-provenance-source="App card"]')).toHaveCount(4);

  await page.getByRole('button', { name: /^leave demo$/i }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText(DEMO_MESSAGE)).toHaveCount(0);
  await expect(page.getByText('Backend offline').first()).toBeVisible();
  await expect(page.getByText('FlowBook')).toHaveCount(0);
});

test('direct demo navigation performs no backend requests', async ({ page }) => {
  const apiRequests: string[] = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
  });

  await page.goto('/demo');
  await expect(page.getByText(DEMO_MESSAGE)).toBeVisible();
  await page.getByRole('button', { name: /^projects$/i }).click();
  await expect(page).toHaveURL(/\/demo\/projects$/);
  await expect(page.getByText('Videomation').first()).toBeVisible();
  await expect(page.locator('[data-provenance-source="App card"]')).toHaveCount(4);

  await page.goto('/demo/runs/run-001');
  await expect(page.locator('[data-provenance-source="Live run detail"]')).toHaveText('Demo');
  await expect(page.locator('[data-provenance-source="Run step"]')).toHaveCount(9);
  const generateReport = page.getByRole('button', { name: /generate report/i });
  await expect(generateReport).toBeDisabled();
  await expect(generateReport).toHaveAttribute('title', READ_ONLY_TOOLTIP);

  await page.goto('/demo/reports/rep1');
  await expect(page.locator('[data-provenance-source="Report detail"]')).toHaveText('Demo');
  const exportReport = page.getByRole('button', { name: /export json/i });
  await expect(exportReport).toBeDisabled();
  await expect(exportReport).toHaveAttribute('title', READ_ONLY_TOOLTIP);

  await page.goto('/demo');
  await page.getByText('Mobile testing requires Appium').last().click();
  await expect(page).toHaveURL(/\/demo\/doctor$/);
  await expect(page.locator('[data-provenance-source="Runtime Doctor detail"]')).toHaveText('Demo');
  await expect(page.locator('[data-provenance-source="Runtime Doctor component"]')).toHaveCount(8);

  await page.goto('/demo/connectors');
  await expect(page.locator('[data-provenance-source="Connectors detail"]')).toHaveText('Demo');
  await expect(page.locator('[data-provenance-source="Connector status"]')).toHaveCount(8);
  await expect(page.locator('[data-provenance-source="Connector app"]')).toHaveCount(4);

  await page.goto('/demo/apps/missing-app');
  await expect(page.getByText(DEMO_MESSAGE)).toBeVisible();
  await expect(page.getByText('App not found')).toBeVisible();

  await page.getByRole('button', { name: /open search/i }).click();
  const searchInput = page.getByPlaceholder(/search apps, runs, packs, reports/i);
  await expect(searchInput).toBeDisabled();
  await expect(searchInput).toHaveAttribute('title', READ_ONLY_TOOLTIP);
  expect(apiRequests).toEqual([]);
});
