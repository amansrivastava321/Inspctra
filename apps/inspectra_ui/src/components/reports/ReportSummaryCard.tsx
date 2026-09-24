import { FileText } from 'lucide-react';
import { P } from '../../design/tokens';
import { StatusBadge } from '../status/StatusBadge';
import type { ReportRecord } from '../../types/api';
import type { StatusKind } from '../../design/tokens';
import { ProvenanceBadge } from '../ProvenanceBadge';
import { ReportDownloadButtons } from './ReportDownloadButtons';

export function ReportSummaryCard({ report, onClick }: { report: ReportRecord; onClick?: () => void }) {
  return (
    <div onClick={onClick} style={{
      background: P.card, border: `1px solid ${P.border}`, borderRadius: 10,
      padding: '16px 18px', cursor: onClick ? 'pointer' : 'default',
      display: 'flex', alignItems: 'center', gap: 14,
      transition: 'border-color 0.12s',
    }}
      onMouseEnter={e => { if (onClick) (e.currentTarget as HTMLElement).style.borderColor = P.borderHi; }}
      onMouseLeave={e => { if (onClick) (e.currentTarget as HTMLElement).style.borderColor = P.border; }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 9, background: P.cardHi,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <FileText size={16} color={P.textMute} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: P.text, marginBottom: 2 }}>
          {report.app_name ?? 'Report'} · {report.pack_name}
        </div>
        {report.summary && (
          <div style={{ fontSize: 12, color: P.textDim, lineHeight: 1.4 }}>{report.summary}</div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexShrink: 0 }}>
        <ReportDownloadButtons runId={report.run_id} compact />
        <ProvenanceBadge provenance={report.provenance} source="Report summary" />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: P.pass }}>{report.pass_count ?? 0}</div>
          <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase', letterSpacing: '0.06em' }}>PASS</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: P.fail }}>{report.fail_count ?? 0}</div>
          <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase', letterSpacing: '0.06em' }}>FAIL</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: P.unclear }}>{report.unclear_count ?? 0}</div>
          <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase', letterSpacing: '0.06em' }}>UNCLEAR</div>
        </div>
        {report.verdict && <StatusBadge kind={report.verdict as StatusKind} />}
      </div>
    </div>
  );
}
