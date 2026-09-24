import { useCallback } from 'react';
import { RefreshCw, Plus, AlertTriangle } from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { LoadingSkeleton, ErrorState, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get } from '../api/client';
import type { ConnectorsResponse } from '../types/api';
import type { AppTarget, Provenance } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { PreviewBadge } from '../components/PreviewBadge';
import { isPreviewAppType } from '../config/capabilities';

// ── Backend types ─────────────────────────────────────────────────────────────

interface BackendSubCheck {
  id: string;
  name: string;
  ready: boolean;
  check_type: string;
  details: string;
  provenance?: Provenance;
}

interface BackendConnector {
  connector_id: string;
  connector_type: string;
  ready: boolean;
  partial?: boolean;
  check_type: string;
  details: string;
  sub_checks?: BackendSubCheck[];
  provenance?: Provenance;
}

interface BackendConnectorsResponse {
  checked_at: string;
  connectors: BackendConnector[];
  total: number;
  ready: number;
  partial?: number;
  provenance?: Provenance;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function connectorStatus(c: BackendConnector): 'ready' | 'partial' | 'missing' {
  if (c.ready) return 'ready';
  if (c.partial) return 'partial';
  return 'missing';
}

function statusDot(s: 'ready' | 'partial' | 'missing') {
  if (s === 'ready')   return P.pass;
  if (s === 'partial') return P.unclear;
  return P.fail;
}

// ── Sub-component: single dependency row ─────────────────────────────────────

function DepRow({ c, inheritedProvenance }: { c: BackendConnector; inheritedProvenance?: Provenance }) {
  const st = connectorStatus(c);
  const dot = statusDot(st);
  const provenance = c.provenance ?? inheritedProvenance;
  const preview = c.connector_id.toLowerCase().includes('appium') || c.connector_type.toLowerCase().includes('mobile');

  return (
    <div>
      {/* Main row */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px',
      }}>
        <div style={{ width: 8, height: 8, borderRadius: 99, flexShrink: 0, background: dot }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: P.text }}>
              {c.connector_id.charAt(0).toUpperCase() + c.connector_id.slice(1)}
            </span>
            <span style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>
              {c.connector_type}
            </span>
            {c.check_type === 'composite' && (
              <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono,
                padding: '1px 5px', borderRadius: 4, border: `1px solid ${P.border}` }}>
                composite
              </span>
            )}
            {preview && <PreviewBadge />}
          </div>
          <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>{c.details}</div>
        </div>
        <StatusBadge
          kind={st === 'partial' ? 'partial' : st === 'ready' ? 'ready' : 'missing'}
          small
        />
        <ProvenanceBadge provenance={provenance} source="Connector status" />
      </div>

      {/* Sub-checks for composite connectors (e.g. Appium) */}
      {c.sub_checks && c.sub_checks.length > 0 && (
        <div style={{
          marginLeft: 38, borderLeft: `2px solid ${P.border}`,
          marginBottom: 4,
        }}>
          {c.sub_checks.map((sub, i) => (
            <div key={sub.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '7px 16px',
              borderBottom: i < c.sub_checks!.length - 1 ? `1px solid ${P.border}22` : 'none',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: 99, flexShrink: 0,
                background: sub.ready ? P.pass : P.fail,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 12, color: P.textDim }}>{sub.name}</span>
                <span style={{ fontSize: 11, color: P.textFaint, marginLeft: 8 }}>{sub.details}</span>
              </div>
              <span style={{
                fontSize: 10, fontFamily: F.mono, padding: '1px 6px', borderRadius: 4,
                background: sub.ready ? `${P.pass}22` : `${P.fail}22`,
                color: sub.ready ? P.pass : P.fail,
                border: `1px solid ${sub.ready ? P.pass : P.fail}44`,
              }}>
                {sub.ready ? 'OK' : 'MISSING'}
              </span>
              <ProvenanceBadge provenance={sub.provenance ?? provenance} source="Connector sub-check" />
            </div>
          ))}

          {/* Partial warning banner */}
          {!c.ready && c.partial && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              margin: '6px 16px 8px', padding: '8px 12px', borderRadius: 7,
              background: `${P.unclear}18`, border: `1px solid ${P.unclear}44`,
            }}>
              <AlertTriangle size={13} color={P.unclear} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ fontSize: 11, color: P.unclear }}>
                Client installed but mobile testing is not ready.
                Start the Appium server: <code style={{ fontFamily: F.mono }}>appium server</code>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Fetchers ──────────────────────────────────────────────────────────────────

function getConnectors() {
  return get<BackendConnectorsResponse>('/connectors');
}

