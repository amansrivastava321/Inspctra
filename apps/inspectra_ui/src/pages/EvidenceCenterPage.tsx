import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Filter } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { EvidenceCard } from '../components/evidence/EvidenceCard';
import { LoadingSkeleton, ErrorState, OfflineState, EmptyState, BlockedState, StaleDataState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, evidenceDownloadUrl } from '../api/client';
import type {
  AccessibilitySummaryMetadata,
  AccessibilityViolationsMetadata,
  EvidenceFile,
  EvidenceType,
  LiveRunRecord,
  PerformanceSummaryMetadata,
  SecurityFindingsMetadata,
  VisualDiffMetadata,
  WebTimingMetadata,
} from '../types/api';

const percent = (value?: number) => (typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '—');

/** Visual diff verdict, or null when the metadata does not carry both numbers. */
function visualDiffPassed(meta: VisualDiffMetadata): boolean | null {
  return typeof meta.diff_ratio === 'number' && typeof meta.threshold === 'number'
    ? meta.diff_ratio <= meta.threshold
    : null;
}

/** `metadata_json` is free-form JSON; this is the one place it is read as a per-type shape. */
function metaOf<T>(file: EvidenceFile): T {
  return (file.metadata_json ?? {}) as T;
}
import { ProvenanceBadge } from '../components/ProvenanceBadge';

function getEvidence() { return get<EvidenceFile[]>('/evidence'); }
function getRuns() { return get<LiveRunRecord[]>('/runs?limit=1'); }

const TABS: { key: EvidenceType | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'screenshot', label: 'Screenshots' },
  { key: 'log', label: 'Logs' },
  { key: 'api', label: 'API' },
  { key: 'db', label: 'Database' },
  { key: 'ai', label: 'AI Oracle' },
  { key: 'trace', label: 'Traces' },
  { key: 'performance_summary', label: 'Performance' },
  { key: 'accessibility_summary', label: 'Accessibility' },
  { key: 'visual_diff', label: 'Visual Diffs' },
  { key: 'security_findings', label: 'Security' },
];

function isApiEvidenceType(type: EvidenceType | string | undefined) {
  return type === 'api' || type === 'api_request' || type === 'api_response' || type === 'api_assertion';
}

function isA11yEvidenceType(type: EvidenceType | string | undefined) {
  return type === 'accessibility_summary' || type === 'accessibility_violations';
}

