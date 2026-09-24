import { AlertTriangle } from 'lucide-react';
import { F, P } from '../../design/tokens';
import type { EvidenceFile, StepResult } from '../../types/api';

interface FailureDetailsProps {
  step: StepResult;
  evidence: EvidenceFile[];
}

function valueText(value: unknown): string {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

export function FailureDetails({ step, evidence }: FailureDetailsProps) {
  if (step.status !== 'failed' && step.status !== 'error') return null;
  const assertion = evidence.find((item) => (item.evidence_type ?? item.type) === 'api_assertion');
  const assertionMetadata = assertion?.metadata_json ?? {};
  const message = step.failure_reason || step.notes || step.error || 'Step failed.';
  const expected = step.expected ?? assertionMetadata.expected;
  const actual = step.actual ?? assertionMetadata.actual ?? step.status_code;

  return (
    <section aria-label="Failure details" style={{ padding: 14, borderRadius: 10, border: `1px solid ${P.fail}44`, background: P.failSoft, display: 'flex', flexDirection: 'column', gap: 11 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: P.fail, fontSize: 12, fontWeight: 700 }}>
        <AlertTriangle size={15} /> Failure details
      </div>
      <div style={{ color: P.text, fontSize: 12, lineHeight: 1.55 }}>{message}</div>
      {(expected !== undefined || actual !== undefined) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
          <div style={{ padding: 10, borderRadius: 8, border: `1px solid ${P.border}`, background: P.card }}>
            <div style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9, textTransform: 'uppercase' }}>Expected</div>
            <pre style={{ margin: '6px 0 0', color: P.text, fontFamily: F.mono, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{expected === undefined ? '—' : valueText(expected)}</pre>
          </div>
          <div style={{ padding: 10, borderRadius: 8, border: `1px solid ${P.fail}33`, background: P.card }}>
            <div style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9, textTransform: 'uppercase' }}>Actual</div>
            <pre style={{ margin: '6px 0 0', color: P.fail, fontFamily: F.mono, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{actual === undefined ? '—' : valueText(actual)}</pre>
          </div>
        </div>
      )}
      {step.error && (
        <details style={{ borderTop: `1px solid ${P.fail}33`, paddingTop: 8 }}>
          <summary style={{ color: P.textDim, cursor: 'pointer', fontSize: 11 }}>Exception details</summary>
          <pre style={{ margin: '8px 0 0', padding: 9, borderRadius: 7, background: P.bg, color: P.fail, fontFamily: F.mono, fontSize: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{step.error}</pre>
        </details>
      )}
    </section>
  );
}
