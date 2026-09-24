import { AlertCircle, CheckCircle, XCircle, HelpCircle, Clock, Circle, MinusCircle } from 'lucide-react';
import { P, F } from '../../design/tokens';
import { ConfidenceMeter } from '../status/StatusBadge';
import type { StepResult } from '../../types/api';
import { ProvenanceBadge } from '../ProvenanceBadge';

const STEP_ICON: Record<string, typeof CheckCircle> = {
  passed: CheckCircle, failed: XCircle, error: AlertCircle, unclear: HelpCircle,
  running: Clock, blocked: MinusCircle,
};
const STEP_COLOR: Record<string, string> = {
  passed: P.pass, failed: P.fail, error: P.fail, unclear: P.unclear,
  running: P.accent, blocked: P.blocked, pending: P.textFaint, skipped: P.textFaint,
};

interface StepTimelineProps {
  steps: StepResult[];
  activeStepId?: string;
  onSelectStep?: (step: StepResult) => void;
}

export function StepTimeline({ steps, activeStepId, onSelectStep }: StepTimelineProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {steps.map((step, i) => {
        const Icon = STEP_ICON[step.status] ?? Circle;
        const color = STEP_COLOR[step.status] ?? P.textFaint;
        const active = step.id === activeStepId;
        const isRunning = step.status === 'running';

        return (
          <div key={step.id ?? step.step_id ?? step.index}
            onClick={() => onSelectStep?.(step)}
            style={{
              display: 'flex', gap: 10, padding: '9px 14px',
              background: active ? P.accentSoft : 'transparent',
              borderLeft: `2px solid ${active ? P.accent : 'transparent'}`,
              cursor: onSelectStep ? 'pointer' : 'default',
              transition: 'background 0.1s',
              position: 'relative',
            }}>
            {/* Icon */}
            <div style={{ flexShrink: 0, marginTop: 2, position: 'relative' }}>
              <Icon aria-label={`Step ${step.index} status: ${step.status}`} size={16} color={color} strokeWidth={isRunning ? 1.5 : 2}
                style={{ animation: isRunning ? 'spin 1.5s linear infinite' : undefined }} />
            </div>
            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{
                  fontSize: 12, fontWeight: active ? 500 : 400,
                  color: active ? P.text : P.textDim,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}>
                  {`Step ${step.index}: ${step.name}`}
                  {(step as any).warning && <span title="Performance Warning" style={{ color: P.unclear, fontSize: 11 }}>⚠</span>}
                </span>
                <span style={{ fontSize: 9, fontFamily: F.mono, color, flexShrink: 0, textTransform: 'uppercase' }}>{step.status}</span>
              </div>
              {(step.failure_reason || step.notes || step.error || step.actual_result) && (
                <div style={{ marginTop: 4, color: step.status === 'failed' || step.status === 'error' ? P.fail : P.textMute, fontSize: 10, lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {step.failure_reason || step.notes || step.error || step.actual_result}
                </div>
              )}
              {(step.started_at || step.completed_at) && (
                <div style={{ display: 'flex', gap: 5, marginTop: 4, color: P.textFaint, fontFamily: F.mono, fontSize: 9 }}>
                  {step.started_at && <span>{new Date(step.started_at).toLocaleTimeString()}</span>}
                  {step.started_at && step.completed_at && <span>→</span>}
                  {step.completed_at && <span>{new Date(step.completed_at).toLocaleTimeString()}</span>}
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <ProvenanceBadge provenance={step.provenance} source="Run step" />
                {step.confidence !== undefined && (
                  <ConfidenceMeter value={step.confidence} width={80}
                    color={step.status === 'passed' ? P.pass : step.status === 'failed' ? P.fail : undefined} />
                )}
                {step.confidence !== undefined && (
                  <span style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>
                    {step.confidence}%
                  </span>
                )}
                {(step.evidence_count ?? step.evidence_ids?.length ?? 0) > 0 && (
                  <span style={{ fontSize: 10, color: P.textFaint }}>
                    +{step.evidence_count ?? step.evidence_ids?.length ?? 0} ev
                  </span>
                )}
                {step.duration_ms && (
                  <span style={{ fontSize: 10, color: P.textFaint, marginLeft: 'auto' }}>
                    {(step.duration_ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
            </div>
            {/* Connector line */}
            {i < steps.length - 1 && (
              <div style={{
                position: 'absolute', left: 22, top: '100%',
                width: 1, height: 18, background: P.border,
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}
