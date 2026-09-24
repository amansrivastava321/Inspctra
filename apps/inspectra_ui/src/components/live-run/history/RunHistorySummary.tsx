import { F, P } from '../../../design/tokens';
import type { RunHistoryItem, RunHistoryResponse } from '../../../types/api';
import { ProvenanceBadge } from '../../ProvenanceBadge';
import { HistoricalRunCitation } from './HistoricalRunCitation';


interface SummaryProps {
  history: RunHistoryResponse;
  onOpenRun: (runId: string) => void;
}

function LastFact({
  label,
  item,
  onOpenRun,
}: {
  label: string;
  item: RunHistoryItem | null;
  onOpenRun: (runId: string) => void;
}) {
  return (
    <div style={{ padding: 11, borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi }}>
      <div style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9, textTransform: 'uppercase' }}>
        {label}
      </div>
      {item ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 7 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ color: P.text, fontSize: 12 }}>{item.status}</span>
            <ProvenanceBadge provenance={item.provenance} source={`${label} ${item.run_id}`} />
          </div>
          <HistoricalRunCitation citation={item.citation} onOpenRun={onOpenRun} />
        </div>
      ) : (
        <div style={{ color: P.textMute, fontSize: 11, marginTop: 7 }}>None recorded.</div>
      )}
    </div>
  );
}

export function RunHistorySummary({ history, onOpenRun }: SummaryProps) {
  const ratePercent = `${Math.round(history.failure_rate.value * 100)}%`;
  return (
    <section aria-label="Historical summary" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 8 }}>
        <LastFact label="Last factual pass" item={history.last_passed} onOpenRun={onOpenRun} />
        <LastFact label="Last factual failure" item={history.last_failed} onOpenRun={onOpenRun} />
        <div style={{ padding: 11, borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi }}>
          <div style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9, textTransform: 'uppercase' }}>
            Factual failure rate
          </div>
          <div style={{ color: P.text, fontSize: 22, fontWeight: 700, marginTop: 5 }}>{ratePercent}</div>
          <div style={{ color: P.textDim, fontSize: 11, marginTop: 4 }}>
            {history.failure_rate.failed} of {history.failure_rate.total} comparable real executions failed.
          </div>
        </div>
      </div>

      {history.failure_rate.citations.length > 0 && (
        <details>
          <summary style={{ color: P.textDim, cursor: 'pointer', fontSize: 10 }}>
            Failure-rate citations · {history.failure_rate.citations.length}
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 7 }}>
            {history.failure_rate.citations.map((citation, index) => (
              <HistoricalRunCitation
                key={`${citation.run_id}-${index}`}
                citation={citation}
                onOpenRun={onOpenRun}
              />
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
