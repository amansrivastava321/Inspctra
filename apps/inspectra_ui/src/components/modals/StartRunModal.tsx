/**
 * StartRunModal
 *
 * Lists available app targets and POSTs to start a live run for a given pack.
 * On success, navigates to /runs/{run_id}.
 */
import { useState, useEffect, useCallback } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { useNavigate } from 'react-router-dom';
import { Play, X } from 'lucide-react';
import { P, F } from '../../design/tokens';
import { Btn } from '../layout/AppShell';
import { get, post } from '../../api/client';
import type { AppTarget, LiveRunRecord } from '../../types/api';
import { PreviewBadge } from '../PreviewBadge';
import { isPreviewAppType, PREVIEW_TOOLTIP } from '../../config/capabilities';

interface StartRunModalProps {
  packId: string;
  packName: string;
  onClose: () => void;
  isManual?: boolean;
}

export function StartRunModal({ packId, packName, onClose, isManual = false }: StartRunModalProps) {
  const nav = useNavigate();
  const trapRef = useFocusTrap();
  const handleEscape = useCallback((e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }, [onClose]);
  useEffect(() => {
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [handleEscape]);
  const [apps, setApps] = useState<AppTarget[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [selectedAppId, setSelectedAppId] = useState('');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  // Load app targets on mount
  useEffect(() => {
    let cancelled = false;
    get<AppTarget[]>('/apps')
      .then(data => { if (!cancelled) setApps(data); })
      .catch(err => { if (!cancelled) setLoadError(String(err instanceof Error ? err.message : err)); });
    return () => { cancelled = true; };
  }, []);

  const handleStart = async () => {
    if (!selectedAppId) return;
    setStarting(true);
    setStartError('');
    try {
      const run = await post<LiveRunRecord>(
        isManual ? `/validation-packs/${packId}/runs` : `/validation-packs/${packId}/run`,
        { app_target_id: selectedAppId, execution_mode: isManual ? 'manual' : 'automated' },
      );
      nav(`/runs/${run.id}`);
    } catch (err) {
      setStartError(String(err instanceof Error ? err.message : err));
      setStarting(false);
    }
  };

  return (
    /* Backdrop */
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="start-run-modal-title"
        ref={trapRef}
        tabIndex={-1}
        style={{
          background: P.card, border: `1px solid ${P.border}`, borderRadius: 12,
          width: 480, maxWidth: '90vw', padding: 24,
          display: 'flex', flexDirection: 'column', gap: 16,
          outline: 'none',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div id="start-run-modal-title" style={{ fontSize: 16, fontWeight: 700, color: P.text }}>
              {isManual ? 'Start manual run' : 'Start live run'}
            </div>
            <div style={{ fontSize: 12, color: P.textMute, marginTop: 2 }}>{packName}</div>
          </div>
          <button aria-label="Close dialog" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer',
            color: P.textMute, padding: 4, display: 'flex', alignItems: 'center' }}>
            <X size={16} />
          </button>
        </div>

        {/* App target selection */}
        <div>
          <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Select app target
          </div>

          {loadError && (
            <div style={{ fontSize: 12, color: P.fail, marginBottom: 8 }}>
              Could not load apps: {loadError}
            </div>
          )}

          {!apps && !loadError && (
            <div style={{ fontSize: 12, color: P.textMute, padding: '12px 0' }}>Loading apps…</div>
          )}

          {apps && apps.length === 0 && (
            <div style={{ padding: '12px 14px', borderRadius: 8, background: P.cardHi,
              border: `1px solid ${P.border}`, fontSize: 12, color: P.textMute }}>
              No app targets configured.{' '}
              <span style={{ color: P.accent, cursor: 'pointer' }}
                onClick={() => { onClose(); nav('/projects/new'); }}>
                Add one first
              </span>.
            </div>
          )}

          {apps && apps.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 240, overflowY: 'auto' }}>
              {apps.map(app => {
                const preview = isPreviewAppType(app.app_type);
                return (
                <button
                  key={app.id}
                  type="button"
                  disabled={preview}
                  aria-label={`${app.name} ${app.app_type}${preview ? ' Preview' : ''}`}
                  title={preview ? PREVIEW_TOOLTIP : undefined}
                  onClick={() => setSelectedAppId(app.id)}
                  style={{
                  width: '100%', padding: '10px 14px', borderRadius: 8,
                  cursor: preview ? 'not-allowed' : 'pointer',
                  border: `1px solid ${selectedAppId === app.id ? P.accent : P.border}`,
                  background: selectedAppId === app.id ? P.accentSoft : P.cardHi,
                  transition: 'border-color 0.12s, background 0.12s',
                  display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left',
                  opacity: preview ? 0.72 : 1,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: P.text }}>{app.name}</div>
                    <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>
                      {app.app_type}
                    </div>
                  </div>
                  {preview && <PreviewBadge />}
                  {selectedAppId === app.id && (
                    <div style={{ width: 8, height: 8, borderRadius: 99, background: P.accent, flexShrink: 0 }} />
                  )}
                </button>
              );})}
            </div>
          )}
        </div>

        {startError && (
          <div style={{ padding: '8px 12px', borderRadius: 7,
            background: P.failSoft, border: `1px solid ${P.fail}33`,
            fontSize: 12, color: P.fail }}>
            Start failed: {startError}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
          <Btn
            variant="primary"
            onClick={handleStart}
            disabled={!selectedAppId || starting || !apps || apps.length === 0}
          >
            <Play size={12} />
            {starting ? 'Starting…' : 'Start run'}
          </Btn>
        </div>
      </div>
    </div>
  );
}
