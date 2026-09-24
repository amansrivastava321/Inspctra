import { useState, useCallback } from 'react';
import { P, F } from '../design/tokens';
import { AppShell, PageHeader, Card, Btn } from '../components/layout/AppShell';
import { LoadingSkeleton, OfflineState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get, patch } from '../api/client';
import type { ProductSetting } from '../types/api';

const getSettings = () => get<ProductSetting[]>('/settings');

// Grouped by real backend allowlist keys only
const SETTING_GROUPS = [
  {
    id: 'general',
    label: 'General',
    keys: ['dashboard_title', 'artifacts_dir', 'theme'],
  },
  {
    id: 'runtime',
    label: 'Runtime',
    keys: ['default_timeout_seconds', 'run_concurrency_limit', 'log_level'],
  },
  {
    id: 'features',
    label: 'Features',
    keys: ['enable_runtime_doctor', 'auto_index_artifacts'],
  },
];

export default function SettingsPage() {
  const settingsFn = useCallback(getSettings, []);
  const { data, loading, isOffline, refetch } = useApi(settingsFn, { demo: workspace => workspace.settings });
  const [saving, setSaving] = useState<string | null>(null);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [activeGroup, setActiveGroup] = useState(SETTING_GROUPS[0].id);

  const allSettings = data ?? [];
  const getValue = (key: string) => local[key] ?? allSettings.find(s => s.key === key)?.value ?? '';

  const handleSave = async (key: string) => {
    setSaving(key);
    try {
      await patch(`/settings/${key}`, { value: local[key] ?? getValue(key) });
    } catch { /* offline — surface if needed */ }
    finally { setSaving(null); }
  };

  const currentGroup = SETTING_GROUPS.find(g => g.id === activeGroup)!;
  const groupSettings = allSettings.filter(s =>
    currentGroup.keys.includes(s.key) || s.category === activeGroup
  );

  return (
    <AppShell section="11" title="Settings">
      <PageHeader title="Settings" subtitle="Workspace configuration" />

      {isOffline ? (
        <OfflineState onRetry={refetch} />
      ) : (
        <div style={{ display: 'flex', gap: 20 }}>
          {/* Left nav */}
          <div style={{ width: 200, flexShrink: 0 }}>
            <Card pad={0}>
              {SETTING_GROUPS.map((g, i) => (
                <button key={g.id} onClick={() => setActiveGroup(g.id)} style={{
                  width: '100%', padding: '10px 14px', textAlign: 'left',
                  background: activeGroup === g.id ? P.accentSoft : 'transparent',
                  borderLeft: `2px solid ${activeGroup === g.id ? P.accent : 'transparent'}`,
                  color: activeGroup === g.id ? P.accent : P.textDim,
                  fontSize: 13, cursor: 'pointer', border: 'none',
                  borderBottom: i < SETTING_GROUPS.length - 1 ? `1px solid ${P.border}` : 'none',
                }}>
                  {g.label}
                </button>
              ))}
            </Card>
          </div>

          {/* Settings detail */}
          <div style={{ flex: 1 }}>
            {loading ? <LoadingSkeleton /> : (
              <Card>
                <div style={{ fontSize: 15, fontWeight: 600, color: P.text, marginBottom: 16 }}>
                  {currentGroup.label}
                </div>
                {groupSettings.map((s, i) => (
                  <div key={s.key} style={{
                    display: 'flex', alignItems: 'center', gap: 16, paddingBottom: 14,
                    marginBottom: i < groupSettings.length - 1 ? 14 : 0,
                    borderBottom: i < groupSettings.length - 1 ? `1px solid ${P.border}` : 'none',
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: P.text, fontFamily: F.mono }}>
                        {s.key}
                      </div>
                      {s.description && (
                        <div style={{ fontSize: 11, color: P.textMute, marginTop: 2 }}>
                          {s.description}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input
                        value={getValue(s.key)}
                        onChange={e => setLocal(l => ({ ...l, [s.key]: e.target.value }))}
                        style={{
                          width: 140, padding: '5px 8px', borderRadius: 6,
                          background: P.bg, border: `1px solid ${P.border}`,
                          color: P.text, fontSize: 12, fontFamily: F.mono, outline: 'none',
                        }}
                      />
                      {local[s.key] !== undefined &&
                        local[s.key] !== (allSettings.find(x => x.key === s.key)?.value ?? '') && (
                        <Btn
                          size="sm" variant="primary"
                          onClick={() => handleSave(s.key)}
                          disabled={saving === s.key}
                        >
                          {saving === s.key ? '…' : 'Save'}
                        </Btn>
                      )}
                    </div>
                  </div>
                ))}
                {groupSettings.length === 0 && (
                  <div style={{ fontSize: 13, color: P.textMute }}>No settings in this group.</div>
                )}
              </Card>
            )}

            {/* Backend info */}
            <Card style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: P.text, marginBottom: 8 }}>Backend</div>
              <div style={{ fontFamily: F.mono, fontSize: 11, color: P.textMute, lineHeight: 1.8 }}>
                <div><span style={{ color: P.textFaint }}>URL: </span>http://127.0.0.1:8765</div>
                <div>
                  <span style={{ color: P.textFaint }}>Start: </span>
                  <span style={{ color: P.text }}>uvicorn qa_ai.server:app --host 127.0.0.1 --port 8765</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}
