import { Play, Plus } from 'lucide-react';
import { P, F } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge, ConfidenceMeter } from '../components/status/StatusBadge';
import { LoadingSkeleton, ErrorState, OfflineState, EmptyState, BlockedState, StaleDataState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get } from '../api/client';
import type { AppTarget, ValidationPack } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { PreviewBadge } from '../components/PreviewBadge';
import { PreviewSchedule } from '../components/validation/PreviewSchedule';
import { hasPreviewSteps, isPreviewAppType, PREVIEW_TOOLTIP } from '../config/capabilities';

function getPacks() { return get<ValidationPack[]>('/validation-packs'); }
function getApps() { return get<AppTarget[]>('/apps'); }

function MiniHistory({ history }: { history: boolean[] }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {history.map((pass, i) => (
        <div key={i} style={{
          width: 6, height: 14, borderRadius: 2,
          background: pass ? P.pass : P.fail, opacity: 0.8,
        }} />
      ))}
    </div>
  );
}

export default function ValidationPacksPage() {
  const nav = useWorkspaceNavigate();
  const { data, loading, error, refetch, isDemo, isOffline, fetchedAt } = useApi(getPacks, { demo: workspace => workspace.validationPacks });
  const { data: apps, loading: appsLoading } = useApi(getApps, { demo: workspace => workspace.apps });

  return (
    <AppShell section="03" title="Validation Packs">
      <PageHeader
        title="Validation Packs"
        subtitle={`${data?.length ?? 0} packs configured`}
        actions={
          <Btn variant="primary" onClick={() => nav('/packs/new')}>
            <Plus size={12} />New pack
          </Btn>
        }
      />

      <StaleDataState fetchedAt={fetchedAt} onRefresh={refetch} />

      {loading ? <LoadingSkeleton /> : isOffline ? <OfflineState onRetry={refetch} /> : error && !data ? <ErrorState message={error} onRetry={refetch} /> :
        !data?.length && !appsLoading && !apps?.length ? (
          <BlockedState
            title="Connect an app first"
            description="You need at least one connected app before creating validation packs. Connect an app to define what Inspectra should test."
            action={<Btn variant="primary" onClick={() => nav('/projects/new')}>Connect App</Btn>}
          />
        ) : !data?.length ? (
          <EmptyState
            title="No validation packs yet"
            description="Create a validation pack to define the test steps Inspectra will run against your app."
            action={<Btn variant="primary" onClick={() => nav('/packs/new')}>Create Pack</Btn>}
          />
        ) : (
        <div className="resp-table-wrap">
        <Card pad={0} style={{ minWidth: 640 }}>
          {/* Header row */}
          <div style={{ display: 'grid', padding: '10px 18px',
            gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1fr 1fr 100px',
            gap: 12, borderBottom: `1px solid ${P.border}` }}>
            {['Pack', 'Targets', 'Schedule', 'Readiness', 'Last run', 'Verdict', 'Actions'].map(h => (
              <div key={h} style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</div>
            ))}
          </div>

          {(data ?? []).map((pack, idx) => {
            const linkedApp = (apps ?? []).find(app => app.id === pack.app_id);
            const targetApps = (apps ?? []).filter(app =>
              app.id === pack.app_id
              || pack.target_app_ids?.includes(app.id)
              || pack.target_names?.includes(app.name)
            );
            const containsPreview = hasPreviewSteps(pack.steps ?? [])
              || isPreviewAppType(linkedApp?.app_type)
              || targetApps.some(app => isPreviewAppType(app.app_type));
            return (
            <div key={pack.id}
              style={{ display: 'grid', padding: '12px 18px', alignItems: 'center',
                gridTemplateColumns: '2fr 1.5fr 1fr 1fr 1fr 1fr 100px',
                gap: 12,
                borderBottom: idx < (data?.length ?? 0) - 1 ? `1px solid ${P.border}` : 'none',
                cursor: 'pointer', transition: 'background 0.1s',
              }}
              onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = P.cardHi}
              onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
              onClick={() => nav(`/packs/${pack.id}`)}
            >
              {/* Name + history */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{pack.name}</div>
                  {containsPreview && <PreviewBadge />}
                  <ProvenanceBadge provenance={pack.provenance} source="Validation pack row" />
                </div>
                {pack.history && <MiniHistory history={pack.history} />}
              </div>

              {/* Targets */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {(pack.target_names ?? []).map(t => (
                  <span key={t} style={{ padding: '2px 6px', borderRadius: 4, background: P.cardHi,
                    border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim }}>
                    {t}
                  </span>
                ))}
              </div>

              {/* Schedule */}
              <PreviewSchedule schedule={pack.schedule} />

              {/* Readiness */}
              <StatusBadge kind={(pack.readiness ?? 'missing') as StatusKind} small />

              {/* Last run */}
              <div style={{ fontSize: 11, color: P.textMute }}>
                {pack.last_run_at ? new Date(pack.last_run_at).toLocaleDateString() : 'never'}
              </div>

              {/* Verdict */}
              {pack.last_verdict ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusBadge kind={pack.last_verdict as StatusKind} small />
                  {pack.avg_pass_rate !== undefined && pack.avg_pass_rate > 0 && (
                    <ConfidenceMeter value={pack.avg_pass_rate} width={50} />
                  )}
                </div>
              ) : <span style={{ color: P.textFaint, fontSize: 11 }}>—</span>}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 6 }} onClick={e => e.stopPropagation()}>
                <Btn size="sm" variant="ghost" disabled title="Not available yet">Dry run</Btn>
                <Btn
                  size="sm"
                  variant="primary"
                  disabled={isDemo || containsPreview}
                  demoWrite
                  title={containsPreview ? PREVIEW_TOOLTIP : !isDemo ? `Review and run ${pack.name}` : undefined}
                  onClick={() => nav(`/packs/${pack.id}`)}
                >
                  <Play size={10} />Review &amp; run
                </Btn>
              </div>
            </div>
          );})}
        </Card>
        </div>
        )}
    </AppShell>
  );
}
