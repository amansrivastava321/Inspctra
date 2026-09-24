import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Play, Stethoscope, Trash2 } from 'lucide-react';
import { P, F, STATUS_MAP } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { LoadingSkeleton, ErrorState, OfflineState, EmptyState, StaleDataState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, del } from '../api/client';
import type { AppTarget } from '../types/api';
import { DEMO_READ_ONLY_TOOLTIP, useWorkspaceMode } from '../state/WorkspaceModeContext';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { PreviewBadge } from '../components/PreviewBadge';
import { isPreviewAppType, PREVIEW_TOOLTIP } from '../config/capabilities';

function getApps() { return get<AppTarget[]>('/apps'); }

const TAB_FILTERS = ['All', 'Web', 'Mobile', 'Desktop', 'API'];

export default function ProjectsPage() {
  const nav = useNavigate();
  const { isDemo, toWorkspacePath } = useWorkspaceMode();
  const { data, loading, error, refetch, isOffline, fetchedAt } = useApi(getApps, { demo: workspace => workspace.apps });
  const go = (path: string) => nav(toWorkspacePath(path));

  const count = data?.length ?? 0;
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [runModalApp, setRunModalApp] = useState<AppTarget | null>(null);

  const handleDelete = async (app: AppTarget) => {
    if (isDemo) return;
    if (!window.confirm(`Remove "${app.name}"? This cannot be undone.`)) return;
    setDeletingId(app.id);
    setDeleteError('');
    try {
      await del(`/apps/${app.id}`);
      await refetch();
    } catch (err) {
      setDeleteError(String(err instanceof Error ? err.message : 'Delete failed'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <AppShell section="projects" title={`${count} app${count !== 1 ? 's' : ''} connected`}>
      <PageHeader
        title="Projects"
        subtitle={count > 0 ? `${count} app${count !== 1 ? 's' : ''} connected` : 'No apps connected yet'}
        actions={
          <Btn variant="primary" demoWrite onClick={() => go('/projects/new')}>
            <Plus size={12} />Connect app
          </Btn>
        }
      />

      <StaleDataState fetchedAt={fetchedAt} onRefresh={refetch} />

      {/* Filter tabs — disabled until filter state is implemented */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {TAB_FILTERS.map((f, i) => (
          <button key={f} disabled={i > 0} title={i > 0 ? 'Filtering not yet available' : undefined}
            style={{
              padding: '5px 12px', borderRadius: 6, fontSize: 12,
              cursor: i === 0 ? 'default' : 'not-allowed',
              background: i === 0 ? P.cardHi : 'transparent',
              border: `1px solid ${i === 0 ? P.border : 'transparent'}`,
              color: i === 0 ? P.text : P.textMute,
              opacity: i === 0 ? 1 : 0.4,
            }}>
            {f}{i === 0 && count > 0 ? ` · ${count}` : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : isOffline ? (
        <OfflineState onRetry={refetch} />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : count === 0 ? (
        <EmptyState
          title="No apps connected yet"
          description="Connect your first app to start validating it with Inspectra."
          action={
            <Btn variant="primary" demoWrite onClick={() => go('/projects/new')}>
              <Plus size={12} />Connect first app
            </Btn>
          }
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
          {(data ?? []).map(app => {
            const hasIssue = app.status === 'missing' || app.status === 'perm';
            const preview = isPreviewAppType(app.app_type);
            return (
              <Card key={app.id} style={{ cursor: 'pointer' }} pad={16}>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 9, background: P.cardHi,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 16, fontWeight: 700, color: P.textDim,
                    }}>
                      {app.name[0].toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: P.text }}>{app.name}</div>
                      <div style={{ fontSize: 11, color: P.textMute }}>
                        {app.app_type}{app.platform ? ` · ${app.platform}` : ''}
                      </div>
                      {preview && <PreviewBadge style={{ marginTop: 4 }} />}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ProvenanceBadge provenance={app.provenance} source="App card" />
                    {app.status && <StatusBadge kind={app.status as StatusKind} small />}
                  </div>
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
                  {[
                    { label: 'PASS', value: app.pass_rate !== undefined ? `${app.pass_rate}%` : '—', color: app.pass_rate !== undefined ? P.pass : P.textMute },
                    { label: 'RUNS', value: app.total_runs ?? 0, color: P.text },
                    { label: 'OPEN', value: app.open_issues ?? 0, color: (app.open_issues ?? 0) > 0 ? P.fail : P.textMute },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono, marginBottom: 2 }}>{label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
                    </div>
                  ))}
                  <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                    <div style={{ fontSize: 11, color: P.textMute, marginBottom: 2 }}>LAST RUN</div>
                    <div style={{ fontSize: 12, color: P.textDim }}>
                      {app.last_run_at ? new Date(app.last_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'never'}
                    </div>
                  </div>
                </div>

                {/* Issue banners — only when status is actually set by backend */}
                {hasIssue && app.status === 'missing' && (
                  <div style={{ padding: '6px 10px', borderRadius: 6,
                    background: P.unclearSoft, border: `1px solid ${P.unclear}33`,
                    fontSize: 11, color: P.unclear, marginBottom: 10 }}>
                    ⚠ Setup required — run Runtime Doctor
                  </div>
                )}
                {hasIssue && app.status === 'perm' && (
                  <div style={{ padding: '6px 10px', borderRadius: 6,
                    background: P.accentSoft, border: `1px solid ${P.accent}33`,
                    fontSize: 11, color: P.accent, marginBottom: 10 }}>
                    🔒 Permission needed — run Runtime Doctor
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: 8 }}>
                  <Btn size="sm" variant="secondary" onClick={() => go(`/apps/${app.id}`)}>Open</Btn>
                  <Btn size="sm" variant="ghost" onClick={() => go('/doctor')}>
                    <Stethoscope size={11} />Doctor
                  </Btn>
                  <button
                    data-testid={`remove-app-${app.id}`}
                    title={isDemo ? DEMO_READ_ONLY_TOOLTIP : 'Remove app'}
                    disabled={isDemo || deletingId === app.id}
                    onClick={() => handleDelete(app)}
                    style={{
                      background: 'none', border: 'none', cursor: isDemo || deletingId === app.id ? 'not-allowed' : 'pointer',
                      color: P.fail, display: 'inline-flex', alignItems: 'center',
                      padding: '5px 6px', borderRadius: 7, opacity: deletingId === app.id ? 0.5 : 1,
                    }}>
                    <Trash2 size={11} />
                  </button>
                  <Btn size="sm" variant="primary" demoWrite style={{ marginLeft: 'auto' }}
                    disabled={preview}
                    title={preview ? PREVIEW_TOOLTIP : undefined}
                    onClick={() => setRunModalApp(app)}>
                    <Play size={11} />Run
                  </Btn>
                </div>
              </Card>
            );
          })}

          {/* Add app card */}
          <Card style={{ cursor: 'pointer', border: `1px dashed ${P.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            minHeight: 180 }}
            pad={16}>
            <div onClick={() => { if (!isDemo) go('/projects/new'); }} title={isDemo ? DEMO_READ_ONLY_TOOLTIP : undefined}
              style={{ textAlign: 'center', opacity: isDemo ? 0.5 : 1 }}>
              <div style={{ width: 40, height: 40, borderRadius: 99, background: P.cardHi,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 10px' }}>
                <Plus size={18} color={P.textMute} />
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: P.textDim }}>Connect new app</div>
              <div style={{ fontSize: 11, color: P.textMute, marginTop: 4 }}>Walk the setup wizard</div>
            </div>
          </Card>
        </div>
      )}
      {deleteError && (
        <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 7,
          background: P.failSoft, border: `1px solid ${P.fail}33`,
          fontSize: 12, color: P.fail }}>
          Delete failed: {deleteError}
          <button onClick={() => setDeleteError('')} style={{ marginLeft: 8, background: 'none', border: 'none', color: P.fail, cursor: 'pointer', fontSize: 11 }}>✕</button>
        </div>
      )}

      {/* Run modal — select or create pack for this app */}
      {runModalApp && (
        <div data-testid="run-modal-backdrop" onClick={() => setRunModalApp(null)} style={{
          position: 'fixed', inset: 0, zIndex: 9000, background: 'rgba(0,0,0,0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div data-testid="run-modal" onClick={e => e.stopPropagation()} style={{
            background: P.card, borderRadius: 12, padding: 24,
            maxWidth: 400, width: '90%', border: `1px solid ${P.border}`,
            boxShadow: '0 16px 48px rgba(0,0,0,0.4)',
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: P.text, marginBottom: 8 }}>
              Run validation pack
            </div>
            <p style={{ fontSize: 13, color: P.textDim, marginBottom: 20 }}>
              Select or create a validation pack to run against <strong>{runModalApp.name}</strong>.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Btn variant="ghost" onClick={() => setRunModalApp(null)}>Cancel</Btn>
              <Btn variant="secondary" onClick={() => { setRunModalApp(null); go('/packs'); }}>
                View packs
              </Btn>
              <Btn variant="primary" demoWrite onClick={() => { setRunModalApp(null); go('/packs/new'); }}>
                Create pack
              </Btn>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
