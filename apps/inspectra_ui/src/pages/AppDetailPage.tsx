import { useCallback, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Trash2, Plus, Play } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn, StatCard } from '../components/layout/AppShell';
import { LoadingSkeleton, ErrorState, OfflineState, PartialConfigBanner } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, del, post } from '../api/client';
import type { AppTarget, AppMapDraft, ValidationPack, Provenance } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { PreviewBadge } from '../components/PreviewBadge';
import { isPreviewAppType, PREVIEW_TOOLTIP } from '../config/capabilities';

// Backend AppTarget shape
interface BackendApp {
  id: string;
  name: string;
  app_type: string;
  project_id: string;
  base_url?: string;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  provenance?: Provenance;
  // Discovery / source fields (optional)
  source_type?: string;
  source_path?: string;
  source_url?: string;
  launch_command?: string;
  working_directory?: string;
  discovery_id?: string;
  detected_stack?: string;
}

const APP_TYPE_LABELS: Record<string, string> = {
  web:       '🌐 Web',
  desktop:   '💻 Desktop',
  mobile:    '📱 Mobile',
  api:       '🔌 API / Service',
  ai_app:    '🤖 AI App',
  '3rd_party': '🔗 3rd Party',
};

export default function AppDetailPage() {
  const { appId } = useParams<{ appId: string }>();
  const nav = useWorkspaceNavigate();

  const getApp = useCallback(() => get<BackendApp>(`/apps/${appId}`), [appId]);
  const { data: app, loading, error, refetch, isOffline } = useApi(getApp, {
    demo: workspace => workspace.apps.find(item => item.id === appId) as unknown as BackendApp,
  });

  // App map — fetch on load, allow generate-on-demand
  const getAppMap = useCallback(
    () => get<AppMapDraft | null>(`/apps/${appId}/app-map`),
    [appId],
  );
  const { data: fetchedMap, refetch: refetchMap } = useApi(getAppMap, {
    demo: null as unknown as AppMapDraft,
  });
  const [appMap, setAppMap] = useState<AppMapDraft | null>(null);
  const [generatingMap, setGeneratingMap] = useState(false);
  const [mapError, setMapError] = useState('');

  // Merge fetched map into local state once loaded.
  // Guard: only accept if it looks like a real AppMapDraft (has app_map_id).
  if (fetchedMap && !appMap && (fetchedMap as AppMapDraft).app_map_id) setAppMap(fetchedMap);

  const handleGenerateMap = async () => {
    if (!appId) return;
    setGeneratingMap(true);
    setMapError('');
    try {
      const map = await post<AppMapDraft>(`/apps/${appId}/app-map/generate`, {});
      setAppMap(map);
      refetchMap();
    } catch (err) {
      setMapError(String(err instanceof Error ? err.message : err));
    } finally {
      setGeneratingMap(false);
    }
  };

  // App-specific validation packs
  const getAppPacks = useCallback(
    () => get<ValidationPack[]>(`/validation-packs?app_id=${appId}`),
    [appId],
  );
  const { data: appPacks, loading: packsLoading } = useApi(getAppPacks, {
    demo: workspace => workspace.validationPacks.filter(pack => pack.app_id === appId || pack.target_app_ids?.includes(appId ?? '')),
  });

  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const handleDelete = async () => {
    if (!app) return;
    if (!window.confirm(`Delete "${app.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await del(`/apps/${appId}`);
      nav('/projects');
    } catch (err) {
      setDeleteError(String(err instanceof Error ? err.message : 'Delete failed'));
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <AppShell title="Loading…"><LoadingSkeleton /></AppShell>;
  if (isOffline) return <AppShell title="App"><OfflineState onRetry={refetch} /></AppShell>;
  if (error && !app) return <AppShell title="Error"><ErrorState message={error} onRetry={refetch} /></AppShell>;
  if (!app) return <AppShell title="App not found"><ErrorState message="This app does not exist in this workspace." /></AppShell>;
  const isPreviewApp = isPreviewAppType(app.app_type);

  return (
    <AppShell section="app" title={app.name}>
      <PageHeader
        title={app.name}
        subtitle={APP_TYPE_LABELS[app.app_type] ?? app.app_type}
        provenance={app.provenance}
        provenanceSource="App detail"
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn size="sm" variant="ghost" onClick={() => nav('/projects')}>
              <ArrowLeft size={12} />Projects
            </Btn>
            <Btn size="sm" variant="ghost" onClick={refetch}>
              <RefreshCw size={12} />
            </Btn>
          </div>
        }
      />

      {isPreviewApp && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
          padding: '9px 12px', borderRadius: 7, background: `${P.textMute}12`,
          border: `1px solid ${P.textMute}33`, color: P.textDim, fontSize: 12,
        }}>
          <PreviewBadge />
          This app type is in preview. Its configuration is preserved, but tests cannot be executed yet.
        </div>
      )}

      {/* Stats row */}
      <div className="resp-stats-row" style={{ marginBottom: 20 }}>
        <StatCard label="App type" value={APP_TYPE_LABELS[app.app_type] ?? app.app_type}
          provenance={app.provenance} provenanceSource="App detail metric" />
        <StatCard label="Tags" value={app.tags.length > 0 ? app.tags.join(', ') : '—'}
          provenance={app.provenance} provenanceSource="App detail metric" />
        <StatCard label="Created" value={new Date(app.created_at).toLocaleDateString()}
          provenance={app.provenance} provenanceSource="App detail metric" />
      </div>

      <div className="resp-detail-grid">
        {/* Details */}
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            APP DETAILS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
            <div>
              <span style={{ color: P.textMute }}>Name: </span>
              <span style={{ color: P.text, fontWeight: 500 }}>{app.name}</span>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Type: </span>
              <span style={{ color: P.text }}>{APP_TYPE_LABELS[app.app_type] ?? app.app_type}</span>
              {isPreviewApp && <PreviewBadge style={{ marginLeft: 6 }} />}
            </div>
            {app.base_url && (
              <div>
                <span style={{ color: P.textMute }}>URL: </span>
                <a href={app.base_url} target="_blank" rel="noopener noreferrer"
                  style={{ color: P.accent, fontFamily: F.mono, fontSize: 11 }}>
                  {app.base_url}
                </a>
              </div>
            )}
            {app.description && (
              <div>
                <span style={{ color: P.textMute }}>Description: </span>
                <span style={{ color: P.textDim }}>{app.description}</span>
              </div>
            )}
            {app.tags.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ color: P.textMute }}>Tags: </span>
                {app.tags.map(tag => (
                  <span key={tag} style={{
                    padding: '2px 7px', borderRadius: 4, fontSize: 11,
                    background: P.cardHi, border: `1px solid ${P.border}`, color: P.textDim,
                  }}>
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Metadata + actions */}
        <Card>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            METADATA
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
            <div>
              <span style={{ color: P.textMute }}>App ID: </span>
              <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>{app.id}</code>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Project ID: </span>
              <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>{app.project_id}</code>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Created: </span>
              <span style={{ color: P.text }}>{new Date(app.created_at).toLocaleString()}</span>
            </div>
            <div>
              <span style={{ color: P.textMute }}>Updated: </span>
              <span style={{ color: P.text }}>{new Date(app.updated_at).toLocaleString()}</span>
            </div>
          </div>

          <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Btn variant="primary" demoWrite
              onClick={() => nav(`/packs/new?app_id=${app.id}&project_id=${app.project_id}`)}>
              <Plus size={12} />Create validation pack
            </Btn>
            <Btn variant="ghost" onClick={() => nav('/doctor')}>
              Run Runtime Doctor
            </Btn>
            <Btn variant="danger" demoWrite onClick={handleDelete} disabled={deleting}>
              <Trash2 size={12} />{deleting ? 'Deleting…' : 'Delete app'}
            </Btn>
            {deleteError && (
              <div style={{ fontSize: 11, color: P.fail, padding: '6px 8px', borderRadius: 6,
                background: P.failSoft, border: `1px solid ${P.fail}33` }}>
                {deleteError}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* App Map */}
      <Card style={{ marginTop: 20 }} data-testid="app-map-section">
        <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
          textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
          APP MAP
        </div>

        {!appMap && !generatingMap && (
          <div data-testid="app-map-empty" style={{ padding: '16px 0' }}>
            <div style={{ fontSize: 13, color: P.textDim, marginBottom: 10 }}>
              No app map yet. Generate one to see entry points, testable surfaces, and risk areas.
            </div>
            <button
              data-testid="generate-app-map-btn"
              onClick={handleGenerateMap}
              style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                border: `1px solid ${P.accent}`, background: P.accentSoft,
                color: P.accent, cursor: 'pointer',
              }}
            >
              Generate app map
            </button>
            {mapError && (
              <div style={{ marginTop: 10, fontSize: 11, color: P.fail,
                padding: '6px 10px', borderRadius: 6, background: P.failSoft }}>
                {mapError}
              </div>
            )}
          </div>
        )}

        {generatingMap && (
          <div style={{ fontSize: 13, color: P.textMute }}>Generating app map…</div>
        )}

        {appMap && (
          <div data-testid="app-map-content">
            {/* Header row */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16,
              padding: '8px 12px', borderRadius: 8, background: P.cardHi, border: `1px solid ${P.border}`,
              fontSize: 12 }}>
              <div>
                <span style={{ color: P.textMute }}>Type: </span>
                <code style={{ fontFamily: F.mono, fontSize: 10, color: P.textDim }}>
                  {appMap.map_type}
                </code>
              </div>
              <div>
                <span style={{ color: P.textMute }}>Confidence: </span>
                <span style={{
                  fontSize: 10, fontFamily: F.mono, borderRadius: 4, padding: '1px 6px',
                  marginLeft: 2,
                  color: appMap.confidence === 'high' ? P.pass : appMap.confidence === 'medium' ? P.unclear : P.textMute,
                  border: `1px solid ${(appMap.confidence === 'high' ? P.pass : appMap.confidence === 'medium' ? P.unclear : P.textMute) + '44'}`,
                }}>
                  {(appMap.confidence ?? 'unknown').toUpperCase()}
                </span>
              </div>
              {appMap.detected_stack.length > 0 && (
                <div>
                  <span style={{ color: P.textMute }}>Stack: </span>
                  <span style={{ color: P.text }}>{appMap.detected_stack.join(', ')}</span>
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Testable surfaces */}
              <div data-testid="app-map-surfaces">
                <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Testable surfaces ({appMap.testable_surfaces.length})
                </div>
                {appMap.testable_surfaces.length === 0 ? (
                  <div style={{ fontSize: 12, color: P.textFaint }}>None detected</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {appMap.testable_surfaces.map((s, i) => (
                      <div key={i} style={{ fontSize: 12, padding: '6px 10px', borderRadius: 6,
                        background: P.cardHi, border: `1px solid ${P.border}` }}>
                        <div style={{ fontWeight: 500, color: P.text }}>{s.name}</div>
                        {s.note && <div style={{ fontSize: 10, color: P.textFaint }}>{s.note}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Risk areas */}
              <div data-testid="app-map-risks">
                <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Risk areas ({appMap.risk_areas.length})
                </div>
                {appMap.risk_areas.length === 0 ? (
                  <div style={{ fontSize: 12, color: P.textFaint }}>None flagged</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {appMap.risk_areas.map((r, i) => (
                      <div key={i} style={{ fontSize: 12, padding: '6px 10px', borderRadius: 6,
                        background: r.risk_level === 'critical' || r.risk_level === 'high'
                          ? P.failSoft : P.unclearSoft,
                        border: `1px solid ${r.risk_level === 'critical' || r.risk_level === 'high'
                          ? P.fail + '33' : P.unclear + '33'}` }}>
                        <div style={{ fontWeight: 500, color: P.text }}>
                          {r.label}
                          <span style={{ fontSize: 10, marginLeft: 6, fontFamily: F.mono,
                            color: r.risk_level === 'critical' || r.risk_level === 'high' ? P.fail : P.unclear }}>
                            {r.risk_level.toUpperCase()}
                          </span>
                        </div>
                        {r.description && (
                          <div style={{ fontSize: 10, color: P.textFaint }}>{r.description}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Capability gaps */}
            {appMap.capability_gaps.length > 0 && (
              <div data-testid="app-map-gaps" style={{ marginTop: 16, padding: '10px 14px',
                borderRadius: 8, background: P.unclearSoft, border: `1px solid ${P.unclear}33` }}>
                <div style={{ fontSize: 11, color: P.unclear, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  Capability gaps ({appMap.capability_gaps.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {appMap.capability_gaps.map(g => (
                    <div key={g.id} style={{ fontSize: 12 }}>
                      <span style={{ fontWeight: 500, color: P.text }}>{g.title}</span>
                      {g.description && (
                        <span style={{ color: P.textDim }}> — {g.description}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <button
                data-testid="regenerate-app-map-btn"
                onClick={handleGenerateMap}
                disabled={generatingMap}
                style={{ fontSize: 11, color: P.textMute, background: 'none', border: 'none',
                  cursor: 'pointer', textDecoration: 'underline' }}>
                Regenerate app map
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Validation Packs for this app */}
      <Card style={{ marginTop: 20 }} data-testid="app-packs-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            VALIDATION PACKS
          </div>
          <Btn size="sm" variant="ghost"
            data-testid="create-pack-btn"
            onClick={() => nav(`/packs/new?app_id=${app.id}&project_id=${app.project_id}`)}>
            <Plus size={11} />New pack
          </Btn>
        </div>

        {packsLoading ? (
          <LoadingSkeleton rows={2} />
        ) : !Array.isArray(appPacks) || appPacks.length === 0 ? (
          <div data-testid="app-packs-empty">
            <PartialConfigBanner
              message="This app has no validation packs. Create one to start testing."
              action={
                <Btn size="sm" variant="primary" demoWrite
                  onClick={() => nav(`/packs/new?app_id=${app.id}&project_id=${app.project_id}`)}>
                  <Plus size={11} />Create Pack
                </Btn>
              }
            />
          </div>
        ) : (
          <div data-testid="app-packs-list" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {appPacks.map(pack => (
              <div key={pack.id} data-testid={`pack-card-${pack.id}`}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', borderRadius: 8, background: P.cardHi,
                  border: `1px solid ${P.border}` }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{pack.name}</div>
                  <ProvenanceBadge provenance={pack.provenance} source="App validation pack card" style={{ marginTop: 4 }} />
                  {pack.description && (
                    <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>{pack.description}</div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <Btn size="sm" variant="ghost" onClick={() => nav(`/packs/${pack.id}`)}>
                    Open
                  </Btn>
                  <Btn size="sm" variant="primary" demoWrite
                    disabled={isPreviewApp}
                    title={isPreviewApp ? PREVIEW_TOOLTIP : undefined}
                    onClick={() => nav(`/packs/${pack.id}`)}>
                    <Play size={11} />Review &amp; run
                  </Btn>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Source / Discovery info (shown only if discovered) */}
      {app.source_type && app.source_type !== 'manual' && (
        <Card style={{ marginTop: 20 }}>
          <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            SOURCE &amp; DETECTION
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
            <div>
              <span style={{ color: P.textMute }}>Source type: </span>
              <span style={{ color: P.text, textTransform: 'capitalize' }}>
                {app.source_type.replace(/_/g, ' ')}
              </span>
            </div>
            {app.source_path && (
              <div>
                <span style={{ color: P.textMute }}>Local path: </span>
                <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>
                  {app.source_path}
                </code>
              </div>
            )}
            {app.source_url && (
              <div>
                <span style={{ color: P.textMute }}>Source URL: </span>
                <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim }}>
                  {app.source_url}
                </code>
              </div>
            )}
            {app.launch_command && (
              <div>
                <span style={{ color: P.textMute }}>Launch command: </span>
                <code style={{ fontFamily: F.mono, fontSize: 11, color: P.textDim, background: P.cardHi,
                  padding: '2px 6px', borderRadius: 4, border: `1px solid ${P.border}` }}>
                  {app.launch_command}
                </code>
              </div>
            )}
            {app.detected_stack && (
              <div>
                <span style={{ color: P.textMute }}>Detected stack: </span>
                <span style={{ color: P.text }}>
                  {app.detected_stack.split(',').filter(Boolean).join(', ')}
                </span>
              </div>
            )}
            {app.discovery_id && (
              <div>
                <span style={{ color: P.textMute }}>Discovery ID: </span>
                <code style={{ fontFamily: F.mono, fontSize: 10, color: P.textFaint }}>
                  {app.discovery_id}
                </code>
              </div>
            )}
          </div>
        </Card>
      )}
    </AppShell>
  );
}
