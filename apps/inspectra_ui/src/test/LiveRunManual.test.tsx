import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LiveRunDetailPage from '../pages/LiveRunDetailPage';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Mock api client
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
    evidenceDownloadUrl: vi.fn().mockReturnValue('http://download'),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError: class ApiError extends Error {
      status: number;
      constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
    }
  };
});

// Mock validationPacks API
vi.mock('../api/validationPacks', () => {
  return {
    saveManualStepVerdict: vi.fn(),
    uploadManualEvidence: vi.fn(),
    finalizeManualRun: vi.fn(),
  };
});

// Mock hooks
vi.mock('../hooks/useRunStream', () => ({
  useRunStream: () => ({ events: [], connected: false, error: null })
}));
vi.mock('../hooks/usePermissionRequests', () => ({
  usePermissionRequests: () => ({ pending: [], approve: vi.fn(), deny: vi.fn() })
}));

import { get } from '../api/client';
import { saveManualStepVerdict, finalizeManualRun } from '../api/validationPacks';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockSaveVerdict = saveManualStepVerdict as ReturnType<typeof vi.fn>;
const mockFinalize = finalizeManualRun as ReturnType<typeof vi.fn>;

const MANUAL_RUN = {
  id: 'run-manual-1',
  pack_id: 'pack-1',
  pack_name: 'Smoke Pack',
  app_target_id: 'app-1',
  app_name: 'My Web App',
  status: 'pending',
  execution_mode: 'manual',
  step_results: [],
  steps: [
    {
      step_id: 'step-1',
      action_type: 'navigate',
      target: 'http://example.com',
      description: 'Navigate to homepage',
      optional: false,
    },
    {
      step_id: 'step-2',
      action_type: 'click',
      target: '#submit-btn',
      description: 'Click submit',
      optional: true,
    }
  ]
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/runs/run-manual-1']}>
      <Routes>
        <Route path="/runs/:runId" element={<LiveRunDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LiveRunDetailPage — Manual Execution', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders manual run steps and details', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(MANUAL_RUN);
      if (path.includes('/evidence')) return Promise.resolve([]);
      return Promise.resolve(null);
    });

    renderPage();

    // Verify app & pack names are displayed in header (may appear in multiple places)
    await waitFor(() => {
      expect(screen.getAllByText(/My Web App/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Smoke Pack/i).length).toBeGreaterThan(0);
    });

    // Check timeline shows both steps (appear in timeline + workspace)
    expect(screen.getAllByText(/Step 1: Navigate to homepage/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Step 2: Click submit/i)).toBeInTheDocument();

    // Check active step workspace renders (first step auto-selected)
    // The h2 in the workspace has exact text "Step 1: Navigate to homepage"
    expect(screen.getAllByText(/Step 1:/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/REQUIRED/i).length).toBeGreaterThan(0);

    // Buttons Pass/Fail/Block/Skip should be visible
    expect(screen.getByRole('button', { name: /Pass/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Fail/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Block/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Skip/i })).toBeInTheDocument();
  });

  it('calls saveManualStepVerdict when verdict button is clicked', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(MANUAL_RUN);
      if (path.includes('/evidence')) return Promise.resolve([]);
      return Promise.resolve(null);
    });
    mockSaveVerdict.mockResolvedValue({ ...MANUAL_RUN, step_results: [{ step_id: 'step-1', status: 'passed' }] });

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Pass/i })).toBeInTheDocument();
    });

    // Enter tester name and click Pass
    const testerInput = screen.getByPlaceholderText(/Enter your name/i);
    fireEvent.change(testerInput, { target: { value: 'Tester Bob' } });

    const passBtn = screen.getByRole('button', { name: /Pass/i });
    fireEvent.click(passBtn);

    await waitFor(() => {
      expect(mockSaveVerdict).toHaveBeenCalledWith('run-manual-1', 'step-1', {
        status: 'passed',
        actual_result: '',
        notes: '',
        tester_name: 'Tester Bob',
        failure_reason: undefined,
      });
    });
    await waitFor(() => {
      expect(mockGet.mock.calls.filter(([path]) => String(path).includes('/evidence?run_id=')).length).toBeGreaterThan(1);
      expect(mockGet.mock.calls.filter(([path]) => String(path).endsWith('/events')).length).toBeGreaterThan(1);
    });
  });

  it('shows finalize button disabled until required steps are completed', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(MANUAL_RUN);
      if (path.includes('/evidence')) return Promise.resolve([]);
      return Promise.resolve(null);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Required Steps Remaining/i)).toBeInTheDocument();
    });

    const finalizeBtn = screen.getByTestId('finalize-run-btn');
    expect(finalizeBtn).toBeDisabled();
  });

  it('enables and triggers finalize when required steps are completed', async () => {
    // Return run with required step completed
    const COMPLETED_RUN = {
      ...MANUAL_RUN,
      step_results: [
        {
          step: 1,
          step_id: 'step-1',
          status: 'passed',
          description: 'Navigate to homepage'
        }
      ]
    };

    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(COMPLETED_RUN);
      if (path.includes('/evidence')) return Promise.resolve([]);
      return Promise.resolve(null);
    });
    mockFinalize.mockResolvedValue({ ...COMPLETED_RUN, status: 'completed' });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Run Ready to Finalize/i)).toBeInTheDocument();
    });

    const finalizeBtn = screen.getByTestId('finalize-run-btn');
    expect(finalizeBtn).not.toBeDisabled();

    fireEvent.click(finalizeBtn);

    await waitFor(() => {
      expect(mockFinalize).toHaveBeenCalledWith('run-manual-1');
    });
  });
});
