import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowLeft, Download, RotateCcw } from 'lucide-react';
import { P, F } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { FindingCard } from '../components/common/FindingCard';
import { LoadingSkeleton, ErrorState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, reportExportUrl, retestFailed } from '../api/client';
import type { ReportRecord } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { ReportDownloadButtons } from '../components/reports/ReportDownloadButtons';

export default function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const nav = useWorkspaceNavigate();
  const [retesting, setRetesting] = useState(false);
  const [retestError, setRetestError] = useState('');

  const getReport = useCallback(() => get<ReportRecord>(`/reports/${reportId}`), [reportId]);
  const { data: report, loading, error, refetch } = useApi(getReport, {
    demo: workspace => workspace.reports.find(r => r.id === reportId) as ReportRecord,
  });

  const handleRetest = async () => {
    if (!report?.run_id) return;
    setRetesting(true);
    setRetestError('');
    try {
      const newRun = await retestFailed(report.run_id);
      nav(`/runs/${newRun.id}`);
    } catch (err) {
      setRetestError(err instanceof Error ? err.message : String(err));
    } finally {
      setRetesting(false);
    }
  };

  if (loading) return <AppShell title="Report"><LoadingSkeleton /></AppShell>;
  if (error && !report) return <AppShell title="Error"><ErrorState message={error} onRetry={refetch} /></AppShell>;
  if (!report) return <AppShell title="Report not found"><ErrorState message="This report does not exist in this workspace." /></AppShell>;

  return (
    <AppShell
      section="AUDIT REPORT"
      title={`${report.verdict?.toUpperCase() ?? '—'} · ${report.app_name ?? 'Report'}`}
      provenance={report.provenance}
      provenanceSource="Report detail"
      actions={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn size="sm" variant="ghost" onClick={() => nav('/reports')}><ArrowLeft size={12} />Reports</Btn>
          {report.run_id && (
            <>
              <ReportDownloadButtons runId={report.run_id} />
              <Btn
                size="sm" variant="secondary"
                onClick={handleRetest}
                disabled={retesting}
                data-testid="retest-failed-btn"
              >
                <RotateCcw size={12} />{retesting ? 'Retesting…' : 'Retest failed'}
              </Btn>
            </>
          )}
          <Btn size="sm" variant="secondary" onClick={() => {
            // Safe: controlled URL points to local backend only
            const a = document.createElement('a');
            a.href = reportExportUrl(report!.id);
            a.download = `report-${report!.id}.json`;
            a.rel = 'noopener noreferrer';
            a.click();
          }}>
            <Download size={12} />Export JSON
          </Btn>
        </div>
      }
    >
      {retestError && (
        <div style={{ padding: '8px 12px', borderRadius: 7, marginBottom: 12,
          background: `${P.fail}22`, border: `1px solid ${P.fail}44`,
          fontSize: 12, color: P.fail }}>
          Retest failed: {retestError}
        </div>
      )}

      {/* Hero: editorial audit summary */}
      <div style={{
        background: `linear-gradient(135deg, ${P.cardHi}, ${P.card})`,
        border: `1px solid ${P.border}`, borderRadius: 12,
        padding: '28px 32px', marginBottom: 20, position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: `radial-gradient(60% 80% at 80% 20%, rgba(91,140,255,0.08), transparent)`,
        }} />
        <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
          letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
          AUDIT REPORT · {report.pack_name} · {report.verdict ? <StatusBadge kind={report.verdict as StatusKind} small /> : null}
        </div>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: P.text, lineHeight: 1.2, marginBottom: 8 }}>
          {report.app_name} is {report.verdict === 'pass' ? 'mostly working.' : report.verdict === 'fail' ? 'failing.' : 'partially working.'}
        </h1>
        {report.summary && (
          <p style={{ fontSize: 16, color: P.textDim, lineHeight: 1.5 }}>{report.summary}</p>
        )}

        {/* Metrics row */}
        <div style={{ display: 'flex', gap: 32, marginTop: 20 }}>
          {[
            { label: 'PASSED', value: report.pass_count ?? 0, color: P.pass },
            { label: 'FAILED', value: report.fail_count ?? 0, color: P.fail },
            { label: 'UNCLEAR', value: report.unclear_count ?? 0, color: P.unclear },
            { label: 'EVIDENCE', value: report.evidence_count ?? 0, color: P.accent },
          ].map(({ label, value, color }) => (
            <div key={label}>
              <div style={{ fontSize: 32, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      <Card>
        <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
          textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
          API SUMMARY
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
          {[
            { label: 'API STEPS', value: report.api_step_count ?? 0, color: P.accent },
            { label: 'API PASS', value: report.api_pass_count ?? 0, color: P.pass },
            { label: 'API FAIL', value: report.api_fail_count ?? 0, color: P.fail },
            { label: 'AVG API MS', value: report.api_avg_response_time_ms ?? 0, color: P.text },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                {label}
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Performance Summary */}
      {report.perf_total_checks !== undefined && report.perf_total_checks !== null && report.perf_total_checks > 0 && (
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            PERFORMANCE SUMMARY
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            {[
              { label: 'TOTAL CHECKS', value: report.perf_total_checks ?? 0, color: P.accent },
              { label: 'PASSED BUDGETS', value: report.perf_passed_budgets ?? 0, color: P.pass },
              { label: 'FAILED BUDGETS', value: report.perf_failed_budgets ?? 0, color: P.fail },
              { label: 'AVG PAGE LOAD', value: report.perf_avg_page_load_ms ? `${report.perf_avg_page_load_ms}ms` : '—', color: P.text },
              { label: 'AVG API LATENCY', value: report.perf_avg_api_response_time_ms ? `${report.perf_avg_api_response_time_ms}ms` : '—', color: P.text },
              { label: 'SLOWEST CHECK', value: report.perf_slowest_check_ms ? `${report.perf_slowest_check_ms}ms` : '—', color: P.fail },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Accessibility Summary */}
      {report.a11y_total_checks !== undefined && report.a11y_total_checks !== null && report.a11y_total_checks > 0 && (
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            ACCESSIBILITY SUMMARY
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            {[
              { label: 'TOTAL AUDITS', value: report.a11y_total_checks ?? 0, color: P.accent },
              { label: 'PASSED CHECKS', value: report.a11y_passed_checks ?? 0, color: P.pass },
              { label: 'FAILED CHECKS', value: report.a11y_failed_checks ?? 0, color: P.fail },
              { label: 'TOTAL VIOLATIONS', value: report.a11y_total_violations ?? 0, color: (report.a11y_total_violations ?? 0) > 0 ? P.fail : P.pass },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Visual Regression Summary */}
      {report.visual_total_checks !== undefined && report.visual_total_checks !== null && report.visual_total_checks > 0 && (
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            VISUAL REGRESSION SUMMARY
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            {[
              { label: 'TOTAL CHECKS', value: report.visual_total_checks ?? 0, color: P.accent },
              { label: 'PASSED CHECKS', value: report.visual_passed_checks ?? 0, color: P.pass },
              { label: 'FAILED CHECKS', value: report.visual_failed_checks ?? 0, color: P.fail },
              { label: 'AVG DIFF %', value: report.visual_avg_diff_percent !== undefined && report.visual_avg_diff_percent !== null ? `${(report.visual_avg_diff_percent * 100).toFixed(2)}%` : '—', color: P.text },
              { label: 'WORST DIFF %', value: report.visual_worst_diff_percent !== undefined && report.visual_worst_diff_percent !== null ? `${(report.visual_worst_diff_percent * 100).toFixed(2)}%` : '—', color: (report.visual_worst_diff_percent ?? 0) > 0 ? P.fail : P.pass },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Security Summary */}
      {report.security_total_checks !== undefined && report.security_total_checks !== null && report.security_total_checks > 0 && (
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            SECURITY SUMMARY
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            {[
              { label: 'TOTAL CHECKS', value: report.security_total_checks ?? 0, color: P.accent },
              { label: 'PASSED CHECKS', value: report.security_passed_checks ?? 0, color: P.pass },
              { label: 'FAILED CHECKS', value: report.security_failed_checks ?? 0, color: P.fail },
              { label: 'TOTAL FINDINGS', value: report.security_total_findings ?? 0, color: (report.security_total_findings ?? 0) > 0 ? P.fail : P.pass },
              { label: 'CRITICAL/HIGH', value: report.security_critical_findings ?? 0, color: (report.security_critical_findings ?? 0) > 0 ? P.fail : P.textMute },
              { label: 'WARNINGS', value: report.security_warning_findings ?? 0, color: (report.security_warning_findings ?? 0) > 0 ? P.unclear : P.textMute },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Findings */}
      {report.findings && report.findings.length > 0 && (
        <Card pad={0}>
          <div style={{ padding: '14px 18px', borderBottom: `1px solid ${P.border}` }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text }}>Findings</div>
          </div>
          <div style={{ padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {report.findings.map(f => <FindingCard key={f.id} finding={f} />)}
          </div>
        </Card>
      )}
    </AppShell>
  );
}
