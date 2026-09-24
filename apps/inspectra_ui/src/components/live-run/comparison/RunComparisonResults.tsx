import { P } from '../../../design/tokens';
import type { RunComparisonObservation, RunComparisonResponse, RunComparisonSummaryCounts } from '../../../types/api';
import { ComparisonProvenance, identityLabels, RunLink, transitionLabels } from './ComparisonDetails';
import { StepComparisonTable } from './StepComparisonTable';

const countLabels: Record<keyof RunComparisonSummaryCounts, string> = {
  matched: 'Matched', passed_to_failed: transitionLabels.passed_to_failed, failed_to_passed: transitionLabels.failed_to_passed,
  passed_to_passed: transitionLabels.passed_to_passed, failed_to_failed: transitionLabels.failed_to_failed,
  inconclusive_transitions: 'Inconclusive transitions', baseline_only: identityLabels.baseline_only, comparison_only: identityLabels.comparison_only,
  identity_unavailable: identityLabels.identity_unavailable, identity_conflict: identityLabels.identity_conflict, not_comparable: 'Not comparable',
};
const chronologyLabels = { forward: 'Forward comparison', reverse: 'Reverse chronological comparison', same_time: 'Same timestamp', unavailable: 'Chronology unavailable' };

function Observation({ data, label }: { data: RunComparisonObservation; label: string }) {
  return <section aria-label={`${label} observation`} style={{ padding: 8, border: `1px solid ${P.border}`, borderRadius: 6 }}>
    <strong>{label}: {data.status}</strong>
    <div>Execution mode: {data.execution_mode ?? 'Unavailable'}</div>
    {data.execution_mode === 'manual' && <div>Manual observation — informational only.</div>}
    <ComparisonProvenance provenance={data.provenance} basis={data.provenance_basis} />
    {data.error && <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{data.error}</div>}
  </section>;
}

export function RunComparisonResults({ data, onOpenRun }: { data: RunComparisonResponse; onOpenRun: (id: string) => void }) {
  return <div style={{ display: 'grid', gap: 12, minWidth: 0 }}>
    <div aria-label="Comparison direction" style={{ overflowWrap: 'anywhere' }}>
      Baseline: <RunLink id={data.baseline_run_id} onOpenRun={onOpenRun} /> → Current: <RunLink id={data.comparison_run_id} onOpenRun={onOpenRun} />
    </div>
    <div><strong>{chronologyLabels[data.chronology.state]}</strong>
      <div>Timestamp basis: {data.chronology.basis}</div>
      <div>Baseline time: {data.chronology.baseline_time ?? 'Unavailable'}</div>
      <div>Current time: {data.chronology.comparison_time ?? 'Unavailable'}</div>
    </div>
    {data.chronology.state === 'reverse' && <div role="note" style={{ color: P.unclear }}>
      This reference run is newer than the current run. Comparison direction remains reference → current.
    </div>}
    {data.comparability_warnings.map((warning, i) => <div key={i} role="note" style={{ padding: 9, background: P.unclearSoft, border: `1px solid ${P.borderHi}`, borderRadius: 6 }}>{warning}</div>)}
    <Observation data={data.baseline} label="Baseline" />
    <Observation data={data.comparison} label="Current" />
    <div>Provenance compatibility: {data.provenance_compatibility}</div>
    <div>Comparability: {data.comparability.state}
      {data.comparability.reason_codes.map((reason, i) => <div key={i} style={{ color: P.textMute }}>{reason}</div>)}
    </div>
    {!data.coverage.complete && <div role="note" style={{ background: P.unclearSoft, padding: 9, borderRadius: 6 }}>
      <strong>Comparison coverage is partial.</strong>
      {data.coverage.omissions.map((reason, i) => <div key={i} style={{ overflowWrap: 'anywhere' }}>{reason}</div>)}
    </div>}
    <div style={{ color: P.textMute }}>
      Coverage: {data.coverage.complete ? 'Complete' : 'Partial'} · Limits per run: {data.coverage.step_limit_per_run} steps, {data.coverage.evidence_limit_per_run} evidence records, {data.coverage.result_bytes_limit_per_run} result bytes.
    </div>
    <dl aria-label="Comparison summary" style={{ margin: 0, display: 'grid', gap: 5 }}>
      {(Object.keys(countLabels) as Array<keyof RunComparisonSummaryCounts>).map(key => <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <dt>{countLabels[key]}</dt><dd aria-label={`${countLabels[key]} count`} style={{ margin: 0 }}>{data.summary_counts[key]}</dd>
      </div>)}
    </dl>
    <p style={{ margin: 0, color: P.textMute }}>Matching failure signatures do not prove the same root cause.</p>
    <p style={{ margin: 0, color: P.textMute }}>Evidence comparison uses metadata only. Stored hashes do not establish semantic similarity or current file availability.</p>
    {data.step_comparisons.length === 0 ? <div>No comparable step observations are available.</div> : <StepComparisonTable rows={data.step_comparisons} onOpenRun={onOpenRun} />}
  </div>;
}
