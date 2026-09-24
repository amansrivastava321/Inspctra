import { Camera, FileText, Database, Globe, Cpu, Layers, Activity, Shield } from 'lucide-react';
import { P, F } from '../../design/tokens';
import { StatusBadge } from '../status/StatusBadge';
import type { EvidenceFile, EvidenceType } from '../../types/api';
import type { StatusKind } from '../../design/tokens';
import { ProvenanceBadge } from '../ProvenanceBadge';

const TYPE_ICON: Record<EvidenceType, typeof Camera> = {
  screenshot: Camera,
  console: FileText,
  network: Globe,
  page_html: FileText,
  manual_confirmation: FileText,
  log: FileText,
  db: Database,
  api: Globe,
  api_request: Globe,
  api_response: Globe,
  api_assertion: Globe,
  ai: Cpu,
  trace: Layers,
  performance_summary: Activity,
  web_timing: Activity,
  api_timing: Activity,
  accessibility_summary: FileText,
  accessibility_violations: FileText,
  visual_diff: Camera,
  security_findings: Shield,
};
const TYPE_LABEL: Record<EvidenceType, string> = {
  screenshot: 'SCREENSHOT DIFF',
  console: 'CONSOLE LOGS',
  network: 'NETWORK SUMMARY',
  page_html: 'PAGE HTML',
  manual_confirmation: 'MANUAL CONFIRMATION',
  log: 'LOG MATCH',
  db: 'DATABASE DELTA',
  api: 'API CHECK',
  api_request: 'API REQUEST',
  api_response: 'API RESPONSE',
  api_assertion: 'API ASSERTION',
  ai: 'AI ORACLE',
  trace: 'TRACE FILE',
  performance_summary: 'PERFORMANCE SUMMARY',
  web_timing: 'WEB TIMING',
  api_timing: 'API TIMING',
  accessibility_summary: 'ACCESSIBILITY SUMMARY',
  accessibility_violations: 'ACCESSIBILITY VIOLATIONS',
  visual_diff: 'VISUAL DIFF',
  security_findings: 'SECURITY FINDINGS',
};

interface EvidenceCardProps {
  ev: EvidenceFile;
  onClick?: () => void;
}

export function EvidenceCard({ ev, onClick }: EvidenceCardProps) {
  const Icon = TYPE_ICON[ev.evidence_type] ?? Layers;
  const typeLabel = TYPE_LABEL[ev.evidence_type] ?? ev.evidence_type.toUpperCase();

  return (
    <div onClick={onClick} style={{
      background: P.card, border: `1px solid ${P.border}`, borderRadius: 9,
      padding: '12px 14px', cursor: onClick ? 'pointer' : 'default',
      display: 'flex', alignItems: 'flex-start', gap: 10,
      transition: 'border-color 0.12s, background 0.12s',
    }}
      onMouseEnter={e => { if (onClick) { (e.currentTarget as HTMLElement).style.borderColor = P.borderHi; (e.currentTarget as HTMLElement).style.background = P.cardHi; } }}
      onMouseLeave={e => { if (onClick) { (e.currentTarget as HTMLElement).style.borderColor = P.border; (e.currentTarget as HTMLElement).style.background = P.card; } }}
    >
      <div style={{
        width: 30, height: 30, borderRadius: 7, background: P.cardHi,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon size={13} color={P.textMute} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
            letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {typeLabel}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <ProvenanceBadge provenance={ev.provenance} source="Evidence card" />
            {ev.strength && <StatusBadge kind={ev.strength as StatusKind} small />}
          </div>
        </div>
        {ev.title && (
          <div style={{ fontSize: 12, fontWeight: 500, color: P.text, marginBottom: 2 }}>{ev.title}</div>
        )}
        {ev.description && (
          <div style={{ fontSize: 11, color: P.textDim, lineHeight: 1.4 }}>{ev.description}</div>
        )}
        {ev.content_preview && (
          <div style={{
            marginTop: 6, padding: '4px 8px', borderRadius: 5, background: P.bg,
            fontFamily: F.mono, fontSize: 10, color: P.textMute,
            border: `1px solid ${P.border}`, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {/* Safe display: text content only, no HTML */}
            {ev.content_preview.replace(/</g, '&lt;').replace(/>/g, '&gt;')}
          </div>
        )}
        {ev.id && (
          <div style={{ marginTop: 4, fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>
            evd-{ev.id.slice(-4)}
          </div>
        )}
      </div>
    </div>
  );
}
