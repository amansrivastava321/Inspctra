import { AlertTriangle } from 'lucide-react';
import { F, P } from '../../design/tokens';
import type { EvidenceFile, LiveRunRecord, StepResult } from '../../types/api';
import { EvidenceCard } from './EvidenceCard';
import { ApiExchangeEvidence } from './ApiExchangeEvidence';
import { ManualConfirmationEvidence } from './ManualConfirmationEvidence';
import { ScreenshotEvidence } from './ScreenshotEvidence';
import { TextEvidence } from './TextEvidence';

interface EvidencePanelProps {
  run: LiveRunRecord;
  step: StepResult | null;
  evidence: EvidenceFile[];
  onManualVerdict?: (status: 'passed' | 'failed') => void;
}

function evidenceType(item: EvidenceFile): string {
  return item.evidence_type ?? item.type ?? '';
}

const OWN_VIEWERS = new Set([
  'screenshot', 'page_html', 'console',
  'api_request', 'api_response', 'api_assertion', 'manual_confirmation',
]);

export function EvidencePanel({ run, step, evidence, onManualVerdict }: EvidencePanelProps) {
  const screenshots = evidence.filter((item) => evidenceType(item) === 'screenshot');
  const html = evidence.find((item) => evidenceType(item) === 'page_html');
  const consoleEvidence = evidence.find((item) => evidenceType(item) === 'console');
  const apiRequest = evidence.find((item) => evidenceType(item) === 'api_request');
  const apiResponse = evidence.find((item) => evidenceType(item) === 'api_response');
  const apiAssertion = evidence.find((item) => evidenceType(item) === 'api_assertion');
  const manualConfirmation = evidence.find((item) => evidenceType(item) === 'manual_confirmation');
  const otherEvidence = evidence.filter((item) => !OWN_VIEWERS.has(evidenceType(item)));
  const consoleEntries = (consoleEvidence?.metadata_json?.entries ?? []) as Array<Record<string, unknown>>;
  const hasApi = Boolean(apiRequest || apiResponse || apiAssertion);
  const isManual = run.execution_mode === 'manual' && step != null;

  return (
    <aside aria-label="Run evidence" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 14, border: `1px solid ${P.borderHi}`, borderRadius: 12, background: P.surface, boxShadow: P.shadowCard }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div style={{ color: P.text, fontSize: 14, fontWeight: 700 }}>Evidence</div>
          <div style={{ marginTop: 2, color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>{step ? `STEP ${step.index}` : 'ENTIRE RUN'} · {evidence.length} artifacts</div>
        </div>
      </div>

      {screenshots.length > 0 && <ScreenshotEvidence screenshots={screenshots} step={step} />}

      {isManual && <ManualConfirmationEvidence step={step} evidence={manualConfirmation} onVerdict={onManualVerdict} />}

      {consoleEntries.length > 0 && (
        <details open style={{ borderTop: `1px solid ${P.border}`, paddingTop: 10 }}>
          <summary style={{ color: P.text, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>Console warnings/errors</summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {consoleEntries.map((entry, index) => {
              const isError = String(entry.type).toLowerCase() === 'error';
              return (
                <div key={`${String(entry.timestamp ?? '')}-${index}`} style={{ padding: 8, borderRadius: 6, background: isError ? P.failSoft : P.unclearSoft, borderLeft: `2px solid ${isError ? P.fail : P.unclear}` }}>
                  <div style={{ color: isError ? P.fail : P.unclear, fontFamily: F.mono, fontSize: 10 }}>{String(entry.text ?? entry.message ?? '')}</div>
                  {entry.timestamp != null && <div style={{ marginTop: 3, color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>{new Date(String(entry.timestamp)).toLocaleString()}</div>}
                </div>
              );
            })}
          </div>
        </details>
      )}

      {html && <TextEvidence evidence={html} label="View page source at failure time" />}
      {hasApi && <ApiExchangeEvidence request={apiRequest} response={apiResponse} assertion={apiAssertion} />}

      {otherEvidence.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, borderTop: `1px solid ${P.border}`, paddingTop: 10 }}>
          {otherEvidence.map((item) => <EvidenceCard key={item.id} ev={item} />)}
        </div>
      )}

      {evidence.length === 0 && !isManual && (
        <div style={{ minHeight: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8, textAlign: 'center', color: P.textMute }}>
          <AlertTriangle size={20} color={P.textFaint} />
          <div style={{ maxWidth: 300, fontSize: 12, lineHeight: 1.5 }}>
            {step
              ? 'No evidence for this step.'
              : 'No evidence captured. This run was executed before evidence collection was enabled.'}
          </div>
        </div>
      )}
    </aside>
  );
}
