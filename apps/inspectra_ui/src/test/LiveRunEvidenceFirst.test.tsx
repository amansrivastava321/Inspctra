import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LiveRunDetailPage from '../pages/LiveRunDetailPage';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  generateReport: vi.fn(),
  retestFailed: vi.fn(),
  evaluateRunEvidence: vi.fn(),
  getRunEvaluation: vi.fn().mockResolvedValue([]),
  getRunHistory: vi.fn().mockResolvedValue({
    run_id: 'run-web-1',
    scope: {
      pack_id: 'pack-1', app_target_id: 'app-1',
      terminal_statuses: ['completed', 'failed', 'cancelled'],
      exact_match: true, configuration_snapshot_available: false,
    },
    considered_runs: 0,
    excluded_runs: 0,
    exclusions_by_reason: {},
    insufficient_history: true,
    comparability_warnings: [],
    last_passed: null,
    last_failed: null,
    failure_rate: { failed: 0, total: 0, value: 0, citations: [] },
    step_history: [],
    repeated_failure_signatures: [],
    recent_runs: [],
    manual_observations: [],
  }),
  getRunRootCauseSuggestions: vi.fn().mockResolvedValue({
    analysis_id: '',
    run_id: '',
    authoritative: false,
    inconclusive: false,
    suggestions: [],
  }),
  generateRunRootCauseSuggestions: vi.fn(),
  evidenceDownloadUrl: vi.fn((id: string) => `/api/evidence/${id}/download`),
  runEvidenceZipUrl: vi.fn((id: string) => `/api/runs/${id}/evidence.zip`),
  baselineDownloadUrl: vi.fn((id: string) => `/api/baselines/${id}/download`),
  checkHealth: vi.fn().mockResolvedValue('online'),
  getBackendStatus: vi.fn().mockReturnValue('online'),
  onBackendStatus: vi.fn().mockReturnValue(() => {}),
  ApiError: class ApiError extends Error {},
}));

vi.mock('../api/validationPacks', () => ({
  saveManualStepVerdict: vi.fn(),
  uploadManualEvidence: vi.fn(),
  finalizeManualRun: vi.fn(),
}));

vi.mock('../hooks/useRunStream', () => ({
  useRunStream: () => ({ events: [], connected: false, error: null }),
}));

vi.mock('../hooks/usePermissionRequests', () => ({
  usePermissionRequests: () => ({ pending: [], approve: vi.fn(), deny: vi.fn() }),
}));

import { get } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;

const RUN = {
  id: 'run-web-1',
  pack_id: 'pack-1',
  pack_name: 'Homepage checks',
  app_target_id: 'app-1',
  app_name: 'Example Web',
  status: 'failed',
  execution_mode: 'automated',
  provenance: 'REAL_EXECUTION',
  started_at: '2026-08-14T10:00:00Z',
  completed_at: '2026-08-14T10:00:02Z',
  steps: [
    { step_id: 'step-1', action_type: 'navigate', description: 'Open homepage' },
    { step_id: 'step-2', action_type: 'assert_title_contains', description: 'Check homepage title' },
  ],
  step_results: [
    {
      step: 1, step_id: 'step-1', action_type: 'navigate', status: 'passed',
      notes: 'Opened homepage', duration_ms: 500, provenance: 'REAL_EXECUTION',
    },
    {
      step: 2, step_id: 'step-2', action_type: 'assert_title_contains', status: 'failed',
      failure_reason: "Expected title to contain 'NonExistent' but was 'Example Domain'",
      expected: 'NonExistent', actual: 'Example Domain', duration_ms: 1200,
      started_at: '2026-08-14T10:00:00.800Z', completed_at: '2026-08-14T10:00:02Z',
      evidence_ids: ['shot-1', 'html-1'], provenance: 'REAL_EXECUTION',
    },
  ],
};

const EVIDENCE = [
  {
    id: 'shot-1', run_id: RUN.id, step_id: 'step-2', evidence_type: 'screenshot',
    created_at: '2026-08-14T10:00:02Z', provenance: 'REAL_EXECUTION',
  },
  {
    id: 'html-1', run_id: RUN.id, step_id: 'step-2', evidence_type: 'page_html',
    created_at: '2026-08-14T10:00:02Z', provenance: 'REAL_EXECUTION',
  },
];

const EVENTS = [{
  id: 1, run_id: RUN.id, step_index: 2, step_id: 'step-2',
  event_type: 'evidence_captured', message: 'Evidence captured: screenshot',
  payload: { type: 'screenshot' }, created_at: '2026-08-14T10:00:02Z',
}];

describe('LiveRunDetailPage evidence-first layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path === `/runs/${RUN.id}`) return Promise.resolve(RUN);
      if (path === `/evidence?run_id=${RUN.id}`) return Promise.resolve(EVIDENCE);
      if (path === `/runs/${RUN.id}/events`) return Promise.resolve(EVENTS);
      if (path.startsWith('/baselines')) return Promise.resolve([]);
      return Promise.resolve(null);
    });
  });

  it('selects the failure and leads with its proof and durable history', async () => {
    render(
      <MemoryRouter initialEntries={[`/runs/${RUN.id}`]}>
        <Routes>
          <Route path="/runs/:runId" element={<LiveRunDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Step 2: Check homepage title')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('img', { name: /full-page evidence for step 2/i })).toBeInTheDocument();
    });
    expect(screen.getByText('NonExistent')).toBeInTheDocument();
    expect(screen.getByText('Example Domain')).toBeInTheDocument();
    expect(screen.getByText('Evidence captured: screenshot')).toBeInTheDocument();
    expect(screen.getByText('RUN DURATION')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Historical Context' })).toBeInTheDocument();
    expect(screen.getByText('2.0s')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Download All Evidence/i })).toHaveAttribute(
      'href', `/api/runs/${RUN.id}/evidence.zip`,
    );
  });

  it('clears prior selected failure when navigating to another run with the same step IDs', async () => {
    const previousGet = mockGet.getMockImplementation()!;
    mockGet.mockImplementation((path: string) => {
      if (path === '/runs/historical-pass') return Promise.resolve({
        ...RUN, id: 'historical-pass', app_name: 'Historical passing app', status: 'completed',
        step_results: RUN.step_results.map(result => ({
          ...result, status: 'passed', failure_reason: undefined,
          expected: undefined, actual: undefined, evidence_ids: [],
        })),
      });
      if (path === '/evidence?run_id=historical-pass' || path === '/runs/historical-pass/events') return Promise.resolve([]);
      return previousGet(path);
    });
    render(
      <MemoryRouter initialEntries={[`/runs/${RUN.id}`]}>
        <Link to="/runs/historical-pass">Open historical passing run</Link>
        <Routes><Route path="/runs/:runId" element={<LiveRunDetailPage />} /></Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText('NonExistent')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Open historical passing run' }));
    await screen.findAllByText('Historical passing app');
    await waitFor(() => {
      expect(screen.queryByText('NonExistent')).not.toBeInTheDocument();
      expect(screen.queryByRole('region', { name: 'Failure details' })).not.toBeInTheDocument();
    });
  });
});
