import { useEffect, useState } from 'react';
import { GitCompareArrows } from 'lucide-react';
import { ApiError, get, getBackendStatus, getRunComparison, onBackendStatus } from '../../../api/client';
import { P } from '../../../design/tokens';
import { useWorkspaceMode, useWorkspaceNavigate } from '../../../state/WorkspaceModeContext';
import type { LiveRunRecord, RunComparisonResponse } from '../../../types/api';
import { Card } from '../../layout/AppShell';
import { RunComparisonResults } from './RunComparisonResults';

interface Props { run: LiveRunRecord; backendAvailable?: boolean; }
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
const OFFLINE = 'Run comparison is unavailable while the backend is offline.';
const ACTIVE = 'Comparison is available after both runs finish.';
const SCOPE = 'These runs are not in the same validation-pack and app-target scope.';

function errorCopy(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Run comparison could not be loaded.';
  if (error.status === 0) return OFFLINE;
  if (error.status === 404) return 'One of the selected runs could not be found.';
  if (error.status === 409) return error.message === 'Comparison requires terminal runs.' ? ACTIVE : SCOPE;
  if (error.status === 422) return 'Select a different valid reference run.';
  return 'Run comparison could not be loaded.';
}

/** Remount on identity/scope/workspace changes, independently of parent routing. */
export function RunComparisonPanel({ run, backendAvailable = true }: Props) {
  const { isDemo } = useWorkspaceMode();
  const [connection, setConnection] = useState(getBackendStatus);
  useEffect(() => onBackendStatus(setConnection), []);
  const available = backendAvailable && connection !== 'offline';
  return <Card><section aria-label="Run Comparison" style={{ display: 'grid', gap: 10, color: P.textDim, fontSize: 11, minWidth: 0 }}>
    <h3 style={{ margin: 0, fontSize: 12, color: P.text, display: 'flex', alignItems: 'center', gap: 6 }}><GitCompareArrows size={14} aria-hidden />Run Comparison</h3>
    <ComparisonState key={JSON.stringify([run.id, run.pack_id, run.app_target_id, run.status, isDemo, available])}
      run={run} isDemo={isDemo} backendAvailable={available} />
  </section></Card>;
}

function ComparisonState({ run, isDemo, backendAvailable }: Props & { isDemo: boolean }) {
  const nav = useWorkspaceNavigate();
  const [candidates, setCandidates] = useState<LiveRunRecord[] | null>(null);
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const [selected, setSelected] = useState('');
  const [data, setData] = useState<RunComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scopeAvailable = Boolean(run.pack_id?.trim() && run.app_target_id?.trim());
  const enabled = !isDemo && backendAvailable && TERMINAL.has(run.status) && scopeAvailable;

  useEffect(() => {
    if (!enabled) return;
    let current = true;
    get<LiveRunRecord[]>(`/runs?pack_id=${encodeURIComponent(run.pack_id!)}&limit=200`).then(runs => {
      if (!current) return;
      setCandidates(runs.filter(item => item.id !== run.id && Boolean(item.id) && TERMINAL.has(item.status)
        && item.pack_id === run.pack_id && item.app_target_id === run.app_target_id));
    }).catch(err => { if (current) setCandidateError(errorCopy(err)); });
    return () => { current = false; };
  }, [enabled, run.id, run.pack_id, run.app_target_id]);

  useEffect(() => {
    if (!enabled || !selected) return;
    let current = true;
    getRunComparison(run.id, selected).then(result => {
      if (!current) return;
      if (result.baseline_run_id !== selected || result.comparison_run_id !== run.id) {
        setError('Run comparison could not be loaded.');
        return;
      }
      setData(result);
    }).catch(err => { if (current) setError(errorCopy(err)); });
    return () => { current = false; };
  }, [enabled, run.id, selected]);

  if (isDemo) return <div role="status">Run comparison is unavailable in the demo workspace.</div>;
  if (!backendAvailable) return <div role="status">{OFFLINE}</div>;
  if (!TERMINAL.has(run.status)) return <div role="status">{ACTIVE}</div>;
  if (!scopeAvailable) return <div role="status">Comparison scope is unavailable for this run.</div>;
  if (candidateError) return <div role="alert">{candidateError}</div>;
  if (!candidates) return <div role="status">Loading reference runs…</div>;

  return <>
    <p style={{ margin: 0, color: P.textMute }}>Reference choices use up to 200 most recent runs in this pack.</p>
    {candidates.length === 0 ? <div role="status">No comparable terminal reference runs are available.</div> : <>
      <label htmlFor={`reference-${run.id}`}>Reference run</label>
      <select id={`reference-${run.id}`} value={selected} onChange={event => {
        setData(null); setError(null); setSelected(event.target.value);
      }} style={{ maxWidth: '100%', width: '100%', background: P.cardHi, color: P.text, border: `1px solid ${P.borderHi}`, borderRadius: 6, padding: 8 }}>
        <option value="">Choose a reference run</option>
        {candidates.map(candidate => <option key={candidate.id} value={candidate.id} title={candidate.id}>
          {candidate.id.slice(0, 12)} · {candidate.status} · {candidate.completed_at ?? candidate.started_at ?? candidate.created_at ?? 'Time unavailable'} · {candidate.execution_mode ?? 'Mode unavailable'} · {candidate.provenance ?? 'UNAVAILABLE'}
        </option>)}
      </select>
      <div style={{ color: P.textMute }}>Choose a persisted terminal run to compare with this run.</div>
      <div style={{ color: P.textMute }}>Candidate provenance basis is unavailable until comparison loads.</div>
      {!selected ? <div role="status">Choose a reference run to compare recorded execution observations.</div>
        : error ? <div role="alert">{error}</div>
          : !data ? <div role="status">Loading run comparison…</div>
            : <RunComparisonResults data={data} onOpenRun={id => nav(`/runs/${encodeURIComponent(id)}`)} />}
    </>}
  </>;
}
