import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'ApiError';
    }
  }
  return {
    get: vi.fn().mockRejectedValue(new ApiError(0, 'Network error')),
    post: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('offline'),
    getBackendStatus: vi.fn().mockReturnValue('offline'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    evidenceDownloadUrl: vi.fn((id: string) => `/api/evidence/${id}/download`),
    baselineDownloadUrl: vi.fn((id: string) => `/api/baselines/${id}/download`),
    reportExportUrl: vi.fn((id: string) => `/api/reports/${id}/export`),
    ApiError,
  };
});

import { get } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const DEMO_MESSAGE = 'Demo Workspace — Sample data for exploration. No real tests are running.';
const READ_ONLY_TOOLTIP = 'Available in your real workspace. Leave demo to get started.';

describe('explicit demo workspace route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    window.history.pushState({}, '', '/demo');
  });

  afterEach(() => cleanup());

  it('renders deterministic demo data without calling the backend', async () => {
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /what broke/i })).toBeInTheDocument();
    expect(screen.getByText('Videomation — Full regression')).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('does not emit transient missing-provenance warnings while demo data initializes', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    await screen.findAllByLabelText('Provenance: Demo');
    expect(warn.mock.calls.flat().join(' ')).not.toMatch(/Missing provenance for Dashboard/);
    warn.mockRestore();
  });

  it.each([
    ['/demo', 'Dashboard summary', 1],
    ['/demo', 'Dashboard failed run', 1],
    ['/demo', 'Dashboard failure reason', 3],
    ['/demo', 'Dashboard screenshot', 1],
    ['/demo/projects', 'App card', 4],
    ['/demo/packs', 'Validation pack row', 6],
    ['/demo/runs', 'Live run row', 2],
    ['/demo/evidence', 'Evidence card', 5],
    ['/demo/reports', 'Report summary', 1],
    ['/demo/doctor', 'Runtime Doctor component', 8],
    ['/demo/connectors', 'Connector status', 8],
    ['/demo/connectors', 'Connector app', 4],
  ])('shows provenance on every repeated surface at %s', async (path, source, count) => {
    window.history.pushState({}, '', path);
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    await waitFor(() => {
      expect(document.querySelectorAll(`[data-provenance-source="${source}"]`)).toHaveLength(count);
    });
  });

  it.each([
    ['/demo/apps/a1', 'App detail'],
    ['/demo/packs/pack-001', 'Validation pack detail'],
    ['/demo/runs/run-001', 'Live run detail'],
    ['/demo/reports/rep1', 'Report detail'],
    ['/demo/doctor', 'Runtime Doctor detail'],
    ['/demo/connectors', 'Connectors detail'],
  ])('shows provenance in the detail header at %s', async (path, source) => {
    window.history.pushState({}, '', path);
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(document.querySelector(`[data-provenance-source="${source}"]`)).toHaveTextContent('Demo');
  });

  it('shows provenance in the evidence detail header', async () => {
    window.history.pushState({}, '', '/demo/evidence');
    render(<App />);

    fireEvent.click((await screen.findAllByText('Screenshot diff'))[0]);
    expect(document.querySelector('[data-provenance-source="Evidence detail"]')).toHaveTextContent('Demo');
  });

  it('keeps demo mode and its banner across sidebar navigation', async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /projects/i }));

    await waitFor(() => expect(window.location.pathname).toBe('/demo/projects'));
    expect(screen.getByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(screen.getByText('Videomation')).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('disables run controls with the approved explanation', async () => {
    render(<App />);

    const runButton = await screen.findByRole('button', { name: /re-run failed pack/i });
    expect(runButton).toBeDisabled();
    expect(runButton).toHaveAttribute('title', READ_ONLY_TOOLTIP);
  });

  it('keeps preview labels visible in the demo workspace', async () => {
    window.history.pushState({}, '', '/demo/projects');
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(screen.getAllByTestId('preview-badge').length).toBeGreaterThanOrEqual(3);
  });

  it('labels demo schedules as preview because scheduling is not active', async () => {
    window.history.pushState({}, '', '/demo/packs');
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(screen.getByText('nightly')).toBeInTheDocument();
    expect(screen.getAllByTitle('Scheduling will be available in a future release.').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('preview-badge').length).toBeGreaterThanOrEqual(8);
  });

  it('disables run-detail mutations in demo mode', async () => {
    window.history.pushState({}, '', '/demo/runs/run-001');
    render(<App />);

    for (const name of [/Retest failed/i, /Generate report/i, /Evaluate evidence with AI/i]) {
      const control = await screen.findByRole('button', { name });
      expect(control).toBeDisabled();
      expect(control).toHaveAttribute('title', READ_ONLY_TOOLTIP);
    }
  });

  it.each([
    ['Investigate', 'Runtime Doctor', '/demo/runtime-doctor'],
    [null, 'Validation Packs', '/demo/packs'],
    [null, 'Live Runs', '/demo/runs'],
    ['Investigate', 'Evidence Center', '/demo/evidence'],
    ['Investigate', 'Reports', '/demo/reports'],
    ['Configure', 'Integrations Preview', '/demo/connectors'],
    ['Configure', 'Models', '/demo/models'],
    ['Configure', 'Settings', '/demo/settings'],
  ])('keeps %s inside the static demo workspace', async (group, label, expectedPath) => {
    render(<App />);

    if (group) {
      fireEvent.click(await screen.findByRole('button', { name: group }));
    }
    fireEvent.click(await screen.findByRole('button', { name: label }));

    await waitFor(() => expect(window.location.pathname).toBe(expectedPath));
    expect(screen.getByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('keeps secondary Memory route accessible without primary navigation clutter', async () => {
    window.history.pushState({}, '', '/demo/memory');
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(window.location.pathname).toBe('/demo/memory');
    expect(mockGet).not.toHaveBeenCalled();
  });

  it.each([
    ['/demo/apps/a1', 'FlowBook'],
    ['/demo/packs/pack-001', 'Daily smoke'],
    ['/demo/runs/run-001', 'Daily smoke'],
    ['/demo/reports/rep1', 'FlowBook is mostly working.'],
  ])('renders static detail data at %s without backend reads', async (path, sampleText) => {
    window.history.pushState({}, '', path);
    render(<App />);

    expect(await screen.findByText(DEMO_MESSAGE)).toBeInTheDocument();
    expect(screen.getAllByText(sampleText).length).toBeGreaterThan(0);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('leaves demo for the equivalent real route', async () => {
    window.history.pushState({}, '', '/demo/projects');
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /^leave demo$/i }));

    await waitFor(() => expect(window.location.pathname).toBe('/projects'));
    expect(screen.queryByText(DEMO_MESSAGE)).not.toBeInTheDocument();
    expect(mockGet).toHaveBeenCalled();
  });

  it('preserves the selected view query when leaving demo', async () => {
    window.history.pushState({}, '', '/demo/runs?mode=manual');
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /^leave demo$/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe('/runs');
      expect(window.location.search).toBe('?mode=manual');
    });
  });
});
