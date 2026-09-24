import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AIRootCauseSuggestions } from '../components/live-run/AIRootCauseSuggestions';
import {
  generateRunRootCauseSuggestions,
  getRunRootCauseSuggestions,
} from '../api/client';

class MockApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
  getRunRootCauseSuggestions: vi.fn(),
  generateRunRootCauseSuggestions: vi.fn(),
}));

const mockGet = getRunRootCauseSuggestions as ReturnType<typeof vi.fn>;
const mockGenerate = generateRunRootCauseSuggestions as ReturnType<typeof vi.fn>;

const EMPTY_BATCH = {
  analysis_id: '',
  run_id: 'run-1',
  status: 'inconclusive',
  authoritative: false,
  source_provenance: 'UNAVAILABLE',
  generation_source: 'unavailable',
  generation_metadata: {},
  missing_evidence: ['No root cause suggestions have been generated.'],
  suggestions: [],
  created_at: '2026-09-01T10:00:00Z',
};

const SUGGESTED_BATCH = {
  analysis_id: 'analysis-1',
  run_id: 'run-1',
  status: 'suggested',
  authoritative: false,
  source_provenance: 'REAL_EXECUTION',
  generation_source: 'ollama',
  generation_metadata: { model: 'local-qa' },
  missing_evidence: ['A second browser capture'],
  created_at: '2026-09-01T10:05:00Z',
  suggestions: [{
    suggestion_id: 'suggestion-1',
    analysis_id: 'analysis-1',
    run_id: 'run-1',
    step_id: 'step-2',
    rank: 1,
    title: 'Possible assertion mismatch',
    possible_cause: 'Possible cause: the observed title may differ from the configured expectation.',
    category: 'Assertion failed',
    confidence: 0.35,
    evidence_refs: [
      { type: 'evidence', id: 'ev-1', field: 'content', provenance: 'REAL_EXECUTION' },
      { type: 'step_field', id: 'step-2', field: 'failure_reason', provenance: 'REAL_EXECUTION' },
    ],
    supporting_signals: ['Expected Welcome but observed Login'],
    contradicting_signals: ['No second browser capture is available'],
    missing_evidence: ['A current DOM snapshot'],
    recommended_verification: ['Review the captured page state'],
    suggested_owner_area: 'test_automation',
    source_provenance: 'REAL_EXECUTION',
    generation_source: 'ollama',
    generation_metadata: { model: 'local-qa' },
    authoritative: false,
    created_at: '2026-09-01T10:05:00Z',
  }],
};

function renderPanel(overrides: Record<string, unknown> = {}) {
  return render(
    <AIRootCauseSuggestions
      runId="run-1"
      runStatus="failed"
      hasFailureSignal
      backendAvailable
      isDemo={false}
      {...overrides}
    />,
  );
}

