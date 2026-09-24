import { Check, X } from 'lucide-react';
import { F, P } from '../../design/tokens';
import type { EvidenceFile, StepResult } from '../../types/api';

interface ManualConfirmationEvidenceProps {
  step: StepResult;
  evidence?: EvidenceFile;
  onVerdict?: (status: 'passed' | 'failed') => void;
}

export function ManualConfirmationEvidence({ step, evidence, onVerdict }: ManualConfirmationEvidenceProps) {
  const metadata = evidence?.metadata_json ?? {};
  const status = String(metadata.status ?? step.status);
  const pending = status === 'pending';
  if (pending) {
    return (
      <section style={{ padding: 12, borderRadius: 8, border: `1px solid ${P.unclear}44`, background: P.unclearSoft }}>
        <div style={{ color: P.unclear, fontWeight: 600, fontSize: 12 }}>Awaiting confirmation</div>
        <div style={{ marginTop: 5, color: P.textDim, fontSize: 11 }}>A tester must confirm or decline this step.</div>
        {onVerdict && (
          <div style={{ display: 'flex', gap: 7, marginTop: 10 }}>
            <button type="button" onClick={() => onVerdict('passed')} style={{ padding: '6px 9px', display: 'flex', alignItems: 'center', gap: 5, borderRadius: 6, border: `1px solid ${P.pass}55`, background: P.passSoft, color: P.pass, cursor: 'pointer' }}><Check size={13} />Confirm step</button>
            <button type="button" onClick={() => onVerdict('failed')} style={{ padding: '6px 9px', display: 'flex', alignItems: 'center', gap: 5, borderRadius: 6, border: `1px solid ${P.fail}55`, background: P.failSoft, color: P.fail, cursor: 'pointer' }}><X size={13} />Decline step</button>
          </div>
        )}
      </section>
    );
  }
  const tester = String(metadata.tester_name ?? step.tester_name ?? 'Unknown tester');
  const completedAt = metadata.completed_at ?? step.completed_at;
  return (
    <section style={{ padding: 12, borderRadius: 8, border: `1px solid ${status === 'passed' ? P.pass : P.fail}44`, background: status === 'passed' ? P.passSoft : P.failSoft }}>
      <div style={{ color: status === 'passed' ? P.pass : P.fail, fontWeight: 600, fontSize: 12 }}>{status === 'passed' ? `Confirmed by ${tester}` : `Declined by ${tester}`}</div>
      {completedAt != null && <div style={{ marginTop: 4, color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>{new Date(String(completedAt)).toLocaleString()}</div>}
      {(metadata.actual_result ?? step.actual_result) && <div style={{ marginTop: 8, color: P.text, fontSize: 11 }}>{String(metadata.actual_result ?? step.actual_result)}</div>}
      {(metadata.notes ?? step.notes) && <div style={{ marginTop: 5, color: P.textDim, fontSize: 11 }}>{String(metadata.notes ?? step.notes)}</div>}
      {(metadata.failure_reason ?? step.failure_reason) && <div style={{ marginTop: 5, color: P.fail, fontSize: 11 }}>{String(metadata.failure_reason ?? step.failure_reason)}</div>}
    </section>
  );
}
