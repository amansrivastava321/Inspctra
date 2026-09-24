import { P, F } from '../../../design/tokens';
import type { Provenance, RunComparisonCitation, RunComparisonDisplay, RunComparisonProvenanceBasis, RunStepComparison } from '../../../types/api';
import { ProvenanceBadge } from '../../ProvenanceBadge';

export const identityLabels: Record<RunStepComparison['identity_state'], string> = {
  matched: 'Matched', baseline_only: 'Present only in baseline results',
  comparison_only: 'Present only in comparison results', identity_unavailable: 'Identity unavailable', identity_conflict: 'Identity conflict',
};
export const transitionLabels: Record<RunStepComparison['transition'], string> = {
  passed_to_failed: 'Passed → Failed', failed_to_passed: 'Failed → Passed',
  passed_to_passed: 'Passed → Passed', failed_to_failed: 'Failed → Failed',
  passed_to_inconclusive: 'Passed → Inconclusive', failed_to_inconclusive: 'Failed → Inconclusive',
  inconclusive_to_passed: 'Inconclusive → Passed', inconclusive_to_failed: 'Inconclusive → Failed',
  inconclusive_to_inconclusive: 'Inconclusive → Inconclusive', not_comparable: 'Not comparable',
};

export function ComparisonProvenance({ provenance, basis }: { provenance: Provenance | null; basis?: RunComparisonProvenanceBasis }) {
  if (basis !== 'stored') {
    return <span style={{ color: P.textMute }}>
      {basis === 'inferred' ? 'Inferred provenance' : 'Provenance basis unavailable'} · Recorded value: {provenance ?? 'UNAVAILABLE'} (unverified)
    </span>;
  }
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
    <span>Stored {provenance ?? 'UNAVAILABLE'}</span>
    <ProvenanceBadge provenance={provenance ?? 'UNAVAILABLE'} source="run comparison" />
  </span>;
}

export function RunLink({ id, onOpenRun }: { id: string; onOpenRun: (id: string) => void }) {
  return <button type="button" aria-label={`Open run ${id}`} onClick={() => onOpenRun(id)}
    style={{ border: 0, background: 'transparent', padding: 0, cursor: 'pointer', color: P.accent, fontFamily: F.mono, fontSize: 'inherit', textDecoration: 'underline', overflowWrap: 'anywhere' }}>
    {id}
  </button>;
}

export function ComparisonCitation({ citation, onOpenRun }: { citation: RunComparisonCitation | null; onOpenRun: (id: string) => void }) {
  if (!citation) return <span>Unavailable</span>;
  return <div style={{ display: 'grid', gap: 5 }}>
    <RunLink id={citation.run_id} onOpenRun={onOpenRun} />
    <ComparisonProvenance provenance={citation.provenance} basis={citation.provenance_basis} />
    {citation.evidence_ids.map((id, index) => <span key={`${id}-${index}`} style={{ fontFamily: F.mono, overflowWrap: 'anywhere' }}
      title="Evidence metadata citation; no evidence-detail route is available.">{id}</span>)}
  </div>;
}

export function PersistedDisplay({ data }: { data: RunComparisonDisplay | null }) {
  if (!data) return null;
  return <div style={{ display: 'grid', gap: 3, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
    {Object.entries(data).map(([key, value]) => value !== null && <div key={key}>{key}: {value}</div>)}
  </div>;
}
