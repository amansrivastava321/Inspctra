import { F, P } from '../../../design/tokens';
import type { RepeatedFailureSignature } from '../../../types/api';
import { HistoricalRunCitation } from './HistoricalRunCitation';


export function RepeatedFailureList({
  signatures,
  onOpenRun,
  onSelectStep,
}: {
  signatures: RepeatedFailureSignature[];
  onOpenRun: (runId: string) => void;
  onSelectStep?: (stepId: string) => void;
}) {
  if (signatures.length === 0) return null;
  return (
    <section aria-label="Exact repeated failures" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h4 style={{ color: P.text, fontSize: 11, margin: 0 }}>Exact repeated failures</h4>
      {signatures.map(item => (
        <div key={item.signature} style={{ padding: 10, borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ color: P.text, fontSize: 11, fontWeight: 650 }}>Same deterministic failure signature</span>
            <span style={{ color: P.unclear, fontFamily: F.mono, fontSize: 10 }}>{item.occurrences} occurrences</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 7, marginTop: 8 }}>
            <div><span style={{ color: P.textMute, fontSize: 9 }}>category</span><div style={{ color: P.text, fontSize: 11 }}>{item.category}</div></div>
            <div><span style={{ color: P.textMute, fontSize: 9 }}>step_id</span><div style={{ color: P.text, fontFamily: F.mono, fontSize: 10 }}>{item.step_id}</div></div>
            {item.error_code && <div><span style={{ color: P.textMute, fontSize: 9 }}>error_code</span><div style={{ color: P.textDim, fontFamily: F.mono, fontSize: 10 }}>{item.error_code}</div></div>}
          </div>
          {item.error && <div style={{ color: P.textDim, fontSize: 10, marginTop: 7 }}>{item.error}</div>}
          {item.failure_reason && <div style={{ color: P.textDim, fontSize: 10, marginTop: 5 }}>{item.failure_reason}</div>}
          {item.notes && <div style={{ color: P.textMute, fontSize: 10, marginTop: 5 }}>{item.notes}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {item.citations.map((citation, index) => (
              <HistoricalRunCitation
                key={`${citation.run_id}-${index}`}
                citation={citation}
                onOpenRun={onOpenRun}
                onSelectStep={onSelectStep}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
