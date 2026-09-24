import React from 'react';
import { useLocation } from 'react-router-dom';
import { Play, RefreshCw } from 'lucide-react';
import { P, F } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge, ConfidenceMeter } from '../components/status/StatusBadge';
import { LoadingSkeleton, ErrorState, OfflineState, EmptyState, BlockedState, StaleDataState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get } from '../api/client';
import type { LiveRunRecord, ValidationPack } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { ProvenanceBadge } from '../components/ProvenanceBadge';

function getRuns() { return get<LiveRunRecord[]>('/runs?limit=50'); }
function getPacks() { return get<ValidationPack[]>('/validation-packs'); }

export default function LiveRunsPage() {
  const nav = useWorkspaceNavigate();
  const { data, loading, error, refetch, isOffline, fetchedAt } = useApi(getRuns, { demo: workspace => workspace.liveRuns });
  const { data: packs, loading: packsLoading } = useApi(getPacks, { demo: workspace => workspace.validationPacks });
  const { search } = useLocation();
  const manualOnly = new URLSearchParams(search).get('mode') === 'manual';
  const visibleRuns = manualOnly
    ? (data ?? []).filter(run => run.execution_mode === 'manual')
    : (data ?? []);
  const pageTitle = manualOnly ? 'Manual Tests' : 'Live Test Runs';

  return (
    <AppShell section="04" title={pageTitle}>
      <PageHeader
        title={pageTitle}
        subtitle={`${visibleRuns.length} ${manualOnly ? 'manual ' : ''}runs`}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="ghost" size="sm" onClick={refetch}><RefreshCw size={12} /></Btn>
            <Btn variant="primary" demoWrite onClick={() => nav('/packs')}>
              <Play size={12} />Start new run
            </Btn>
          </div>
        }
      />

      <StaleDataState fetchedAt={fetchedAt} onRefresh={refetch} />

      {loading ? <LoadingSkeleton /> : isOffline ? <OfflineState onRetry={refetch} /> : error && !data ? <ErrorState message={error} onRetry={refetch} /> :
        !visibleRuns.length && !packsLoading && !packs?.length ? (
          <BlockedState
            title="Create a validation pack first"
            description="You need at least one validation pack before running tests. Create a pack to define what Inspectra will test."
            action={<Btn variant="primary" onClick={() => nav('/packs/new')}>Create Pack</Btn>}
          />
        ) : !visibleRuns.length ? (
          <EmptyState
            title={manualOnly ? 'No manual tests yet' : 'No runs yet'}
            description="Execute a validation pack to see test results here."
            action={<Btn variant="primary" onClick={() => nav('/packs')}>Run a Pack</Btn>}
          />
        ) : (
          <div className="resp-table-wrap">
          <Card pad={0} style={{ minWidth: 580 }}>
            <div style={{ display: 'grid', padding: '10px 18px', gap: 12,
              gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1fr 80px',
              borderBottom: `1px solid ${P.border}` }}>
              {['Run', 'Pack · App', 'Status', 'Confidence', 'Started', ''].map(h => (
                <div key={h} style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</div>
              ))}
            </div>

            {visibleRuns.map((run, idx) => {
              const vKind = (run.verdict ?? run.status) as StatusKind;
              return (
                <div key={run.id}
                  onClick={() => nav(`/runs/${run.id}`)}
                  style={{ display: 'grid', padding: '11px 18px', alignItems: 'center',
                    gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1fr 80px',
                    gap: 12, cursor: 'pointer', transition: 'background 0.1s',
                    borderBottom: idx < visibleRuns.length - 1 ? `1px solid ${P.border}` : 'none' }}
                  onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => e.currentTarget.style.background = P.cardHi}
                  onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => e.currentTarget.style.background = 'transparent'}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 500, color: P.text, fontFamily: F.mono }}>
                      {run.id.slice(0, 12)}
                    </div>
                    <div style={{ fontSize: 11, color: P.textMute }}>
                      {run.step_results.length} steps · {run.platform ?? '—'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: P.text }}>{run.pack_name ?? run.pack_id?.slice(0, 16)}</div>
                    <div style={{ fontSize: 11, color: P.textMute }}>{run.app_name ?? '—'}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <StatusBadge kind={vKind} small />
                    <ProvenanceBadge provenance={run.provenance} source="Live run row" />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {run.confidence !== undefined && (
                      <>
                        <ConfidenceMeter value={run.confidence} width={60} />
                        <span style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>{run.confidence}%</span>
                      </>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: P.textMute }}>
                    {run.started_at ? new Date(run.started_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                  </div>
                  <Btn size="sm" variant="ghost" onClick={e => { e?.stopPropagation(); nav(`/runs/${run.id}`); }}>
                    Open
                  </Btn>
                </div>
              );
            })}
          </Card>
          </div>
        )}
    </AppShell>
  );
}
