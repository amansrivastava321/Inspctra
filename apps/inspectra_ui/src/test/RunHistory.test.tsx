import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RunHistoryPanel } from '../components/live-run/history/RunHistoryPanel';
import { WorkspaceModeProvider } from '../state/WorkspaceModeContext';
import type { RunHistoryResponse } from '../types/api';


const citation = (runId: string, stepId: string | null = null, evidenceIds: string[] = []) => ({
  run_id: runId,
  step_id: stepId,
  completed_at: '2026-08-20T10:00:00Z',
  provenance: 'REAL_EXECUTION' as const,
  evidence_ids: evidenceIds,
});

const runItem = (runId: string, outcome: 'passed' | 'failed') => ({
  run_id: runId,
  status: outcome === 'passed' ? 'completed' : 'failed',
  outcome,
  execution_mode: 'automated',
  provenance: 'REAL_EXECUTION' as const,
  started_at: '2026-08-20T09:59:00Z',
  completed_at: '2026-08-20T10:00:00Z',
  created_at: '2026-08-20T09:59:00Z',
  included_in_failure_rate: true,
  exclusion_reason: null,
  citation: citation(runId),
});

const HISTORY: RunHistoryResponse = {
  run_id: 'current-run',
  scope: {
    pack_id: 'pack-1',
    app_target_id: 'app-1',
    terminal_statuses: ['completed', 'failed', 'cancelled'],
    exact_match: true,
    configuration_snapshot_available: false,
  },
  considered_runs: 5,
  excluded_runs: 2,
  exclusions_by_reason: { dry_run: 1, mixed_run_level: 1 },
  insufficient_history: true,
  comparability_warnings: [
    'Historical environment/configuration continuity cannot be verified.',
  ],
  last_passed: runItem('run-pass', 'passed'),
  last_failed: runItem('run-fail', 'failed'),
  failure_rate: {
    failed: 3,
    total: 5,
    value: 0.25,
    citations: [citation('run-pass'), citation('run-fail')],
  },
  step_history: [
    {
      step_id: 'stable-step-1',
      passed: 2,
      failed: 2,
      inconclusive: 1,
      total: 5,
      citations: [citation('run-fail', 'stable-step-1', ['evidence-owned'])],
      insufficient_identity: false,
    },
    {
      step_id: null,
      passed: 0,
      failed: 1,
      inconclusive: 0,
      total: 1,
      citations: [citation('run-legacy')],
      insufficient_identity: true,
    },
  ],
  repeated_failure_signatures: [
    {
      signature: 'signature-1',
      step_id: 'stable-step-1',
      category: 'Timeout',
      error_code: 'navigation_timeout',
      error: 'page timed out',
      failure_reason: 'timeout waiting for page',
      notes: '',
      occurrences: 2,
      citations: [citation('run-fail', 'stable-step-1')],
    },
  ],
  recent_runs: [runItem('run-fail', 'failed'), runItem('run-pass', 'passed')],
  manual_observations: [
    {
      ...runItem('run-manual', 'failed'),
      execution_mode: 'manual',
      included_in_failure_rate: false,
      exclusion_reason: 'manual_execution',
    },
  ],
};

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Bad Request',
    json: async () => data,
  } as Response;
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

function renderHistory(onSelectStep = vi.fn()) {
  return render(
    <MemoryRouter initialEntries={['/runs/current-run']}>
      <WorkspaceModeProvider mode="real">
        <Routes>
          <Route
            path="/runs/:runId"
            element={(
              <>
                <RunHistoryPanel runId="current-run" onSelectStep={onSelectStep} />
                <LocationProbe />
              </>
            )}
          />
        </Routes>
      </WorkspaceModeProvider>
    </MemoryRouter>,
  );
}

