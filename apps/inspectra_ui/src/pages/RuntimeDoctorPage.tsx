import { useCallback } from 'react';
import { RefreshCw, Download } from 'lucide-react';
import { P, F } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { PreviewBadge } from '../components/PreviewBadge';
import { LoadingSkeleton, ErrorState, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get } from '../api/client';
import type { RuntimeDoctorReport, DoctorComponent, DoctorFix, Provenance } from '../types/api';
import type { ReadinessState } from '../types/api';

// ── Backend response shape (EnvironmentDoctorReport) ──────────────────────────
// The backend returns this; we adapt it to RuntimeDoctorReport for the UI.

interface BackendDriverReadiness {
  app_type: string;
  driver_type: string;
  status: string; // 'ready' | 'not_available' | 'missing_deps' | 'permission_denied'
  missing_deps: string[];
}

interface BackendDoctorReport {
  provenance?: Provenance;
  readiness_score: number;
  readiness_label: string; // 'blocked' | 'partial' | 'usable' | 'ready'
  missing_items: string[];
  recommended_actions: string[];
  driver_readiness: BackendDriverReadiness[];
  playwright_installed: boolean;
  playwright_browsers_installed: boolean;
  appium_client_installed: boolean;
  appium_command_available: boolean;
  appium_server_reachable: boolean;
  ollama_reachable: boolean;
  ollama_vision_model_available: boolean;
  macos_accessibility_granted: boolean;
  pywinauto_installed: boolean;
  atspi_installed: boolean;
  npm_available: boolean;
  platform: string;
  needs_mobile?: boolean; // True when mobile app_types were requested
}

// ── Adapter: BackendDoctorReport → RuntimeDoctorReport ────────────────────────

function adaptDoctorReport(raw: BackendDoctorReport): RuntimeDoctorReport {
  const labelToBand: Record<string, ReadinessState> = {
    blocked: 'missing',
    partial: 'partial',
    usable: 'usable',
    ready: 'ready',
  };
  const readiness_band: ReadinessState = labelToBand[raw.readiness_label] ?? 'partial';

  // Appium is only relevant when mobile testing is needed
  const appiumSkipped = !raw.needs_mobile;
  const APPIUM_SKIP_DETAIL = 'Only needed for Android/iOS testing';

  // Build component list from boolean flags
  const flagComponents: DoctorComponent[] = [
    { name: 'Playwright', status: raw.playwright_installed ? 'ready' : 'missing', provenance: raw.provenance },
    { name: 'PW Browsers', status: raw.playwright_browsers_installed ? 'ready' : 'missing', provenance: raw.provenance },
    {
      name: 'Appium Client',
      status: appiumSkipped ? 'skipped' : (raw.appium_client_installed ? 'ready' : 'missing'),
      detail: appiumSkipped ? APPIUM_SKIP_DETAIL : undefined,
      provenance: raw.provenance,
    },
    {
      name: 'Appium CLI',
      status: appiumSkipped ? 'skipped' : (raw.appium_command_available ? 'ready' : 'missing'),
      detail: appiumSkipped ? APPIUM_SKIP_DETAIL : undefined,
      provenance: raw.provenance,
    },
    {
      name: 'Appium Server',
      status: appiumSkipped ? 'skipped' : (raw.appium_server_reachable ? 'ready' : 'missing'),
      detail: appiumSkipped ? APPIUM_SKIP_DETAIL : undefined,
      provenance: raw.provenance,
    },
    { name: 'Ollama', status: raw.ollama_reachable ? 'ready' : 'missing', provenance: raw.provenance },
    { name: 'Vision Model', status: raw.ollama_vision_model_available ? 'ready' : 'missing', provenance: raw.provenance },
  ];

  // Add macOS accessibility if on macOS
  if (raw.macos_accessibility_granted !== undefined) {
    flagComponents.push({
      name: 'macOS Accessibility',
      status: raw.macos_accessibility_granted ? 'ready' : 'perm',
      detail: raw.macos_accessibility_granted
        ? undefined
        : 'System Settings → Privacy & Security → Accessibility',
      provenance: raw.provenance,
    });
  }

  // Add per-driver readiness rows — exclude not_available (wrong platform/N/A)
  const driverComponents: DoctorComponent[] = (raw.driver_readiness ?? [])
    .filter(dr => dr.status !== 'not_available')
    .map(dr => ({
      name: `${dr.app_type} · ${dr.driver_type}`,
      status: (dr.status === 'ready'
        ? 'ready'
        : dr.status === 'permission_denied'
        ? 'perm'
        : 'missing') as ReadinessState,
      detail: dr.missing_deps.length > 0 ? dr.missing_deps.join(', ') : undefined,
      provenance: raw.provenance,
    }));

  const components = [...flagComponents, ...driverComponents];

  // Build things_to_fix from ALL non-ready components, not just missing_items strings.
  // missing_items may be empty even when components show missing/perm — use components as source of truth.
  const nonReadyComponents = components.filter(c => c.status !== 'ready' && c.status !== 'skipped');
  const things_to_fix: DoctorFix[] = nonReadyComponents.map((comp, i) => {
    // Try to enrich with a recommended_action for this component
    const action = (raw.recommended_actions ?? [])[i] ?? undefined;
    return {
      id: `fix-${i}`,
      title: comp.name,
      status: comp.status as 'missing' | 'perm',
      description: comp.detail ?? action,
      provenance: comp.provenance ?? raw.provenance,
    };
  });

  const ready   = components.filter(c => c.status === 'ready').length;
  const missing = components.filter(c => c.status === 'missing').length;
  const perm    = components.filter(c => c.status === 'perm').length;
  const skipped = components.filter(c => c.status === 'skipped').length;

  return {
    readiness_score: raw.readiness_score ?? 0,
    readiness_band,
    components,
    things_to_fix,
    summary: { ready, missing, perm, skipped },
    needs_mobile: raw.needs_mobile ?? false,
    provenance: raw.provenance,
  };
}

