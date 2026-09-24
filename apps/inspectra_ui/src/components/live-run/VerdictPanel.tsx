import { P, F } from '../../design/tokens';
import { StatusBadge } from '../status/StatusBadge';
import type { LiveRunRecord, StepResult } from '../../types/api';
import type { StatusKind } from '../../design/tokens';

export function VerdictPanel({ run, selectedStep }: { run: LiveRunRecord; selectedStep?: StepResult | null }) {
  const pass = run.step_results.filter(s => s.status === 'passed').length;
  const fail = run.step_results.filter(s => s.status === 'failed').length;
  const blocked = run.step_results.filter(s => s.status === 'blocked').length;
  const skipped = run.step_results.filter(s => s.status === 'skipped').length;
  const unclear = run.step_results.filter(s => s.status === 'unclear').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Verdict header */}
      <div style={{ background: P.card, border: `1px solid ${P.border}`, borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase',
          letterSpacing: '0.08em', fontFamily: F.mono, marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
          <span>VERDICT</span>
          <span style={{ color: run.execution_mode === 'manual' ? P.accent : P.textMute, fontWeight: 700 }}>
            {run.execution_mode?.toUpperCase() || 'AUTOMATED'}
          </span>
        </div>
        {run.status === 'running' ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: 99, background: P.accent,
              animation: 'pulse 1s ease-in-out infinite' }} />
            <span style={{ fontSize: 18, fontWeight: 700, color: P.accent }}>RUNNING</span>
          </div>
        ) : run.verdict ? (
          <StatusBadge kind={run.verdict as StatusKind} />
        ) : (
          <span style={{ fontSize: 14, color: P.textMute }}>Pending</span>
        )}

        {/* Pass/Fail/Blocked/Skipped counts */}
        <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
          {[
            { label: 'PASS', value: pass, color: P.pass },
            { label: 'FAIL', value: fail, color: P.fail },
            { label: 'BLOCKED', value: blocked, color: P.unclear },
            { label: 'SKIPPED', value: skipped, color: P.textMute },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ minWidth: 45 }}>
              <div style={{ fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
              <div style={{ fontSize: 9, color: P.textMute, marginTop: 2, fontFamily: F.mono }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Run metadata */}
      <div style={{ background: P.card, border: `1px solid ${P.border}`, borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase',
          letterSpacing: '0.08em', fontFamily: F.mono, marginBottom: 8 }}>
          RUN INFO
        </div>
        {[
          { label: 'App', value: run.app_name ?? '—' },
          { label: 'Pack', value: run.pack_name ?? run.pack_id?.slice(0, 12) ?? '—' },
          { label: 'Platform', value: run.platform ?? '—' },
          { label: 'Elapsed', value: run.elapsed_ms ? `${(run.elapsed_ms / 1000).toFixed(0)}s` : '—' },
          { label: 'Operator', value: run.operator ?? '—' },
          { label: 'Evidence', value: String(run.evidence_count ?? 0) },
        ].map(({ label, value }) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: P.textMute }}>{label}</span>
            <span style={{ fontSize: 12, color: P.text, fontFamily: F.mono }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Selected step detail */}
      {selectedStep && (
        <div style={{ background: P.card, border: `1px solid ${P.border}`, borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase',
            letterSpacing: '0.08em', fontFamily: F.mono, marginBottom: 8 }}>
            SELECTED STEP
          </div>
          <div style={{ fontSize: 13, fontWeight: 500, color: P.text, marginBottom: 8 }}>
            {selectedStep.name}
          </div>
          <StatusBadge kind={selectedStep.status as StatusKind} />
          {selectedStep.confidence !== undefined && (
            <div style={{ marginTop: 8, fontSize: 12, color: P.textMute }}>
              Confidence: <span style={{ color: P.text, fontFamily: F.mono }}>{selectedStep.confidence}%</span>
            </div>
          )}
          {selectedStep.error && (
            <div style={{ marginTop: 8, padding: '6px 8px', borderRadius: 6,
              background: P.failSoft, fontSize: 11, color: P.fail, fontFamily: F.mono }}>
              {selectedStep.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
