import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardPage from '../pages/DashboardPage';
import { WorkspaceModeProvider } from '../state/WorkspaceModeContext';

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
    get: vi.fn(),
    post: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    evidenceDownloadUrl: vi.fn((id: string) => `/api/evidence/${id}/download`),
    ApiError,
  };
});

import { ApiError, checkHealth, get, post } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockCheckHealth = checkHealth as ReturnType<typeof vi.fn>;

const DAYS = [
  { date: '2026-08-08', passed: 0, failed: 0, total: 0, pass_rate: null, provenance: 'UNAVAILABLE' },
  { date: '2026-08-09', passed: 1, failed: 0, total: 1, pass_rate: 100, provenance: 'REAL_EXECUTION' },
  { date: '2026-08-10', passed: 1, failed: 1, total: 2, pass_rate: 50, provenance: 'REAL_EXECUTION' },
  { date: '2026-08-11', passed: 0, failed: 0, total: 0, pass_rate: null, provenance: 'UNAVAILABLE' },
  { date: '2026-08-12', passed: 2, failed: 0, total: 2, pass_rate: 100, provenance: 'REAL_EXECUTION' },
  { date: '2026-08-13', passed: 1, failed: 0, total: 1, pass_rate: 100, provenance: 'REAL_EXECUTION' },
  { date: '2026-08-14', passed: 0, failed: 1, total: 1, pass_rate: 0, provenance: 'REAL_EXECUTION' },
] as const;

const FAILURE_SUMMARY = {
  project_count: 2,
  app_target_count: 3,
  validation_pack_count: 4,
  total_runs: 9,
  runs_completed: 7,
  runs_failed: 2,
  runs_running: 0,
  recent_runs: [],
  projects_count: 2,
  apps_count: 3,
  packs_count: 4,
  total_runs_7d: 7,
  passed_runs_7d: 5,
  recent_failed_run: {
    id: 'run-failed',
    pack_id: 'pack-smoke',
    app_target_id: 'app-smoke',
    app_name: 'Smoke App',
    pack_name: 'Homepage Title Check',
    failure_reason: "Assertion failed: expected 'Welcome' but found 'Login'",
    failed_at: '2026-08-14T10:30:00Z',
    provenance: 'REAL_EXECUTION',
    screenshot_evidence_id: 'shot-1',
    screenshot_provenance: 'REAL_EXECUTION',
  },
  failure_reasons: [
    { category: 'Timeout', count: 4, run_ids: ['r1', 'r2', 'r3', 'r4'], provenance: 'REAL_EXECUTION' },
    { category: 'Assertion failed', count: 2, run_ids: ['r5', 'run-failed'], provenance: 'REAL_EXECUTION' },
    { category: 'HTTP 5xx', count: 1, run_ids: ['r6'], provenance: 'REAL_EXECUTION' },
  ],
  pass_rate_7d: DAYS,
  coverage: {
    with_packs: 2,
    total: 3,
    percentage: 66.7,
    last_pack_created_at: '2026-08-12T08:00:00Z',
    provenance: 'REAL_EXECUTION',
  },
  last_run_at: '2026-08-14T10:30:00Z',
  last_run_provenance: 'REAL_EXECUTION',
  generated_at: '2026-08-14T12:00:00Z',
  provenance: 'REAL_EXECUTION',
} as const;

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderPage({ mode = 'real', path = '/' }: { mode?: 'real' | 'demo'; path?: string } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <WorkspaceModeProvider mode={mode}>
        <DashboardPage />
        <LocationProbe />
      </WorkspaceModeProvider>
    </MemoryRouter>,
  );
}