function getRawDoctor() {
  return get<BackendDoctorReport>('/runtime-doctor');
}

export default function RuntimeDoctorPage() {
  const fetchFn = useCallback(getRawDoctor, []);
  const { data: raw, loading, error, refetch, isMock, isOffline } = useApi(
    fetchFn,
    { demo: workspace => workspace.runtimeDoctor as unknown as BackendDoctorReport },
  );

  // Demo data already uses the display shape; real responses need adapting.
  const data: RuntimeDoctorReport | null = isMock
    ? raw as unknown as RuntimeDoctorReport
    : raw
    ? adaptDoctorReport(raw)
    : null;

  const bandColors: Record<string, { c: string }> = {
    ready:   { c: P.pass },
    usable:  { c: P.pass },
    partial: { c: P.unclear },
    missing: { c: P.fail },
  };
  const band = bandColors[data?.readiness_band ?? 'partial'] ?? bandColors.partial;

  return (
    <AppShell
      section="02 · ONBOARDING"
      title="Runtime Doctor"
      readinessScore={data?.readiness_score}
      readinessSubtitle={data !== null && !data?.needs_mobile ? 'App: —' : undefined}
    >

      <PageHeader
        title="Runtime Doctor"
        subtitle="Checks Inspectra has everything it needs to test your apps."
        provenance={data?.provenance}
        provenanceSource={data && !isOffline ? 'Runtime Doctor detail' : undefined}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="ghost" size="sm" disabled title="Not available yet">
              <Download size={12} />Export report
            </Btn>
            <Btn variant="primary" onClick={refetch} disabled={loading}>
              <RefreshCw
                size={12}
                style={{ animation: loading ? 'spin 1s linear infinite' : undefined }}
              />
              {loading ? 'Checking…' : 'Re-check'}
            </Btn>
          </div>
        }
      />

      {loading ? (
        <LoadingSkeleton />
      ) : isOffline ? (
        <OfflineState onRetry={refetch} />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : (
        <div style={{ display: 'flex', gap: 16 }}>
          {/* Left: Score + Components */}
          <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Score card */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  ENVIRONMENT READINESS
                </div>
                <ProvenanceBadge provenance={data?.provenance} source="Runtime Doctor score" />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 64, fontWeight: 800, color: P.text, lineHeight: 1,
                  fontVariantNumeric: 'tabular-nums' }}>
                  {data?.readiness_score ?? 0}
                </span>
                <span style={{ fontSize: 16, color: P.textMute }}>/ 100</span>
              </div>
              <StatusBadge kind={(data?.readiness_band ?? 'partial') as StatusKind} />

              <div style={{ marginTop: 12, fontSize: 12, color: P.textDim }}>
                {(data?.summary.missing ?? 0) + (data?.summary.perm ?? 0)} things blocking environment readiness.
              </div>

              {/* Band bar */}
              <div style={{ marginTop: 12, display: 'flex', gap: 2, height: 6, borderRadius: 99, overflow: 'hidden' }}>
                <div style={{ flex: 25, background: P.fail, opacity: 0.7 }} />
                <div style={{ flex: 40, background: P.unclear, opacity: 0.7 }} />
                <div style={{ flex: 35, background: P.pass, opacity: 0.9 }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                <span style={{ fontSize: 9, color: P.textFaint, fontFamily: F.mono }}>0-25 Blocked</span>
                <span style={{ fontSize: 9, color: P.textFaint, fontFamily: F.mono }}>26-60 Partial</span>
                <span style={{ fontSize: 9, color: band.c, fontFamily: F.mono, fontWeight: 600 }}>61-85 Usable</span>
                <span style={{ fontSize: 9, color: P.textFaint, fontFamily: F.mono }}>86 ready</span>
              </div>
            </Card>

            {/* Component status */}
            <Card pad={0}>
              <div style={{ padding: '12px 14px', borderBottom: `1px solid ${P.border}` }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em' }}>COMPONENT STATUS</div>
              </div>
              {(data?.components ?? []).map((comp, i) => {
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 14px',
                    borderBottom: i < (data?.components.length ?? 0) - 1 ? `1px solid ${P.border}` : 'none',
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: 12, color: P.textDim }}>
                        {comp.name}
                        {comp.version && ` ${comp.version}`}
                      </span>
                      {comp.name.toLowerCase().includes('appium') && <PreviewBadge style={{ marginLeft: 6 }} />}
                      {comp.detail && comp.status === 'skipped' && (
                        <div style={{ fontSize: 10, color: P.textFaint, marginTop: 1 }}>{comp.detail}</div>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <StatusBadge kind={comp.status as StatusKind} small />
                      <ProvenanceBadge provenance={comp.provenance ?? data?.provenance} source="Runtime Doctor component" />
                    </div>
                  </div>
                );
              })}
              {(data?.components ?? []).length === 0 && (
                <div style={{ padding: '12px 14px', fontSize: 12, color: P.textMute }}>
                  No component data yet.
                </div>
              )}
            </Card>

            {/* Summary */}
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                  textTransform: 'uppercase', letterSpacing: '0.06em' }}>SUMMARY</div>
                <ProvenanceBadge provenance={data?.provenance} source="Runtime Doctor summary" />
              </div>
              <div style={{ display: 'flex', gap: 20 }}>
                {Object.entries(data?.summary ?? { ready: 0, missing: 0, perm: 0, skipped: 0 }).map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: 22, fontWeight: 700,
                      color: k === 'ready' ? P.pass : k === 'missing' ? P.fail : k === 'perm' ? P.accent : P.textMute }}>
                      {v}
                    </div>
                    <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                      textTransform: 'uppercase' }}>{k}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Right: Environment Readiness + App Runtime Readiness */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>

            {/* ── Environment Readiness ── */}
            <div style={{ fontSize: 16, fontWeight: 600, color: P.text }}>Environment Readiness</div>

            {(data?.things_to_fix ?? []).map(fix => (
              <Card key={fix.id}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                    background: fix.status === 'missing' ? P.unclearSoft : fix.status === 'perm' ? P.accentSoft : P.passSoft,
                    border: `1px solid ${fix.status === 'missing' ? P.unclear + '33' : fix.status === 'perm' ? P.accent + '33' : P.pass + '33'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18,
                  }}>
                    {fix.status === 'perm' ? '🔒' : '!'}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, color: P.text }}>{fix.title}</span>
                      <StatusBadge kind={fix.status as StatusKind} small />
                      <ProvenanceBadge provenance={fix.provenance ?? data?.provenance} source="Runtime Doctor recommendation" />
                    </div>
                    {fix.description && (
                      <div style={{ fontSize: 12, color: P.textDim, marginBottom: 10 }}>{fix.description}</div>
                    )}
                    {fix.commands && fix.commands.length > 0 && (
                      <div style={{ background: P.bg, border: `1px solid ${P.border}`,
                        borderRadius: 6, padding: '8px 12px', marginBottom: 10 }}>
                        {fix.commands.map((cmd, i) => (
                          <div key={i} style={{ fontFamily: F.mono, fontSize: 12, color: P.text,
                            marginBottom: i < fix.commands!.length - 1 ? 4 : 0 }}>
                            <span style={{ color: P.accent }}>$ </span>{cmd}
                          </div>
                        ))}
                      </div>
                    )}
                    {fix.status === 'perm' && (
                      <div style={{ fontSize: 12, color: P.textDim, marginBottom: 10 }}>
                        System Settings → Privacy &amp; Security → Accessibility → enable &quot;Inspectra&quot;
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 8 }}>
                      {fix.action_label && (
                        <Btn size="sm" variant="primary">
                          {fix.action_label}
                        </Btn>
                      )}
                      <Btn size="sm" variant="ghost">Skip for now</Btn>
                    </div>
                  </div>
                </div>
              </Card>
            ))}

            {(data?.things_to_fix ?? []).length === 0 && (
              <Card>
                <div style={{ textAlign: 'center', padding: '20px 0' }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>✓</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, color: P.pass }}>All systems ready</div>
                    <ProvenanceBadge provenance={data?.provenance} source="Runtime Doctor recommendation" />
                  </div>
                  <div style={{ fontSize: 12, color: P.textMute, marginTop: 4 }}>No issues to fix</div>
                </div>
              </Card>
            )}

            {/* ── App Runtime Readiness ── */}
            <div style={{ fontSize: 16, fontWeight: 600, color: P.text, marginTop: 8 }}>
              App Runtime Readiness
            </div>

            {!data?.needs_mobile ? (
              <Card>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                    background: P.cardHi, border: `1px solid ${P.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18,
                  }}>
                    ℹ
                  </div>
                  <div data-testid="no-app-connected-doctor" style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: P.textDim }}>Not checked</div>
                      <ProvenanceBadge provenance={data?.provenance} source="Runtime Doctor app readiness" />
                    </div>
                    <div style={{ fontSize: 12, color: P.textMute }}>
                      No app connected yet. Connect an app to run app-specific runtime checks —
                      Android/iOS drivers, mobile Appium setup, and per-app validation targets.
                    </div>
                  </div>
                </div>
              </Card>
            ) : (
              <Card>
                <div style={{ textAlign: 'center', padding: '16px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, color: P.textDim }}>
                      App driver checks included above
                    </div>
                    <ProvenanceBadge provenance={data?.provenance} source="Runtime Doctor app readiness" />
                  </div>
                  <div style={{ fontSize: 12, color: P.textMute, marginTop: 4 }}>
                    Driver requirements are shown in the Environment Readiness fixes.
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}
