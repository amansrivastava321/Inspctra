import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LiveRunDetailPage from '../pages/LiveRunDetailPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  generateReport: vi.fn(),
  retestFailed: vi.fn(),
  evaluateRunEvidence: vi.fn(),
  getRunEvaluation: vi.fn(),
  getRunHistory: vi.fn().mockResolvedValue(null),
  getRunRootCauseSuggestions: vi.fn(),
  generateRunRootCauseSuggestions: vi.fn(),
  evidenceDownloadUrl: vi.fn().mockReturnValue('/api/evidence/ev-1/download'),
  baselineDownloadUrl: vi.fn().mockReturnValue('/api/baselines/base-1/download'),
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

import { get, evaluateRunEvidence, getRunEvaluation, getRunRootCauseSuggestions } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockEvaluateRunEvidence = evaluateRunEvidence as ReturnType<typeof vi.fn>;
const mockGetRunEvaluation = getRunEvaluation as ReturnType<typeof vi.fn>;
const mockGetRootCause = getRunRootCauseSuggestions as ReturnType<typeof vi.fn>;

const RUN = {
  id: 'run-ai-1',
  pack_id: 'pack-1',
  pack_name: 'Checkout Pack',
  app_target_id: 'app-1',
  app_name: 'Checkout UI',
  status: 'failed',
  execution_mode: 'automated',
  step_results: [
    {
      step: 1,
      step_id: 'step-1',
      action_type: 'assert_text',
      status: 'failed',
      notes: 'Expected confirmation text did not appear.',
      failure_reason: 'Missing confirmation text',
      evidence_ids: ['ev-1'],
    },
  ],
};

const EVIDENCE = [
  {
    id: 'ev-1',
    run_id: 'run-ai-1',
    step_id: 'step-1',
    evidence_type: 'log',
    title: 'Run log',
    metadata_json: {},
    created_at: '2026-06-19T10:00:00Z',
  },
];

const NOTE = {
  evaluation_id: 'eval-1',
  run_id: 'run-ai-1',
  step_id: 'step-1',
  verdict_assessment: 'Evidence suggests the failure is likely real.',
  suggested_verdict: 'failed',
  confidence: 0.82,
  summary: 'Confirmation text is absent in the captured evidence.',
  evidence_used: ['Run log', 'Failed step note'],
  missing_evidence: ['DOM snapshot'],
  risk_flags: ['Possible flaky selector'],
  rationale: 'Only textual evidence is present. No DOM capture exists to confirm selector state.',
  generation_source: 'ai:evidence-evaluator',
  generation_metadata: { model: 'local-draft' },
  created_at: '2026-06-19T10:05:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/runs/run-ai-1']}>
      <Routes>
        <Route path="/runs/:runId" element={<LiveRunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AI evidence evaluation UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/runs/')) return Promise.resolve(RUN);
      if (path.includes('/evidence')) return Promise.resolve(EVIDENCE);
      return Promise.resolve(null);
    });
    mockGetRootCause.mockResolvedValue({
      analysis_id: '', run_id: 'run-ai-1', status: 'inconclusive', authoritative: false,
      source_provenance: 'UNAVAILABLE', generation_source: 'unavailable', generation_metadata: {},
      missing_evidence: ['No root cause suggestions have been generated.'], suggestions: [],
      created_at: '2026-09-01T10:00:00Z',
    });
  });

  it('places AI possible causes directly after AI evaluation notes', async () => {
    mockGetRunEvaluation.mockResolvedValue([NOTE]);

    renderPage();

    const evaluation = await screen.findByText('AI Evaluation Notes');
    const possibleCauses = await screen.findByText('AI Possible Causes');
    expect(evaluation.compareDocumentPosition(possibleCauses) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(mockGetRootCause).toHaveBeenCalledWith('run-ai-1');
  });

  it('renders evaluate evidence button and loads existing notes', async () => {
    mockGetRunEvaluation.mockResolvedValue([NOTE]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Evaluate evidence with AI/i })).toBeInTheDocument();
    });

    expect(mockGetRunEvaluation).toHaveBeenCalledWith('run-ai-1');
    expect(screen.getByText(/AI Evaluation Notes/i)).toBeInTheDocument();
    expect(screen.getByText(/AI Draft — Non-Authoritative/i)).toBeInTheDocument();
    expect(screen.getByText(/This does not change the actual run verdict\./i)).toBeInTheDocument();
  });

  it('renders confidence, rationale, evidence used, and missing evidence', async () => {
    mockGetRunEvaluation.mockResolvedValue([NOTE]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/82%/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Only textual evidence is present/i)).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === 'evidence_used: Run log, Failed step note')).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === 'missing_evidence: DOM snapshot')).toBeInTheDocument();
  });

  it('clicking evaluate calls endpoint and refreshes notes', async () => {
    mockGetRunEvaluation
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([NOTE]);
    mockEvaluateRunEvidence.mockResolvedValue([NOTE]);

    renderPage();

    const button = await screen.findByRole('button', { name: /Evaluate evidence with AI/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockEvaluateRunEvidence).toHaveBeenCalledWith('run-ai-1');
    });
    await waitFor(() => {
      expect(mockGetRunEvaluation).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText(/Evidence suggests the failure is likely real\./i)).toBeInTheDocument();
  });

  it('renders evaluation error state', async () => {
    mockGetRunEvaluation.mockResolvedValue([]);
    mockEvaluateRunEvidence.mockRejectedValue(new Error('evaluation failed'));

    renderPage();

    const button = await screen.findByRole('button', { name: /Evaluate evidence with AI/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/evaluation failed/i)).toBeInTheDocument();
    });
  });

  it('does not expose apply verdict action', async () => {
    mockGetRunEvaluation.mockResolvedValue([NOTE]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/AI Evaluation Notes/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /Apply verdict/i })).not.toBeInTheDocument();
  });
});