describe('deterministic Run History panel', () => {
  beforeEach(() => {
    vi.mocked(fetch).mockReset();
  });

  it('requests bounded run history and shows loading without invented facts', () => {
    vi.mocked(fetch).mockImplementation(() => new Promise<Response>(() => {}));

    renderHistory();

    expect(screen.getByText('Loading historical context…')).toBeInTheDocument();
    expect(screen.queryByText(/comparable real executions failed/i)).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      '/api/runs/current-run/history?limit=20',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('shows backend error without historical fallback values', async () => {
    vi.mocked(fetch).mockResolvedValue(response({ detail: 'bad history request' }, 400));

    renderHistory();

    expect(await screen.findByText('Run history could not be loaded.')).toBeInTheDocument();
    expect(screen.queryByText(/last factual pass/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/comparable real executions failed/i)).not.toBeInTheDocument();
  });

  it('shows an honest empty state when no comparable history exists', async () => {
    vi.mocked(fetch).mockResolvedValue(response({
      ...HISTORY,
      considered_runs: 0,
      excluded_runs: 0,
      exclusions_by_reason: {},
      last_passed: null,
      last_failed: null,
      failure_rate: { failed: 0, total: 0, value: 0, citations: [] },
      step_history: [],
      repeated_failure_signatures: [],
      recent_runs: [],
      manual_observations: [],
      comparability_warnings: [],
    }));

    renderHistory();

    expect(await screen.findByText('No comparable historical runs were found.')).toBeInTheDocument();
  });

  it('renders backend facts, insufficient-history copy, warnings, and exclusions exactly', async () => {
    vi.mocked(fetch).mockResolvedValue(response(HISTORY));

    renderHistory();

    expect(await screen.findByText('Last factual pass')).toBeInTheDocument();
    expect(screen.getByText('Last factual failure')).toBeInTheDocument();
    expect(screen.getByText('3 of 5 comparable real executions failed.')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText(/Not enough comparable real-execution history/i)).toBeInTheDocument();
    expect(screen.queryByText(/trend/i)).not.toBeInTheDocument();
    expect(screen.getByText(HISTORY.comparability_warnings[0])).toBeInTheDocument();
    expect(screen.getByText('5 considered')).toBeInTheDocument();
    expect(screen.getByText('2 excluded')).toBeInTheDocument();
    expect(screen.getByText('dry run · 1')).toBeInTheDocument();
    expect(screen.getByText('mixed run level · 1')).toBeInTheDocument();
  });

  it('keeps manual observations separate from automated failure rate', async () => {
    vi.mocked(fetch).mockResolvedValue(response(HISTORY));

    renderHistory();

    const manual = await screen.findByRole('region', { name: 'Manual observations' });
    expect(manual).toHaveTextContent('run-manual');
    expect(manual).toHaveTextContent('Manual');
    expect(screen.getByText('3 of 5 comparable real executions failed.')).toBeInTheDocument();
  });

  it('renders exact step IDs, counts, citations, and insufficient identity', async () => {
    vi.mocked(fetch).mockResolvedValue(response(HISTORY));
    const onSelectStep = vi.fn();

    renderHistory(onSelectStep);

    expect((await screen.findAllByText('stable-step-1')).length).toBeGreaterThan(0);
    expect(screen.getByText('2 passed')).toBeInTheDocument();
    expect(screen.getByText('2 failed')).toBeInTheDocument();
    expect(screen.getByText('1 inconclusive')).toBeInTheDocument();
    expect(screen.getByText(/Historical identity could not be established/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'Focus step stable-step-1' })[0]);
    expect(onSelectStep).toHaveBeenCalledWith('stable-step-1');
    expect(screen.queryByText(/selector history/i)).not.toBeInTheDocument();
  });

  it('labels exact repeated signatures without claiming a shared cause', async () => {
    vi.mocked(fetch).mockResolvedValue(response(HISTORY));

    renderHistory();

    expect(await screen.findByText('Same deterministic failure signature')).toBeInTheDocument();
    expect(screen.getByText('2 occurrences')).toBeInTheDocument();
    expect(screen.getByText('Timeout')).toBeInTheDocument();
    expect(screen.getByText('timeout waiting for page')).toBeInTheDocument();
    expect(screen.queryByText(/same root cause/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/recurring bug/i)).not.toBeInTheDocument();
  });

  it('navigates run citations and keeps evidence references textual', async () => {
    vi.mocked(fetch).mockResolvedValue(response(HISTORY));

    renderHistory();

    fireEvent.click((await screen.findAllByRole('button', { name: 'Open run run-pass' }))[0]);
    expect(screen.getByTestId('location')).toHaveTextContent('/runs/run-pass');
    const evidenceRef = screen.getByText('evidence evidence-owned');
    expect(evidenceRef.closest('a')).toBeNull();
    expect(evidenceRef.closest('button')).toBeNull();
  });

  it('explains manual/non-real-only history without actions or invented controls', async () => {
    vi.mocked(fetch).mockResolvedValue(response({
      ...HISTORY,
      considered_runs: 0,
      last_passed: null,
      last_failed: null,
      failure_rate: { failed: 0, total: 0, value: 0, citations: [] },
      step_history: [],
      repeated_failure_signatures: [],
      recent_runs: HISTORY.manual_observations,
    }));

    renderHistory();

    expect(await screen.findByText(/No comparable automated real-execution history is available/i)).toBeInTheDocument();
    for (const action of ['Retest', 'Retry', 'Heal Selector', 'Fix', 'Generate with AI', 'Update Test']) {
      expect(screen.queryByRole('button', { name: new RegExp(action, 'i') })).not.toBeInTheDocument();
    }
  });
});
