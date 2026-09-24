import { useState, useCallback } from 'react';
import { RefreshCw, Cpu } from 'lucide-react';
import { P, F } from '../design/tokens';
import type { StatusKind } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { StatusBadge } from '../components/status/StatusBadge';
import { LoadingSkeleton, ErrorState, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, post } from '../api/client';
import type { ModelProvider, ModelProfile, HardwareProfile } from '../types/api';

// ── Backend shapes ────────────────────────────────────────────────────────────

interface BackendProvider {
  provider_id: string;
  name: string;
  enabled: boolean;
  provider_type?: string;
  local_only?: boolean;
  api_key_configured?: boolean;
}

interface BackendHardware {
  platform?: string;
  total_ram_gb?: number;
  gpu_label?: string;
  recommended_profile?: string;
  architecture?: string;
  apple_silicon?: boolean;
  error?: string;
}

interface BackendProfileRoute {
  model?: string;
  provider_id?: string;
  latency_estimate_ms?: number;
}

interface BackendProfile {
  profile_id?: string;
  name?: string;
  description?: string;
  task_routes?: Record<string, BackendProfileRoute>;
  error?: string;
}

// ── Adapters ──────────────────────────────────────────────────────────────────

function adaptProviders(raw: BackendProvider[]): ModelProvider[] {
  return (raw ?? []).map(p => ({
    id: p.provider_id,
    name: p.name,
    status: (p.enabled ? 'ready' : 'missing') as ModelProvider['status'],
    models: undefined,
  }));
}

function adaptHardware(raw: BackendHardware): HardwareProfile {
  return {
    platform: raw.platform ?? '—',
    cpu_cores: 0, // not available from backend hardware endpoint
    ram_gb: raw.total_ram_gb ?? 0,
    gpu: raw.gpu_label ?? undefined,
    recommended_profile: raw.recommended_profile,
  };
}

function adaptProfile(raw: BackendProfile): ModelProfile {
  const routes = Object.entries(raw.task_routes ?? {}).map(([task, r]) => ({
    task,
    model_id: r.model ?? '—',
    provider: r.provider_id ?? '—',
    latency_p50_ms: r.latency_estimate_ms ?? undefined,
  }));
  return {
    id: raw.profile_id ?? 'default',
    name: raw.name ?? raw.profile_id ?? 'Auto-detected profile',
    description: raw.description,
    routes,
  };
}

function getRawProviders() { return get<BackendProvider[]>('/models/providers'); }
function getRawHardware() { return get<BackendHardware>('/models/hardware'); }
function getRawProfile() { return get<BackendProfile>('/models/profile/current'); }