describe('AI root-cause suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(EMPTY_BATCH);
    mockGenerate.mockResolvedValue(SUGGESTED_BATCH);
  });

  it('loads and renders persisted advisory suggestions with grounded details', async () => {
    mockGet.mockResolvedValue(SUGGESTED_BATCH);
    const onSelectStep = vi.fn();

    renderPanel({ onSelectStep });

    expect(await screen.findByText(/Possible assertion mismatch/)).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith('run-1');
    expect(mockGenerate).not.toHaveBeenCalled();
    expect(screen.getByText('AI Possible Causes')).toBeInTheDocument();
    expect(screen.getByText('AI Draft — Possible Cause')).toBeInTheDocument();
    expect(screen.getByText('Non-authoritative')).toBeInTheDocument();
    expect(screen.getByText('This is a hypothesis. It does not change the run verdict or fix the app.')).toBeInTheDocument();
    expect(screen.getByText(/observed title may differ/i)).toBeInTheDocument();
    expect(screen.getByText('35%')).toBeInTheDocument();
    expect(screen.getAllByLabelText('Provenance: Real').length).toBeGreaterThan(0);
    expect(screen.getByText('ollama')).toBeInTheDocument();
    expect(screen.getByText('test automation')).toBeInTheDocument();
    expect(screen.getByText('Expected Welcome but observed Login')).toBeInTheDocument();
    expect(screen.getByText('No second browser capture is available')).toBeInTheDocument();
    expect(screen.getByText('A current DOM snapshot')).toBeInTheDocument();
    expect(screen.getByText('Review the captured page state')).toBeInTheDocument();
    expect(screen.getByText('ev-1 · content')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /step-2 · failure_reason/i }));
    expect(onSelectStep).toHaveBeenCalledWith('step-2');

    for (const forbidden of ['Apply Fix', 'Apply Verdict', 'Fix Selector', 'Rerun', 'Generate Patch']) {
      expect(screen.queryByRole('button', { name: new RegExp(forbidden, 'i') })).not.toBeInTheDocument();
    }
  });

  it('does not generate on mount and generates only after explicit click', async () => {
    renderPanel();

    const button = await screen.findByRole('button', { name: 'Suggest possible causes' });
    expect(mockGenerate).not.toHaveBeenCalled();
    fireEvent.click(button);

    await waitFor(() => expect(mockGenerate).toHaveBeenCalledWith('run-1'));
    expect(await screen.findByText(/Possible assertion mismatch/)).toBeInTheDocument();
  });

  it('shows a disabled generating state while POST is pending', async () => {
    let resolveGeneration!: (value: unknown) => void;
    mockGenerate.mockReturnValue(new Promise(resolve => { resolveGeneration = resolve; }));
    renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Suggest possible causes' }));

    expect(screen.getByText('Analyzing available evidence…')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyzing available evidence…' })).toBeDisabled();
    resolveGeneration(SUGGESTED_BATCH);
    expect(await screen.findByText(/Possible assertion mismatch/)).toBeInTheDocument();
  });

  it('renders an honest inconclusive state without placeholder hypotheses', async () => {
    mockGet.mockResolvedValue({
      ...EMPTY_BATCH,
      analysis_id: 'analysis-empty',
      generation_source: 'local_fallback',
      missing_evidence: ['No failed-step artifact was captured'],
    });

    renderPanel();

    expect(await screen.findByText('Insufficient evidence to suggest a reliable possible cause.')).toBeInTheDocument();
    expect(screen.getByText('No failed-step artifact was captured')).toBeInTheDocument();
    expect(screen.queryByText(/observed title may differ/i)).not.toBeInTheDocument();
  });

  it('prevents generation for active runs', async () => {
    renderPanel({ runStatus: 'running' });

    expect(await screen.findByText('Possible-cause analysis is available after the run finishes.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Suggest possible causes' })).not.toBeInTheDocument();
    expect(mockGenerate).not.toHaveBeenCalled();
  });

  it('prevents generation for pass-only terminal runs', async () => {
    renderPanel({ runStatus: 'completed', hasFailureSignal: false });

    expect(await screen.findByText('No failure signal is available for root-cause analysis.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Suggest possible causes' })).not.toBeInTheDocument();
  });

  it('maps backend 409 conflict states to safe copy', async () => {
    mockGenerate.mockRejectedValueOnce(new MockApiError(409, 'run is still in progress'));
    const { unmount } = renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Suggest possible causes' }));
    expect(await screen.findByText('Possible-cause analysis is available after the run finishes.')).toBeInTheDocument();

    unmount();
    mockGet.mockResolvedValue(EMPTY_BATCH);
    mockGenerate.mockRejectedValueOnce(new MockApiError(409, 'no failure signal'));
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Suggest possible causes' }));
    expect(await screen.findByText('No failure signal is available for root-cause analysis.')).toBeInTheDocument();
  });

  it('sanitizes server failures and handles missing analyses', async () => {
    mockGet.mockRejectedValueOnce(new MockApiError(404, 'secret internal path'));
    const { unmount } = renderPanel();
    expect(await screen.findByText('Possible-cause analysis is unavailable for this run.')).toBeInTheDocument();
    expect(screen.queryByText(/secret internal path/i)).not.toBeInTheDocument();

    unmount();
    mockGet.mockResolvedValue(EMPTY_BATCH);
    mockGenerate.mockRejectedValueOnce(new MockApiError(500, 'Bearer secret-server-token'));
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Suggest possible causes' }));
    expect(await screen.findByText('Possible-cause analysis could not be generated.')).toBeInTheDocument();
    expect(screen.queryByText(/secret-server-token/i)).not.toBeInTheDocument();
  });

  it('does not call the backend and disables generation in demo or offline state', async () => {
    const { unmount } = renderPanel({ isDemo: true });
    expect(await screen.findByRole('button', { name: 'Suggest possible causes' })).toBeDisabled();
    expect(mockGet).not.toHaveBeenCalled();

    unmount();
    renderPanel({ backendAvailable: false });
    expect(await screen.findByRole('button', { name: 'Suggest possible causes' })).toBeDisabled();
    expect(mockGet).not.toHaveBeenCalled();
  });
});
