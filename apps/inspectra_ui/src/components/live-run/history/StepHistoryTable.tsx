import { F, P } from '../../../design/tokens';
import type { RunStepHistory } from '../../../types/api';
import { HistoricalRunCitation } from './HistoricalRunCitation';


export function StepHistoryTable({
  steps,
  onOpenRun,
  onSelectStep,
}: {
  steps: RunStepHistory[];
  onOpenRun: (runId: string) => void;
  onSelectStep?: (stepId: string) => void;
}) {
  if (steps.length === 0) return null;
  return (
    <section aria-label="Exact step history" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h4 style={{ color: P.text, fontSize: 11, margin: 0 }}>Exact stable-step history</h4>
      {steps.map((step, index) => (
        <div
          key={`${step.step_id ?? 'missing'}-${index}`}
          style={{ padding: 10, borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi }}
        >
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 9 }}>
            <code style={{ color: step.insufficient_identity ? P.unclear : P.text, fontFamily: F.mono, fontSize: 11 }}>
              {step.step_id ?? 'identity unavailable'}
            </code>
            <span style={{ color: P.pass, fontSize: 10 }}>{step.passed} passed</span>
            <span style={{ color: P.fail, fontSize: 10 }}>{step.failed} failed</span>
            <span style={{ color: P.unclear, fontSize: 10 }}>{step.inconclusive} inconclusive</span>
            <span style={{ color: P.textMute, fontSize: 10 }}>{step.total} total</span>
          </div>
          {step.insufficient_identity && (
            <div role="note" style={{ color: P.unclear, fontSize: 10, marginTop: 7 }}>
              Historical identity could not be established for this observation.
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {step.citations.map((citation, citationIndex) => (
              <HistoricalRunCitation
                key={`${citation.run_id}-${citationIndex}`}
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
