/**
 * NativePermissionPanel
 *
 * Shown in the start-run dialog for Mac, Windows, Android and iOS app targets. Lists what the platform needs
 * (tools and OS permissions, each of which can be requested from the OS where it allows that), then asks the
 * user to allow Inspectra to drive apps there. Nothing is driven until they do.
 */
import { useCallback, useEffect, useState } from 'react';
import { P, F } from '../../design/tokens';
import { Btn } from '../layout/AppShell';
import { del, get, post, put } from '../../api/client';
import type { NativePlatform } from '../../config/native';

export interface NativeRequirement {
  id: string;
  label: string;
  status: 'granted' | 'missing' | 'unknown';
  how_to_fix: string;
  can_request: boolean;
  optional: boolean;
}

export interface NativeReadiness {
  platform: NativePlatform;
  label: string;
  requirements: NativeRequirement[];
  tools_ready: boolean;
  consent: { scopes: string[]; unattended: boolean; granted_at: string } | null;
  consent_scopes: { id: string; label: string }[];
  ready: boolean;
}

const STATUS_TEXT: Record<NativeRequirement['status'], string> = {
  granted: 'Ready',
  missing: 'Missing',
  unknown: 'Not checked yet',
};

export function NativePermissionPanel({
  platform,
  onReadyChange,
}: {
  platform: NativePlatform;
  onReadyChange: (ready: boolean) => void;
}) {
  const [readiness, setReadiness] = useState<NativeReadiness | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [unattended, setUnattended] = useState(false);

  const load = useCallback(async () => {
    setError('');
    try {
      const data = await get<NativeReadiness>(`/native/${platform}/readiness`);
      setReadiness(data);
      onReadyChange(data.ready);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onReadyChange(false);
    }
  }, [platform, onReadyChange]);

  useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!readiness) {
    return (
      <div style={{ fontSize: 12, color: error ? P.fail : P.textMute }}>
        {error ? `Could not check this computer: ${error}` : 'Checking what this computer needs…'}
      </div>
    );
  }

  const desktop = platform === 'native_macos' || platform === 'native_windows';
  const allTicked = readiness.consent_scopes.every(s => checked[s.id]);

  return (
    <fieldset
      aria-label="Permissions"
      style={{ border: `1px solid ${P.border}`, borderRadius: 8, padding: '10px 14px', margin: 0,
        display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <legend style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase',
        letterSpacing: '0.06em', padding: '0 6px' }}>
        Permissions · {readiness.label}
      </legend>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {readiness.requirements.map(r => (
          <div key={r.id} data-testid={`requirement-${r.id}`} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span
              aria-label={STATUS_TEXT[r.status]}
              style={{ width: 8, height: 8, borderRadius: 99, marginTop: 5, flexShrink: 0,
                background: r.status === 'granted' ? P.pass : r.status === 'missing' ? (r.optional ? P.unclear : P.fail) : P.textMute }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: P.text }}>
                {r.label} — <span style={{ color: P.textMute }}>{STATUS_TEXT[r.status]}{r.optional && r.status !== 'granted' ? ' (optional)' : ''}</span>
              </div>
              {r.status !== 'granted' && r.how_to_fix && (
                <div style={{ fontSize: 11, color: P.textMute }}>{r.how_to_fix}</div>
              )}
            </div>
            {r.status !== 'granted' && r.can_request && (
              <Btn
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => act(() => post(`/native/${platform}/permissions/${r.id}/request`))}
              >
                Ask the system
              </Btn>
            )}
          </div>
        ))}
        <div>
          <Btn size="sm" variant="ghost" disabled={busy} onClick={() => act(async () => undefined)}>Check again</Btn>
        </div>
      </div>

      {desktop && (
        <div role="note" style={{ fontSize: 11, color: P.unclear }}>
          Desktop app runs use your real screen: Inspectra moves the pointer and types, so leave the computer alone
          until the run finishes.
        </div>
      )}

      {readiness.consent ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: P.text }}>
          <span>
            You allowed Inspectra to drive {readiness.label}s
            {readiness.consent.unattended ? ', including scheduled runs while you are away' : ''}.
          </span>
          <Btn size="sm" variant="ghost" disabled={busy} onClick={() => act(() => del(`/native/${platform}/consent`))}>
            Take back
          </Btn>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 12, color: P.text, fontWeight: 500 }}>Allow Inspectra to:</div>
          {readiness.consent_scopes.map(s => (
            <label key={s.id} style={{ display: 'flex', gap: 8, fontSize: 12, color: P.text, alignItems: 'flex-start' }}>
              <input
                type="checkbox"
                checked={Boolean(checked[s.id])}
                onChange={e => setChecked(prev => ({ ...prev, [s.id]: e.target.checked }))}
                style={{ accentColor: P.accent, marginTop: 2 }}
              />
              {s.label}
            </label>
          ))}
          <label style={{ display: 'flex', gap: 8, fontSize: 12, color: P.textMute, alignItems: 'flex-start' }}>
            <input
              type="checkbox"
              checked={unattended}
              onChange={e => setUnattended(e.target.checked)}
              style={{ accentColor: P.accent, marginTop: 2 }}
            />
            Also let scheduled runs do this while I am away (optional)
          </label>
          <div>
            <Btn
              size="sm"
              variant="primary"
              disabled={busy || !allTicked}
              onClick={() => act(() => put(`/native/${platform}/consent`, {
                scopes: readiness.consent_scopes.map(s => s.id),
                unattended,
              }))}
            >
              Allow
            </Btn>
          </div>
        </div>
      )}

      {!readiness.tools_ready && (
        <div style={{ fontSize: 11, color: P.fail }}>Fix the missing items above, then press "Check again".</div>
      )}
      {error && <div role="alert" style={{ fontSize: 12, color: P.fail }}>{error}</div>}
    </fieldset>
  );
}
