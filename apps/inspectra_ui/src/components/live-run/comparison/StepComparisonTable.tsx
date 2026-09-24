import type { CSSProperties } from 'react';
import { P } from '../../../design/tokens';
import type { RunComparisonMetric, RunStepComparison } from '../../../types/api';
import { ComparisonCitation, ComparisonProvenance, identityLabels, PersistedDisplay, transitionLabels } from './ComparisonDetails';

const cell: CSSProperties = { padding: 8, borderBottom: `1px solid ${P.border}`, textAlign: 'left', verticalAlign: 'top', overflowWrap: 'anywhere' };
const metrics: Record<RunComparisonMetric['key'], string> = {
  duration_ms: 'Recorded step duration', response_time_ms: 'API response time', status_code: 'HTTP status',
};
const signatureLabels = {
  same_signature: 'Same deterministic failure signature', different_signature: 'Different deterministic failure signature', unavailable: 'Unavailable',
};
const hashes = { same_hash: 'Same stored hash', different_hash: 'Different stored hashes', unavailable: 'Stored hash comparison unavailable' };

function Metric({ metric }: { metric: RunComparisonMetric }) {
  const value = (v: number | null) => v === null ? 'Unavailable' : `${v}${metric.unit === 'ms' ? ' ms' : ''}`;
  return <div style={{ marginBottom: 10 }}>
    <strong>{metrics[metric.key]}</strong>
    <div>{value(metric.baseline_value)} → {value(metric.comparison_value)}</div>
    {metric.key !== 'status_code' && <div>Delta: <span>{metric.delta === null ? 'Unavailable' : `${metric.delta > 0 ? '+' : ''}${metric.delta} ms`}</span></div>}
    {metric.reason && <div style={{ color: P.textMute }}>{metric.reason}</div>}
  </div>;
}

export function StepComparisonTable({ rows, onOpenRun }: { rows: RunStepComparison[]; onOpenRun: (id: string) => void }) {
  return <div style={{ overflowX: 'auto', maxWidth: '100%' }} tabIndex={0} role="region" aria-label="Scrollable step comparison results">
    <table aria-label="Step comparisons" style={{ borderCollapse: 'collapse', width: '100%', minWidth: 980, tableLayout: 'fixed', fontSize: 11 }}>
      <thead><tr>{['Step ID / identity', 'Baseline status', 'Current status', 'Transition', 'Provenance', 'Metrics', 'Evidence metadata', 'Failure signature'].map(label =>
        <th key={label} scope="col" style={cell}>{label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={`${row.step_id ?? 'unavailable'}-${index}`}>
        <th scope="row" style={cell}>
          <div>{row.step_id ?? 'Unavailable'}</div><div>{identityLabels[row.identity_state]}</div>
          {row.reason_codes.map((reason, i) => <div key={i} style={{ color: P.textMute, fontWeight: 400 }}>{reason}</div>)}
        </th>
        <td style={cell}>{row.baseline_status ?? 'Unavailable'}<PersistedDisplay data={row.baseline_display} /></td>
        <td style={cell}>{row.comparison_status ?? 'Unavailable'}<PersistedDisplay data={row.comparison_display} /></td>
        <td style={cell}>{transitionLabels[row.transition]}<div>Comparison: {row.comparison_state}</div></td>
        <td style={cell}><div>Baseline: <ComparisonProvenance provenance={row.baseline_provenance} basis={row.baseline_citation?.provenance_basis} /></div>
          <div>Current: <ComparisonProvenance provenance={row.comparison_provenance} basis={row.comparison_citation?.provenance_basis} /></div></td>
        <td style={cell}>{row.metric_comparisons.length === 0 ? 'Unavailable' : row.metric_comparisons.map(metric => <Metric key={metric.key} metric={metric} />)}</td>
        <td style={cell}>
          {!row.evidence_comparison.complete && <div role="note">Evidence coverage is partial.</div>}
          <div>Baseline evidence: {row.evidence_comparison.baseline_count ?? 'Unavailable'}</div>
          {Object.entries(row.evidence_comparison.baseline_type_counts).map(([type, count]) => <div key={type}>Baseline {type}: {count}</div>)}
          <ComparisonCitation citation={row.baseline_citation} onOpenRun={onOpenRun} />
          <div style={{ marginTop: 8 }}>Current evidence: {row.evidence_comparison.comparison_count ?? 'Unavailable'}</div>
          {Object.entries(row.evidence_comparison.comparison_type_counts).map(([type, count]) => <div key={type}>Current {type}: {count}</div>)}
          <ComparisonCitation citation={row.comparison_citation} onOpenRun={onOpenRun} />
          <div style={{ marginTop: 8 }}>{hashes[row.evidence_comparison.hash_comparison]}</div>
        </td>
        <td style={cell}>{signatureLabels[row.failure_signature_comparison.state]}
          <div>{row.failure_signature_comparison.algorithm}</div>
          {row.failure_signature_comparison.reason && <div>{row.failure_signature_comparison.reason}</div>}
        </td>
      </tr>)}</tbody>
    </table>
  </div>;
}