export default function EvidenceCenterPage() {
  const nav = useNavigate();
  const { data, loading, error, refetch, isOffline, fetchedAt } = useApi(getEvidence, { demo: workspace => workspace.evidence });
  const { data: runs, loading: runsLoading } = useApi(getRuns, { demo: workspace => workspace.liveRuns });
  const [tab, setTab] = useState<EvidenceType | 'all'>('all');
  const [selected, setSelected] = useState<EvidenceFile | null>(null);

  const filtered = tab === 'all'
    ? (data ?? [])
    : (data ?? []).filter(ev => {
        const evidenceType = ev.evidence_type ?? ev.type;
        if (tab === 'performance_summary') {
          return evidenceType === 'performance_summary' || evidenceType === 'web_timing' || evidenceType === 'api_timing';
        }
        if (tab === 'accessibility_summary') {
          return isA11yEvidenceType(evidenceType);
        }
        return tab === 'api' ? isApiEvidenceType(evidenceType) : evidenceType === tab;
      });

  const handleDownload = (ev: EvidenceFile) => {
    if (!(ev.file_path || ev.path || ev.relative_path)) return;
    // Safe: controlled URL, no external domain
    const a = document.createElement('a');
    a.href = evidenceDownloadUrl(ev.id);
    a.download = `evidence-${ev.id}`;
    a.rel = 'noopener noreferrer';
    a.click();
  };

  return (
    <AppShell section="05" title="Evidence Center">
      <PageHeader
        title="Evidence Center"
        subtitle={`${data?.length ?? 0} artifacts collected`}
        actions={
          <Btn variant="ghost" size="sm"><Filter size={12} />Filter</Btn>
        }
      />

      {/* Type tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 16,
        borderBottom: `1px solid ${P.border}`, paddingBottom: 0 }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding: '6px 14px', cursor: 'pointer', fontSize: 12, background: 'none',
            borderBottom: tab === t.key ? `2px solid ${P.accent}` : '2px solid transparent',
            color: tab === t.key ? P.accent : P.textMute,
            fontWeight: tab === t.key ? 500 : 400,
          }}>
            {t.label}
          </button>
        ))}
      </div>

      <StaleDataState fetchedAt={fetchedAt} onRefresh={refetch} />

      {loading ? <LoadingSkeleton /> : isOffline ? <OfflineState onRetry={refetch} /> : error && !data ? <ErrorState message={error} onRetry={refetch} /> :
        filtered.length === 0 && tab === 'all' && !runsLoading && !runs?.length ? (
          <BlockedState
            title="Run tests to collect evidence"
            description="Evidence is captured during live test runs — screenshots, logs, API exchanges, and more. Execute a validation pack to start collecting."
            action={<Btn variant="primary" onClick={() => nav('/packs')}>Run a Pack</Btn>}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={tab === 'all' ? 'No evidence captured yet' : `No ${tab} evidence`}
            description={tab === 'all' ? 'Run tests to collect screenshots, logs, and reports.' : `No ${tab} artifacts from any test runs yet.`}
            action={tab === 'all' ? <Btn variant="primary" onClick={() => nav('/packs')}>Run a Pack</Btn> : undefined}
          />
        ) : (
          <div style={{ display: 'flex', gap: 14, minHeight: 400 }}>
            {/* Grid */}
            <div style={{ flex: 1, display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10, alignContent: 'start' }}>
              {filtered.map(ev => (
                <EvidenceCard
                  key={ev.id}
                  ev={ev}
                  onClick={() => setSelected(ev)}
                />
              ))}
            </div>

            {/* Detail drawer */}
            {selected && (
              <div style={{ width: 300, flexShrink: 0 }}>
                <Card>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: P.text }}>Evidence Detail</div>
                      <ProvenanceBadge provenance={selected.provenance} source="Evidence detail" />
                    </div>
                    <button onClick={() => setSelected(null)} style={{ color: P.textMute, fontSize: 16 }}>×</button>
                  </div>

                  {[
                    { label: 'Type', value: selected.evidence_type ?? selected.type },
                    { label: 'Run', value: selected.run_id.slice(0, 12) },
                    { label: 'Step', value: selected.step_id?.slice(0, 12) ?? '—' },
                    { label: 'Strength', value: selected.strength ?? '—' },
                    { label: 'Created', value: selected.created_at ? new Date(selected.created_at).toLocaleString() : '—' },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: 11, color: P.textMute }}>{label}</span>
                      <span style={{ fontSize: 11, color: P.text, fontFamily: F.mono }}>{value}</span>
                    </div>
                  ))}

                  {selected.description && (
                    <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi,
                      fontSize: 12, color: P.textDim, marginTop: 8 }}>
                      {selected.description}
                    </div>
                  )}

                  {selected.content_preview && (
                    <div style={{ padding: '8px 10px', borderRadius: 6, background: P.bg,
                      border: `1px solid ${P.border}`, fontFamily: F.mono, fontSize: 11,
                      color: P.textMute, marginTop: 8 }}>
                      {/* Safe text display — no innerHTML */}
                      {selected.content_preview}
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'performance_summary' || selected.type === 'performance_summary') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>PERFORMANCE SUMMARY PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        <div><strong>Metric Name:</strong> {String(metaOf<PerformanceSummaryMetadata>(selected).metric_name || '')}</div>
                        <div><strong>Measured:</strong> {String(metaOf<PerformanceSummaryMetadata>(selected).measured_ms || '')}ms</div>
                        <div><strong>Budget:</strong> {String(metaOf<PerformanceSummaryMetadata>(selected).budget_ms || '')}ms</div>
                        <div><strong>Warn Threshold:</strong> {String(metaOf<PerformanceSummaryMetadata>(selected).warn_ms || '')}ms</div>
                        <div><strong>Verdict:</strong> <span style={{ color: metaOf<PerformanceSummaryMetadata>(selected).verdict === 'fail' ? P.fail : (metaOf<PerformanceSummaryMetadata>(selected).verdict === 'warn' ? P.unclear : P.pass) }}>{metaOf<PerformanceSummaryMetadata>(selected).verdict}</span></div>
                      </div>
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'web_timing' || selected.type === 'web_timing') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>WEB TIMING METRICS PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        {Object.entries(metaOf<WebTimingMetadata>(selected).metrics || {}).map(([k, v]) => (
                          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>{k}</span>
                            <span style={{ fontSize: 11, color: P.text, fontWeight: 500 }}>{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'accessibility_summary' || selected.type === 'accessibility_summary') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>ACCESSIBILITY SUMMARY PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        <div><strong>Total Violations:</strong> {String(metaOf<AccessibilitySummaryMetadata>(selected).total_violations ?? '')}</div>
                        <div><strong>Max Budget:</strong> {String(metaOf<AccessibilitySummaryMetadata>(selected).budget_violations ?? '')}</div>
                        <div><strong>Warn Threshold:</strong> {String(metaOf<AccessibilitySummaryMetadata>(selected).warn_violations ?? '')}</div>
                        <div><strong>Verdict:</strong> <span style={{ color: metaOf<AccessibilitySummaryMetadata>(selected).verdict === 'fail' ? P.fail : (metaOf<AccessibilitySummaryMetadata>(selected).verdict === 'warn' ? P.unclear : P.pass) }}>{metaOf<AccessibilitySummaryMetadata>(selected).verdict}</span></div>
                      </div>
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'accessibility_violations' || selected.type === 'accessibility_violations') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>ACCESSIBILITY VIOLATIONS PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        <div><strong>Total Violations:</strong> {String(metaOf<AccessibilityViolationsMetadata>(selected).a11y_result?.total_violations ?? '')}</div>
                        <div><strong>Max Budget:</strong> {String(metaOf<AccessibilityViolationsMetadata>(selected).budget_violations ?? '')}</div>
                        <div><strong>Warn Threshold:</strong> {String(metaOf<AccessibilityViolationsMetadata>(selected).warn_violations ?? '')}</div>
                      </div>
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'visual_diff' || selected.type === 'visual_diff') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>VISUAL DIFF PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        <div><strong>Diff Ratio:</strong> {percent(metaOf<VisualDiffMetadata>(selected).diff_ratio)}</div>
                        <div><strong>Threshold:</strong> {percent(metaOf<VisualDiffMetadata>(selected).threshold)}</div>
                        <div><strong>Verdict:</strong> <span style={{ color: visualDiffPassed(metaOf<VisualDiffMetadata>(selected)) === null ? P.textMute : visualDiffPassed(metaOf<VisualDiffMetadata>(selected)) ? P.pass : P.fail }}>
                          {visualDiffPassed(metaOf<VisualDiffMetadata>(selected)) === null ? 'UNKNOWN' : visualDiffPassed(metaOf<VisualDiffMetadata>(selected)) ? 'PASSED' : 'FAILED'}
                        </span></div>
                      </div>
                    </div>
                  )}

                  {selected.metadata_json && (selected.evidence_type === 'security_findings' || selected.type === 'security_findings') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>SECURITY FINDINGS PREVIEW</div>
                      <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi, border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                        <div><strong>Total Findings:</strong> {String(metaOf<SecurityFindingsMetadata>(selected).findings?.length ?? 0)}</div>
                        <div><strong>Critical/High:</strong> {String(metaOf<SecurityFindingsMetadata>(selected).findings?.filter((f) => ['critical', 'high'].includes(f.severity)).length ?? 0)}</div>
                        <div><strong>Warnings:</strong> {String(metaOf<SecurityFindingsMetadata>(selected).findings?.filter((f) => f.severity === 'medium').length ?? 0)}</div>
                      </div>
                      <div style={{ fontSize: 9, color: P.pass, marginTop: 2, fontStyle: 'italic' }}>
                        ℹ Sensitive headers (Authorization, Cookie, Set-Cookie) are redacted.
                      </div>
                    </div>
                  )}

                  {(selected.evidence_type === 'screenshot' || selected.type === 'screenshot' || selected.evidence_type === 'visual_diff' || selected.type === 'visual_diff') && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, marginBottom: 4 }}>
                        {selected.evidence_type === 'visual_diff' || selected.type === 'visual_diff' ? 'DIFF OVERLAY PREVIEW' : 'IMAGE PREVIEW'}
                      </div>
                      <img
                        src={evidenceDownloadUrl(selected.id)}
                        alt={selected.name || 'Evidence image'}
                        style={{ width: '100%', borderRadius: 6, border: `1px solid ${P.border}`, background: '#0a0a0c' }}
                      />
                    </div>
                  )}

                  {selected.metadata_json && (
                    <div style={{ padding: '8px 10px', borderRadius: 6, background: P.bg,
                      border: `1px solid ${P.border}`, fontFamily: F.mono, fontSize: 11,
                      color: P.textMute, marginTop: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify(selected.metadata_json, null, 2)}
                    </div>
                  )}

                  {(selected.file_path || selected.path || selected.relative_path) && (
                    <Btn variant="secondary" style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}
                      onClick={() => handleDownload(selected)}>
                      <Download size={12} />Download
                    </Btn>
                  )}
                </Card>
              </div>
            )}
          </div>
        )}
    </AppShell>
  );
}
