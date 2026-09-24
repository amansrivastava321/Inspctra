import { AlertTriangle, AlertCircle, Info, CheckCircle } from 'lucide-react';
import { P } from '../../design/tokens';
import { StatusBadge } from '../status/StatusBadge';
import type { ReportFinding } from '../../types/api';
import type { StatusKind } from '../../design/tokens';

const SEV_CONFIG = {
  critical: { c: P.fail,    Icon: AlertCircle,   bg: P.failSoft },
  high:     { c: P.fail,    Icon: AlertTriangle,  bg: P.failSoft },
  medium:   { c: P.unclear, Icon: AlertTriangle,  bg: P.unclearSoft },
  low:      { c: P.blocked, Icon: Info,           bg: P.blockedSoft },
  info:     { c: P.accent,  Icon: Info,           bg: P.accentSoft },
};

export function FindingCard({ finding, expanded }: { finding: ReportFinding; expanded?: boolean }) {
  const { c, Icon, bg } = SEV_CONFIG[finding.severity] ?? SEV_CONFIG.info;

  return (
    <div style={{
      background: P.card, border: `1px solid ${bg.replace('0.12', '0.2')}`,
      borderLeft: `3px solid ${c}`, borderRadius: 9,
      padding: '12px 14px 12px 12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <Icon size={14} color={c} style={{ marginTop: 1, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{finding.title}</span>
            <span style={{ fontSize: 10, color: c, textTransform: 'uppercase',
              letterSpacing: '0.06em', fontFamily: "'JetBrains Mono', monospace" }}>
              {finding.severity}
            </span>
            {finding.status && <StatusBadge kind={finding.status as StatusKind} small />}
          </div>
          {finding.step_name && (
            <div style={{ fontSize: 11, color: P.textMute, marginBottom: 4 }}>
              Step: {finding.step_name}
            </div>
          )}
          {(expanded || true) && finding.description && (
            <div style={{ fontSize: 12, color: P.textDim, lineHeight: 1.5 }}>
              {finding.description}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