function getApps() {
  return get<AppTarget[]>('/apps');
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ConnectorsPage() {
  const nav = useWorkspaceNavigate();

  const fetchConnectors = useCallback(getConnectors, []);
  const fetchApps = useCallback(getApps, []);

  const {
    data: rawConnectors, loading: connLoading, error: connError,
    refetch: refetchConn, isMock, isOffline,
  } = useApi(fetchConnectors, {
    demo: workspace => workspace.connectors as unknown as BackendConnectorsResponse,
  });

  const {
    data: apps, loading: appsLoading,
  } = useApi(fetchApps, { demo: workspace => workspace.apps });

  // Demo uses the display connector shape; backend responses use the runtime shape.
  const connectors: BackendConnector[] = isMock
    ? ((rawConnectors as unknown as ConnectorsResponse | null)?.connectors ?? []).map(c => ({
        connector_id: c.id,
        connector_type: c.connector_type,
        ready: c.status === 'ready',
        partial: c.status === 'partial',
        check_type: 'client_library',
        details: c.detail ?? '',
        provenance: c.provenance,
      }))
    : rawConnectors?.connectors ?? [];

  const readyCount  = connectors.filter(c => c.ready).length;
  const partialCount = connectors.filter(c => !c.ready && c.partial).length;
  const hasApps = (apps ?? []).length > 0;

  // Summary subtitle: only mention "ready" if we actually have data
  let subtitle = 'Checking dependencies…';
  if (!connLoading && connectors.length > 0) {
    const parts: string[] = [`${readyCount} / ${connectors.length} ready`];
    if (partialCount > 0) parts.push(`${partialCount} partial`);
    subtitle = parts.join(' · ') + ' — global runtime checks';
  } else if (!connLoading && connectors.length === 0 && !connError) {
    subtitle = 'No dependency data returned';
  }

  return (
    <AppShell section="08" title="Connectors">
      <PageHeader
        title="Connectors"
        subtitle={subtitle}
        provenance={rawConnectors?.provenance}
        provenanceSource={rawConnectors && !isOffline ? 'Connectors detail' : undefined}
        actions={
          <Btn size="sm" variant="ghost" onClick={refetchConn}>
            <RefreshCw size={12} />Re-check
          </Btn>
        }
      />

      {isOffline ? (
        <OfflineState onRetry={refetchConn} />
      ) : connError && !rawConnectors && !isMock ? (
        <ErrorState message={connError} onRetry={refetchConn} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* ── SECTION 1: App Runtime Connectors ──────────────────────────── */}
          <section aria-label="App runtime connectors">
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
              APP RUNTIME CONNECTORS
            </div>

            {appsLoading ? (
              <Card><LoadingSkeleton rows={2} /></Card>
            ) : !hasApps ? (
              // ── No app connected yet ────────────────────────────────────
              <div data-testid="no-app-state">
                <Card>
                  <div style={{ padding: '12px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: P.text }}>
                      No app connected yet
                    </div>
                    <div style={{ fontSize: 12, color: P.textMute, maxWidth: 440 }}>
                      Connect an app to see per-app runtime connector status — which browser, mobile driver, or backend the test run uses.
                    </div>
                    <div data-testid="connect-app-cta">
                      <Btn
                        variant="primary"
                        size="sm"
                        onClick={() => nav('/projects/new')}
                      >
                        <Plus size={12} />Connect app
                      </Btn>
                    </div>
                  </div>
                </Card>
              </div>
            ) : (
              // ── App exists but no per-app connector endpoint yet ────────
              <Card>
                <div style={{ padding: '10px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 13, color: P.textDim }}>
                    {(apps ?? []).length} app{(apps ?? []).length !== 1 ? 's' : ''} connected.
                    Per-app connector diagnostics are shown when a live run is active.
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(apps ?? []).map(a => (
                      <span key={a.id} style={{
                        padding: '3px 9px', borderRadius: 6, fontSize: 12,
                        background: P.cardHi, border: `1px solid ${P.border}`, color: P.textDim,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                      }}>
                        {a.name}
                        {isPreviewAppType(a.app_type) && <PreviewBadge />}
                        <ProvenanceBadge provenance={a.provenance} source="Connector app" />
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            )}
          </section>

          {/* ── SECTION 2: Global Runtime Dependencies ─────────────────────── */}
          <section aria-label="Global runtime dependencies">
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono,
              textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
              GLOBAL RUNTIME DEPENDENCIES
            </div>

            <div style={{ fontSize: 11, color: P.textFaint, marginBottom: 12 }}>
              These checks run on the local machine — not against a specific app.
              Server reachability checks do not make cloud calls.
            </div>

            {connLoading ? (
              <Card><LoadingSkeleton rows={4} /></Card>
            ) : connectors.length === 0 ? (
              <Card>
                <div style={{ padding: '16px 0', fontSize: 12, color: P.textMute, textAlign: 'center' }}>
                  No dependency data available.
                </div>
              </Card>
            ) : (
              <div data-testid="global-deps-list">
                <Card pad={0}>
                  {connectors.map((c, i) => (
                    <div key={c.connector_id} style={{
                      borderBottom: i < connectors.length - 1 ? `1px solid ${P.border}` : 'none',
                    }}>
                      <DepRow c={c} inheritedProvenance={rawConnectors?.provenance} />
                    </div>
                  ))}
                </Card>
              </div>
            )}
          </section>

        </div>
      )}
    </AppShell>
  );
}
