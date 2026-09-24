import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LiveRunDetailPage from '../pages/LiveRunDetailPage';
import ReportDetailPage from '../pages/ReportDetailPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../api/client', () => {
  return {
    get: vi.fn(),
    post: vi.fn(),
    generateReport: vi.fn(),
    retestFailed: vi.fn(),
    getRunHistory: vi.fn().mockResolvedValue(null),
    getRunRootCauseSuggestions: vi.fn().mockResolvedValue({
      analysis_id: '',
      run_id: '',
      authoritative: false,
      inconclusive: false,
      suggestions: [],
    }),
    generateRunRootCauseSuggestions: vi.fn(),
    reportExportUrl: vi.fn().mockReturnValue('/api/reports/report-1/export'),
    evidenceDownloadUrl: vi.fn().mockReturnValue('/api/evidence/ev-1/download'),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError: class ApiError extends Error {},
  };
});

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

const API_RUN = {
  id: 'run-api-1',
  pack_id: 'pack-1',
  pack_name: 'API Pack',
  app_target_id: 'app-1',
  app_name: 'Backend API',
  status: 'failed',
  execution_mode: 'automated',
  step_results: [
    {
      step: 1,
      step_id: 'step-api-1',
      action_type: 'api_request',
      status: 'passed',
      notes: 'GET returned 200.',
      method: 'GET',
      url: 'http://127.0.0.1:8765/api/health',
      status_code: 200,
      response_time_ms: 14,
      evidence_ids: ['ev-req', 'ev-res'],
    },
    {
      step: 2,
      step_id: 'step-api-2',
      action_type: 'assert_status',
      status: 'failed',
      notes: 'Assertion failed: expected 201, got 200',
      assertion_result: false,
      failure_reason: 'Assertion failed: expected 201, got 200',
      evidence_ids: ['ev-assert'],
    },
  ],
};

const API_EVIDENCE = [
  {
    id: 'ev-req',
    run_id: 'run-api-1',
    step_id: 'step-api-1',
    evidence_type: 'api_request',
    title: 'API Request',
    description: 'Outgoing request summary',
    metadata_json: {
      method: 'GET',
      url: 'http://127.0.0.1:8765/api/health',
      headers: { Authorization: '[REDACTED]' },
    },
    created_at: new Date().toISOString(),
  },
  {
    id: 'ev-res',
    run_id: 'run-api-1',
    step_id: 'step-api-1',
    evidence_type: 'api_response',
    title: 'API Response',
    description: 'Incoming response summary',
    metadata_json: {
      status_code: 200,
      response_time_ms: 14,
      headers: { 'set-cookie': '[REDACTED]' },
    },
    created_at: new Date().toISOString(),
  },
  {
    id: 'ev-assert',
    run_id: 'run-api-1',
    step_id: 'step-api-2',
    evidence_type: 'api_assertion',
    title: 'API Assertion',
    description: 'Assertion result',
    metadata_json: {
      passed: false,
      details: 'expected 201, got 200',
    },
    created_at: new Date().toISOString(),
  },
];

const API_REPORT = {
  id: 'report-1',
  run_id: 'run-api-1',
  app_name: 'Backend API',
  pack_name: 'API Pack',
  verdict: 'fail',
  summary: '1 API assertion failed.',
  pass_count: 1,
  fail_count: 1,
  unclear_count: 0,
  evidence_count: 3,
  api_step_count: 2,
  api_pass_count: 1,
  api_fail_count: 1,
  api_avg_response_time_ms: 14,
  findings: [],
};

function renderRunPage() {
  return render(
    <MemoryRouter initialEntries={['/runs/run-api-1']}>
      <Routes>
        <Route path="/runs/:runId" element={<LiveRunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderReportPage() {
  return render(
    <MemoryRouter initialEntries={['/reports/report-1']}>
      <Routes>
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('API run UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows API evidence card details with redacted headers and failed assertion reason', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(API_RUN);
      if (path.includes('/evidence')) return Promise.resolve(API_EVIDENCE);
      return Promise.resolve(null);
    });

    renderRunPage();

    await waitFor(() => {
      expect(screen.getByText(/Backend API/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/GET returned 200/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Assertion failed: expected 201, got 200/i).length).toBeGreaterThan(0);

    // Failed steps are selected first. Select the request step to inspect its
    // own request/response evidence and verify sensitive headers stay redacted.
    fireEvent.click(screen.getByLabelText(/Step 1 status: passed/i));
    await waitFor(() => {
      expect(screen.getAllByText(/\[REDACTED\]/i).length).toBeGreaterThan(0);
    });
    expect(screen.getByText(/response_time_ms/i)).toBeInTheDocument();
  });

  it('report detail shows API summary metrics', async () => {
    mockGet.mockResolvedValue(API_REPORT);

    renderReportPage();

    await waitFor(() => {
      expect(screen.getByText(/API STEPS/i)).toBeInTheDocument();
    });

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/AVG API MS/i)).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
  });
});
