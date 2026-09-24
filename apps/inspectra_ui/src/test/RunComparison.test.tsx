import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, checkHealth, getRunComparison } from '../api/client';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation, useParams, Route, Routes } from 'react-router-dom';
import { RunComparisonPanel } from '../components/live-run/comparison/RunComparisonPanel';
import { WorkspaceModeProvider } from '../state/WorkspaceModeContext';
import type { LiveRunRecord, RunComparisonResponse, RunStepComparison } from '../types/api';

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, statusText: 'Response', json: async () => data } as Response;
}

beforeEach(async () => {
  vi.mocked(fetch).mockReset().mockResolvedValue(response({}));
  await checkHealth();
  vi.mocked(fetch).mockReset();
});

describe('explicit comparison API', () => {
  it('encodes both IDs and uses the new GET route', async () => {
    vi.mocked(fetch).mockResolvedValue(response({}));
    await getRunComparison('current/one', 'base&two');
    expect(fetch).toHaveBeenCalledWith('/api/runs/current%2Fone/compare?baseline_run_id=base%26two', expect.objectContaining({ method: 'GET' }));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it.each([404, 409, 422, 500])('preserves HTTP %s without retry', async status => {
    vi.mocked(fetch).mockResolvedValue(response({ detail: 'sanitized domain error' }, status));
    await expect(getRunComparison('current', 'base')).rejects.toEqual(new ApiError(status, 'sanitized domain error'));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('preserves the existing single-argument retest API unchanged', async () => {
    vi.mocked(fetch).mockResolvedValue(response({}));
    await getRunComparison('child');
    expect(fetch).toHaveBeenCalledWith('/api/runs/child/comparison', expect.objectContaining({ method: 'GET' }));
  });
});

const run = (id: string, extra: Partial<LiveRunRecord> = {}): LiveRunRecord => ({
  id, pack_id: 'pack', app_target_id: 'app', status: 'completed', execution_mode: 'automated',
  provenance: 'REAL_EXECUTION', completed_at: '2026-09-01T00:00:00Z', step_results: [], ...extra,
});
const CURRENT = run('current', { status: 'failed' });
const observation = (id: string) => ({
  run_id: id, status: 'completed', execution_mode: 'automated', provenance: 'REAL_EXECUTION' as const,
  provenance_basis: 'stored' as const, created_at: null, started_at: null,
  completed_at: '2026-09-01T00:00:00Z', error: null, retest_of: null,
});
const citation = (id: string) => ({ run_id: id, step_id: 'stable-step', provenance: 'REAL_EXECUTION' as const,
  provenance_basis: 'stored' as const, evidence_ids: [`evidence-${id}`] });
const STEP: RunStepComparison = {
  step_id: 'stable-step', identity_state: 'matched', comparison_state: 'factual', reason_codes: [],
  baseline_status: 'passed', comparison_status: 'failed', baseline_provenance: 'REAL_EXECUTION', comparison_provenance: 'REAL_EXECUTION',
  transition: 'passed_to_failed', baseline_citation: citation('base'), comparison_citation: citation('current'),
  baseline_display: null, comparison_display: null,
  metric_comparisons: [
    { key: 'duration_ms', unit: 'ms', baseline_value: 10, comparison_value: 25, delta: 15, reason: null },
    { key: 'response_time_ms', unit: 'ms', baseline_value: null, comparison_value: null, delta: null, reason: 'request_identity_unavailable' },
    { key: 'status_code', unit: 'http_status', baseline_value: 200, comparison_value: 500, delta: null, reason: null },
  ],
  evidence_comparison: { complete: true, baseline_count: 1, comparison_count: 1,
    baseline_type_counts: { screenshot: 1 }, comparison_type_counts: { console_log: 1 }, hash_comparison: 'different_hash' },
  failure_signature_comparison: { algorithm: 'history_v1', state: 'different_signature', reason: null },
};
const COMPARISON: RunComparisonResponse = {
  schema_version: '1', baseline_run_id: 'base', comparison_run_id: 'current', selection_mode: 'explicit',
  scope: { pack_id: 'pack', app_target_id: 'app' }, baseline: observation('base'), comparison: observation('current'),
  chronology: { state: 'forward', basis: 'completed_at', baseline_time: '2026-09-01T00:00:00Z', comparison_time: '2026-09-02T00:00:00Z' },
  provenance_compatibility: 'compatible', comparability: { state: 'partial', configuration_snapshot_available: false, reason_codes: ['configuration_continuity_unknown'] },
  comparability_warnings: ['Execution configuration continuity between these runs cannot be fully verified.'],
  coverage: { complete: true, evidence_limit_per_run: 500, step_limit_per_run: 500, result_bytes_limit_per_run: 2097152, omissions: [] },
  summary_counts: { matched: 1, passed_to_failed: 7, failed_to_passed: 3, passed_to_passed: 5, failed_to_failed: 2,
    inconclusive_transitions: 4, baseline_only: 2, comparison_only: 1, identity_unavailable: 0, identity_conflict: 0, not_comparable: 0 },
  step_comparisons: [STEP],
};

function setup(data = COMPARISON, candidates: LiveRunRecord[] = [run('base'), run('other')]) {
  vi.mocked(fetch).mockImplementation(async input => {
    const url = String(input);
    if (url.startsWith('/api/runs?')) return response(candidates);
    if (url.includes('/compare?')) return response(data);
    throw new Error('Unexpected GET');
  });
}
function renderPanel(current = CURRENT, mode: 'real' | 'demo' = 'real', online = true) {
  return render(<MemoryRouter><WorkspaceModeProvider mode={mode}>
    <RunComparisonPanel run={current} backendAvailable={online} />
  </WorkspaceModeProvider></MemoryRouter>);
}
async function selectReference(id = 'base') {
  const selector = await screen.findByRole('combobox', { name: 'Reference run' });
  await waitFor(() => expect(within(selector).getByRole('option', { name: new RegExp(id) })).toBeInTheDocument());
  fireEvent.change(selector, { target: { value: id } });
}
async function displayed(data = COMPARISON) {
  setup(data);
  renderPanel();
  await selectReference();
  await screen.findByText('Forward comparison');
}

describe('read-only comparison panel', () => {
  it('loads exact metadata candidates but does not compare before selection', async () => {
    setup(); renderPanel();
    expect(await screen.findByRole('option', { name: /base/ })).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('');
    expect(screen.getByText('Choose a reference run to compare recorded execution observations.')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/api/runs?pack_id=pack&limit=200', expect.objectContaining({ method: 'GET' }));
  });

  it.each([
    CURRENT, run('wrong-pack', { pack_id: 'other' }), run('wrong-target', { app_target_id: 'other' }),
    run('active', { status: 'running' }), run('pending', { status: 'pending' }), run('blocked', { status: 'blocked' }),
    run('missing-pack', { pack_id: undefined }), run('missing-target', { app_target_id: undefined }),
  ])('excludes ineligible candidate $id', async candidate => {
    setup(COMPARISON, [run('base'), candidate]); renderPanel();
    const selector = await screen.findByRole('combobox');
    await screen.findByRole('option', { name: /base/ });
    expect(within(selector).getAllByRole('option')).toHaveLength(2);
  });

  it('sends explicit selection and preserves baseline → current direction', async () => {
    await displayed();
    expect(fetch).toHaveBeenCalledWith('/api/runs/current/compare?baseline_run_id=base', expect.objectContaining({ method: 'GET' }));
    expect(screen.getByLabelText('Comparison direction')).toHaveTextContent('Baseline: base → Current: current');
    expect(screen.getByText(/Timestamp basis: completed_at/)).toBeInTheDocument();
    expect(screen.getByText('Execution configuration continuity between these runs cannot be fully verified.')).toBeVisible();
  });

  it.each([
    ['reverse', 'Reverse chronological comparison'], ['same_time', 'Same timestamp'], ['unavailable', 'Chronology unavailable'],
  ] as const)('renders %s chronology without reordering', async (state, label) => {
    setup({ ...COMPARISON, chronology: { ...COMPARISON.chronology, state } }); renderPanel(); await selectReference();
    expect(await screen.findByText(label)).toBeVisible();
    expect(screen.getByLabelText('Comparison direction')).toHaveTextContent('Baseline: base → Current: current');
    if (state === 'reverse') expect(screen.getByText(/This reference run is newer/)).toBeVisible();
  });

  it('distinguishes inferred provenance without a green Real badge', async () => {
    await displayed({ ...COMPARISON, baseline: { ...COMPARISON.baseline, provenance_basis: 'inferred' } });
    const baseline = screen.getByRole('region', { name: 'Baseline observation' });
    expect(within(baseline).getByText(/Inferred provenance/)).toBeVisible();
    expect(within(baseline).queryByLabelText('Provenance: Real')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Current observation' })).getByText(/Stored REAL_EXECUTION/)).toBeVisible();
  });

  it.each(['informational', 'unavailable'] as const)('renders backend %s state', async state => {
    await displayed({ ...COMPARISON, provenance_compatibility: state,
      step_comparisons: [{ ...STEP, comparison_state: state, transition: 'not_comparable', reason_codes: ['manual_observation'] }] });
    expect(screen.getByText(`Provenance compatibility: ${state}`)).toBeVisible();
    expect(screen.getAllByText('Not comparable').length).toBeGreaterThan(0);
  });

  it('displays backend counts rather than recalculating from one row', async () => {
    await displayed();
    expect(screen.getByLabelText('Passed → Failed count')).toHaveTextContent('7');
    expect(screen.getByLabelText('Failed → Passed count')).toHaveTextContent('3');
    expect(screen.queryByText(/regression|fixed/i)).not.toBeInTheDocument();
  });

  it.each([
    ['baseline_only', 'Present only in baseline results'], ['comparison_only', 'Present only in comparison results'],
    ['identity_unavailable', 'Identity unavailable'], ['identity_conflict', 'Identity conflict'],
  ] as const)('renders %s identity without inventing transitions', async (identity_state, label) => {
    await displayed({ ...COMPARISON, step_comparisons: [{ ...STEP, identity_state, transition: 'not_comparable', reason_codes: ['identity_conflict'] }] });
    expect(within(screen.getByRole('table', { name: 'Step comparisons' })).getByText(label)).toBeVisible();
    expect(screen.queryByText(/Removed test|Added test/)).not.toBeInTheDocument();
  });

  it('shows recorded duration and categorical HTTP status, never null as zero', async () => {
    await displayed();
    expect(screen.getByText('Recorded step duration')).toBeVisible();
    expect(screen.getByText('+15 ms')).toBeVisible();
    expect(screen.getByText('200 → 500')).toBeVisible();
    expect(screen.getByText('request_identity_unavailable')).toBeVisible();
    expect(screen.queryByText('0 ms')).not.toBeInTheDocument();
  });

  it.each([
    ['same_signature', 'Same deterministic failure signature'], ['different_signature', 'Different deterministic failure signature'], ['unavailable', 'Unavailable'],
  ] as const)('shows %s signature with persistent limitation', async (state, label) => {
    await displayed({ ...COMPARISON, step_comparisons: [{ ...STEP, failure_signature_comparison: { algorithm: 'history_v1', state, reason: 'signature_input_truncated' } }] });
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByText('Matching failure signatures do not prove the same root cause.')).toBeVisible();
    expect(screen.getByText('history_v1')).toBeVisible();
    expect(screen.getByText('signature_input_truncated')).toBeVisible();
  });

  it('shows cited evidence metadata and partial coverage without fake zero', async () => {
    await displayed({ ...COMPARISON, coverage: { ...COMPARISON.coverage, complete: false, omissions: ['base:evidence_limit_exceeded'] },
      step_comparisons: [{ ...STEP, evidence_comparison: { ...STEP.evidence_comparison, complete: false, baseline_count: null } }] });
    expect(screen.getByText('Comparison coverage is partial.')).toBeVisible();
    expect(screen.getByText('base:evidence_limit_exceeded')).toBeVisible();
    expect(screen.getByText('evidence-base')).toBeVisible();
    expect(screen.getByText(/screenshot: 1/)).toBeVisible();
    expect(screen.queryByText('Baseline evidence: 0')).not.toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });

  it.each([
    [404, 'private stack', 'One of the selected runs could not be found.'],
    [409, 'Comparison requires terminal runs.', 'Comparison is available after both runs finish.'],
    [409, 'Comparison requires the same non-empty pack and app target.', 'These runs are not in the same validation-pack and app-target scope.'],
    [422, 'private stack', 'Select a different valid reference run.'],
    [500, 'private stack', 'Run comparison could not be loaded.'],
  ])('handles %s without exposing server internals', async (status, detail, message) => {
    setup(); renderPanel(); await screen.findByRole('option', { name: /base/ });
    vi.mocked(fetch).mockResolvedValue(response({ detail }, Number(status)));
    await selectReference();
    expect(await screen.findByText(message)).toBeVisible();
    expect(screen.queryByText('private stack')).not.toBeInTheDocument();
  });

  it('handles network failure as offline', async () => {
    setup(); renderPanel(); await screen.findByRole('option', { name: /base/ });
    vi.mocked(fetch).mockRejectedValue(new TypeError('private network text'));
    await selectReference();
    expect(await screen.findByText('Run comparison is unavailable while the backend is offline.')).toBeVisible();
  });

  it('known offline skips all requests', () => {
    setup(); renderPanel(CURRENT, 'real', false);
    expect(screen.getByText('Run comparison is unavailable while the backend is offline.')).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('demo skips candidates and comparisons without sample values', () => {
    setup(); renderPanel(CURRENT, 'demo');
    expect(screen.getByText('Run comparison is unavailable in the demo workspace.')).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('no eligible candidates gives an honest bounded-list empty state', async () => {
    setup(COMPARISON, []); renderPanel();
    expect(await screen.findByText('No comparable terminal reference runs are available.')).toBeVisible();
    expect(screen.getByText(/200 most recent/)).toBeVisible();
  });

  it('active current run cannot start comparison', () => {
    setup(); renderPanel(run('current', { status: 'running' }));
    expect(screen.getByText('Comparison is available after both runs finish.')).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('stale successful response cannot overwrite newer selection', async () => {
    setup(); renderPanel(); await screen.findByRole('option', { name: /base/ });
    let resolveOld!: (r: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
      .mockResolvedValueOnce(response({ ...COMPARISON, baseline_run_id: 'other', baseline: observation('other') }));
    await selectReference();
    expect(screen.getByText('Loading run comparison…')).toBeVisible();
    await selectReference('other');
    await waitFor(() => expect(screen.getByLabelText('Comparison direction')).toHaveTextContent('Baseline: other'));
    await act(async () => { resolveOld(response(COMPARISON)); });
    expect(screen.getByLabelText('Comparison direction')).toHaveTextContent('Baseline: other');
  });

  it('live offline status clears loaded results; reconnect requires explicit selection', async () => {
    await displayed();
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('network offline'));
    await act(async () => { await checkHealth(); });
    expect(screen.getByText('Run comparison is unavailable while the backend is offline.')).toBeVisible();
    expect(screen.queryByLabelText('Comparison direction')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    const comparisons = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes('/compare?')).length;
    vi.mocked(fetch).mockResolvedValueOnce(response({}));
    await act(async () => { await checkHealth(); });
    expect(await screen.findByRole('combobox')).toHaveValue('');
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes('/compare?'))).toHaveLength(comparisons);
  });

  it('offline invalidates a pending comparison even if it later succeeds', async () => {
    setup(); renderPanel(); await screen.findByRole('option', { name: /base/ });
    let resolveOld!: (r: Response) => void;
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    await selectReference();
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('network offline'));
    await act(async () => { await checkHealth(); });
    expect(screen.getByText('Run comparison is unavailable while the backend is offline.')).toBeVisible();
    await act(async () => { resolveOld(response(COMPARISON)); });
    expect(screen.queryByLabelText('Comparison direction')).not.toBeInTheDocument();
    expect(await screen.findByRole('combobox')).toHaveValue('');
  });

  it('citation navigation resets reference selection on destination run', async () => {
    function Routed() {
      const { id } = useParams();
      const location = useLocation();
      return <><output>{location.pathname}</output><RunComparisonPanel run={run(id!)} /></>;
    }
    setup();
    render(<MemoryRouter initialEntries={['/runs/current']}><WorkspaceModeProvider mode="real"><Routes>
      <Route path="/runs/:id" element={<Routed />} />
    </Routes></WorkspaceModeProvider></MemoryRouter>);
    await selectReference();
    fireEvent.click((await screen.findAllByRole('button', { name: 'Open run base' }))[0]);
    expect(await screen.findByText('/runs/base')).toBeVisible();
    expect(screen.queryByLabelText('Comparison direction')).not.toBeInTheDocument();
    expect(await screen.findByRole('combobox')).toHaveValue('');
  });

  it('offers navigation only, uses GET only and renders persisted HTML as text', async () => {
    await displayed({ ...COMPARISON, baseline: { ...COMPARISON.baseline, error: '<img src=x onerror=alert(1)>' } });
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
    expect(screen.queryByRole('button', { name: /retest|retry|re-run|fix|heal|apply|update|generate|promote/i })).not.toBeInTheDocument();
    for (const [, opts] of vi.mocked(fetch).mock.calls) expect(opts?.method).toBe('GET');
  });
});