export default function ModelSettingsPage() {
  const providersFn = useCallback(getRawProviders, []);
  const hardwareFn  = useCallback(getRawHardware, []);
  const profileFn   = useCallback(getRawProfile, []);

  const { data: providersRaw, loading: pLoading, isOffline, isMock, refetch: refetchProviders } =
    useApi(providersFn, { demo: workspace => workspace.providers as unknown as BackendProvider[] });
  const { data: hardwareRaw } =
    useApi(hardwareFn, { demo: workspace => workspace.hardware as unknown as BackendHardware });
  const { data: profileRaw, loading: prLoading } =
    useApi(profileFn, { demo: workspace => workspace.profile as unknown as BackendProfile });

  const providers: ModelProvider[] = isMock
    ? (providersRaw as unknown as ModelProvider[] | null) ?? []
    : adaptProviders(providersRaw ?? []);
  const hardware: HardwareProfile | null = isMock
    ? hardwareRaw as unknown as HardwareProfile
    : hardwareRaw
    ? adaptHardware(hardwareRaw)
    : null;
  const profile: ModelProfile | null = isMock
    ? profileRaw as unknown as ModelProfile
    : profileRaw
    ? adaptProfile(profileRaw)
    : null;

  const [discovering, setDiscovering] = useState(false);

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      await post('/models/providers/discover', {});
      await refetchProviders();
    } catch { /* offline — ignore */ }
    finally { setDiscovering(false); }
  };

  return (
    <AppShell section="09" title="Model Settings">
      <PageHeader
        title="Model Settings"
        subtitle="Local-first. Cloud disabled. No API keys stored."
        actions={
          <Btn variant="primary" onClick={handleDiscover} disabled={discovering}>
            <RefreshCw size={12} style={{ animation: discovering ? 'spin 1s linear infinite' : undefined }} />
            {discovering ? 'Discovering…' : 'Discover providers'}
          </Btn>
        }
      />

      {isOffline ? (
        <OfflineState onRetry={refetchProviders} />
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Hardware profile */}
            <Card>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>HARDWARE</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: 9, background: P.accentSoft,
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Cpu size={18} color={P.accent} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: P.text }}>
                    {hardware?.platform ?? '—'}
                  </div>
                  <div style={{ fontSize: 11, color: P.textMute }}>
                    {hardware?.ram_gb ? `${hardware.ram_gb} GB RAM` : '—'}
                  </div>
                </div>
              </div>
              {hardware?.gpu && (
                <div style={{ padding: '8px 10px', borderRadius: 6, background: P.cardHi,
                  fontSize: 12, color: P.textDim }}>
                  GPU: {hardware.gpu}
                </div>
              )}
              {hardware?.recommended_profile && (
                <div style={{ marginTop: 10, fontSize: 12, color: P.textMute }}>
                  Recommended profile:{' '}
                  <span style={{ color: P.accent }}>{hardware.recommended_profile}</span>
                </div>
              )}
            </Card>

            {/* Active profile */}
            <Card>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>ACTIVE PROFILE</div>
              {prLoading ? (
                <div style={{ fontSize: 12, color: P.textMute }}>Loading…</div>
              ) : profile ? (
                <>
                  <div style={{ fontSize: 15, fontWeight: 600, color: P.text, marginBottom: 4 }}>
                    {profile.name}
                  </div>
                  {profile.routes.length === 0 ? (
                    <div style={{ fontSize: 12, color: P.textMute }}>No routes configured.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                      {profile.routes.map(r => (
                        <div key={r.task} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 12, color: P.textMute, textTransform: 'capitalize' }}>
                            {r.task}
                          </span>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{ fontSize: 11, fontFamily: F.mono, color: P.text }}>{r.model_id}</span>
                            {r.latency_p50_ms && (
                              <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>
                                ~{r.latency_p50_ms}ms
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div style={{ fontSize: 12, color: P.textMute }}>Profile data unavailable.</div>
              )}
            </Card>
          </div>

          {/* Providers */}
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginBottom: 12 }}>Providers</div>
            {pLoading ? (
              <LoadingSkeleton rows={3} />
            ) : providers.length === 0 ? (
              <div style={{ fontSize: 13, color: P.textMute, padding: '12px 0' }}>
                No providers configured. Click &quot;Discover providers&quot; to scan for local models.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {providers.map(prov => (
                  <Card key={prov.id} pad={0}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
                      borderBottom: prov.models?.length ? `1px solid ${P.border}` : 'none',
                    }}>
                      <div style={{
                        width: 8, height: 8, borderRadius: 99, flexShrink: 0,
                        background: prov.status === 'ready' ? P.pass : prov.status === 'partial' ? P.unclear : P.fail,
                      }} />
                      <span style={{ fontSize: 13, fontWeight: 500, color: P.text, flex: 1 }}>{prov.name}</span>
                      <StatusBadge kind={prov.status as StatusKind} small />
                    </div>
                    {prov.models && prov.models.length > 0 && (
                      <div>
                        {prov.models.map((m, i) => (
                          <div key={m.id} style={{
                            display: 'flex', alignItems: 'center', gap: 12,
                            padding: '9px 16px 9px 30px',
                            borderBottom: i < (prov.models?.length ?? 0) - 1 ? `1px solid ${P.border}` : 'none',
                          }}>
                            <span style={{ fontSize: 12, color: P.textDim, flex: 1 }}>{m.name}</span>
                            {m.size_gb && (
                              <span style={{ fontSize: 11, color: P.textFaint, fontFamily: F.mono }}>
                                {m.size_gb} GB
                              </span>
                            )}
                            <StatusBadge kind={m.status as StatusKind} small />
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Cloud disabled notice */}
          <div style={{ marginTop: 16, padding: '12px 16px', borderRadius: 8,
            background: P.passSoft, border: `1px solid ${P.pass}33`, fontSize: 12, color: P.textDim }}>
            ✓ Cloud providers disabled · No API keys stored · All inference runs locally
          </div>
        </>
      )}
    </AppShell>
  );
}