describe('Actionable Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCheckHealth.mockResolvedValue('online');
  });

  it('answers what broke with the latest exact failure and evidence', async () => {
    mockGet.mockResolvedValue(FAILURE_SUMMARY);
    renderPage();

    expect(await screen.findByRole('heading', { name: /what broke/i })).toBeInTheDocument();
    expect(screen.getByText('Smoke App — Homepage Title Check')).toBeInTheDocument();
    expect(screen.getByText(FAILURE_SUMMARY.recent_failed_run.failure_reason)).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getAllByLabelText('Provenance: Real').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /view details/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /investigate evidence/i })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /failure screenshot/i })).toHaveAttribute(
      'src',
      '/api/evidence/shot-1/download',
    );
  });

  it('answers why with normalized reasons and seven explicit days', async () => {
    mockGet.mockResolvedValue(FAILURE_SUMMARY);
    renderPage();

    expect(await screen.findByRole('heading', { name: /why/i })).toBeInTheDocument();
    expect(screen.getByText('Timeout')).toBeInTheDocument();
    expect(screen.getByText('4 times')).toBeInTheDocument();
    expect(screen.getAllByTestId('pass-rate-day')).toHaveLength(7);
    expect(screen.getByLabelText(/2026-08-08.*no runs/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/2026-08-14.*0% pass rate/i)).toBeInTheDocument();
  });

  it('reruns the entire failed pack and navigates to the new run', async () => {
    mockGet.mockResolvedValue(FAILURE_SUMMARY);
    mockPost.mockResolvedValue({ id: 'run-new' });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /re-run failed pack/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-smoke/runs', {
        app_target_id: 'app-smoke',
        execution_mode: 'automated',
      });
      expect(screen.getByTestId('location')).toHaveTextContent('/runs/run-new');
    });
  });

  it('shows screenshot placeholders for API-only and missing artifacts', async () => {
    mockGet.mockResolvedValue({
      ...FAILURE_SUMMARY,
      recent_failed_run: { ...FAILURE_SUMMARY.recent_failed_run, screenshot_evidence_id: null },
    });
    const view = renderPage();
    expect(await screen.findByText('No screenshot captured')).toBeInTheDocument();

    view.unmount();
    mockGet.mockResolvedValue(FAILURE_SUMMARY);
    renderPage();
    fireEvent.error(await screen.findByRole('img', { name: /failure screenshot/i }));
    expect(screen.getByText('Screenshot unavailable')).toBeInTheDocument();
  });

  it('shows all-clear and persisted coverage when no recent failure exists', async () => {
    mockGet.mockResolvedValue({
      ...FAILURE_SUMMARY,
      recent_failed_run: null,
      failure_reasons: [],
      total_runs: 8,
      total_runs_7d: 5,
      passed_runs_7d: 5,
      last_run_at: '2026-08-14T09:00:00Z',
    });
    renderPage();

    expect(await screen.findByText('All systems clear')).toBeInTheDocument();
    expect(screen.getByText('5 runs passed in the last 7 days')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /coverage overview/i })).toBeInTheDocument();
    expect(screen.getByText('2 of 3 apps have validation packs')).toBeInTheDocument();
    expect(screen.getAllByText('Projects').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Apps').length).toBeGreaterThan(0);
    expect(screen.getByText('Validation packs')).toBeInTheDocument();
  });

  it('shows an honest empty workspace with onboarding actions', async () => {
    mockGet.mockResolvedValue({
      ...FAILURE_SUMMARY,
      project_count: 0,
      app_target_count: 0,
      validation_pack_count: 0,
      total_runs: 0,
      projects_count: 0,
      apps_count: 0,
      packs_count: 0,
      total_runs_7d: 0,
      passed_runs_7d: 0,
      recent_failed_run: null,
      failure_reasons: [],
      last_run_at: null,
      coverage: { ...FAILURE_SUMMARY.coverage, with_packs: 0, total: 0, percentage: null },
    });
    renderPage();

    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    expect(screen.getByText('Create your first validation pack to start testing')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create your first pack/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /connect an app/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /try demo/i }).length).toBeGreaterThan(0);
  });

  it('does not call an in-progress-only workspace all clear', async () => {
    mockGet.mockResolvedValue({
      ...FAILURE_SUMMARY,
      total_runs: 1,
      total_runs_7d: 0,
      passed_runs_7d: 0,
      recent_failed_run: null,
      failure_reasons: [],
      last_run_at: null,
    });
    renderPage();

    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    expect(screen.queryByText('All systems clear')).not.toBeInTheDocument();
  });

  it('shows only the offline hero when the backend is unreachable', async () => {
    mockGet.mockRejectedValue(new (ApiError as any)(0, 'Network error'));
    renderPage();

    expect((await screen.findAllByText('Backend offline')).length).toBeGreaterThan(0);
    expect(screen.getByText('Connect to your workspace to see test results.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry connection/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /try demo/i }).length).toBeGreaterThan(0);
    expect(screen.queryByText('Coverage Overview')).not.toBeInTheDocument();
    expect(screen.queryByText('Failure breakdown')).not.toBeInTheDocument();
  });

  it('recognizes a Vite proxy 500 as offline after a failed health probe', async () => {
    mockGet.mockRejectedValue(new (ApiError as any)(500, '500 Internal Server Error'));
    mockCheckHealth.mockResolvedValue('offline');
    renderPage();

    expect(await screen.findByText('Connect to your workspace to see test results.')).toBeInTheDocument();
    expect(mockCheckHealth).toHaveBeenCalled();
    expect(screen.queryByText('500 Internal Server Error')).not.toBeInTheDocument();
  });

  it('renders deterministic demo facts with demo provenance and disabled writes', async () => {
    renderPage({ mode: 'demo', path: '/demo' });

    expect(await screen.findByText(/demo workspace — sample data/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /what broke/i })).toBeInTheDocument();
    expect(screen.getAllByLabelText('Provenance: Demo').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /re-run failed pack/i })).toBeDisabled();
    expect(mockGet).not.toHaveBeenCalled();
  });
});
