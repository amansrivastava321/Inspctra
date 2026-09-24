import { ExternalLink } from 'lucide-react';

import { F, P } from '../../../design/tokens';
import type { RunHistoryCitation } from '../../../types/api';
import { ProvenanceBadge } from '../../ProvenanceBadge';


export interface HistoricalRunCitationProps {
  citation: RunHistoryCitation;
  onOpenRun: (runId: string) => void;
  onSelectStep?: (stepId: string) => void;
}

export function HistoricalRunCitation({
  citation,
  onOpenRun,
  onSelectStep,
}: HistoricalRunCitationProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 7 }}>
      <button
        type="button"
        aria-label={`Open run ${citation.run_id}`}
        onClick={() => onOpenRun(citation.run_id)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4, border: 0, padding: 0,
          background: 'transparent', color: P.accent, cursor: 'pointer',
          fontFamily: F.mono, fontSize: 10, textDecoration: 'underline',
        }}
      >
        run {citation.run_id}<ExternalLink size={10} aria-hidden />
      </button>
      {citation.step_id && (
        onSelectStep ? (
          <button
            type="button"
            aria-label={`Focus step ${citation.step_id}`}
            onClick={() => onSelectStep(citation.step_id!)}
            style={{
              border: 0, padding: 0, background: 'transparent', color: P.textDim,
              cursor: 'pointer', fontFamily: F.mono, fontSize: 10, textDecoration: 'underline',
            }}
          >
            step {citation.step_id}
          </button>
        ) : (
          <span style={{ color: P.textDim, fontFamily: F.mono, fontSize: 10 }}>
            step {citation.step_id}
          </span>
        )
      )}
      {citation.evidence_ids.map(evidenceId => (
        <span
          key={evidenceId}
          title="No evidence-detail route is available; reference shown as text."
          style={{ color: P.textMute, fontFamily: F.mono, fontSize: 10 }}
        >
          evidence {evidenceId}
        </span>
      ))}
      {citation.completed_at && (
        <time dateTime={citation.completed_at} style={{ color: P.textMute, fontSize: 10 }}>
          {new Date(citation.completed_at).toLocaleString()}
        </time>
      )}
      <ProvenanceBadge
        provenance={citation.provenance}
        source={`historical citation ${citation.run_id}`}
      />
    </div>
  );
}
