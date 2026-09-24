import { AlertTriangle } from 'lucide-react';
import { P } from '../../design/tokens';
import type { CapabilityGap, Provenance } from '../../types/api';
import { ProvenanceBadge } from '../ProvenanceBadge';

export function CapabilityGapCard({ gap, onAction, provenance, provenanceSource = 'Capability gap card' }: {
  gap: CapabilityGap;
  onAction?: (id: string) => void;
  provenance?: Provenance | null;
  provenanceSource?: string;
}) {
  const severityColor = { high: P.fail, medium: P.unclear, low: P.blocked }[gap.severity] ?? P.textMute;

  return (
    <div style={{
      background: P.card, border: `1px solid ${P.border}`, borderRadius: 9,
      padding: '12px 14px', display: 'flex', gap: 10,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 7, background: `${severityColor}18`,
        border: `1px solid ${severityColor}33`, display: 'flex', alignItems: 'center',
        justifyContent: 'center', flexShrink: 0,
      }}>
        <AlertTriangle size={13} color={severityColor} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: P.text, marginBottom: 3 }}>{gap.title}</div>
        <ProvenanceBadge provenance={provenance} source={provenanceSource} style={{ marginBottom: 5 }} />
        <div style={{ fontSize: 11, color: P.textMute, lineHeight: 1.4 }}>{gap.description}</div>
        {gap.action_label && onAction && (
          <button onClick={() => onAction(gap.id)} style={{
            marginTop: 8, padding: '4px 10px', borderRadius: 5,
            background: P.accentSoft, border: `1px solid ${P.accent}33`,
            fontSize: 11, color: P.accent, cursor: 'pointer', fontWeight: 500,
          }}>
            {gap.action_label}
          </button>
        )}
      </div>
    </div>
  );
}
