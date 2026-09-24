import { useState, useEffect, useCallback } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Terminal, X, Clock, HardDrive, Wifi } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { DoctorFix } from '../../types/api';

interface SetupActionModalProps {
  fix: DoctorFix;
  onRunManually: (id: string) => void;
  onSkip: (id: string) => void;
  onClose: () => void;
}

export function SetupActionModal({ fix, onRunManually, onSkip, onClose }: SetupActionModalProps) {
  const [confirmed, setConfirmed] = useState(false);
  const trapRef = useFocusTrap();
  const handleEscape = useCallback((e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }, [onClose]);
  useEffect(() => {
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [handleEscape]);

  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(8,9,11,0.75)', backdropFilter: 'blur(4px)',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="setup-action-modal-title"
        ref={trapRef}
        tabIndex={-1}
        style={{
          width: 480, background: P.card, border: `1px solid ${P.borderHi}`,
          borderRadius: 12, boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
          animation: 'fadeIn 0.15s ease-out', outline: 'none',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '18px 20px', borderBottom: `1px solid ${P.border}` }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: P.accentSoft,
            border: `1px solid ${P.accent}33`, display: 'flex', alignItems: 'center',
            justifyContent: 'center', flexShrink: 0 }}>
            <Terminal size={16} color={P.accent} />
          </div>
          <div style={{ flex: 1 }}>
            <div id="setup-action-modal-title" style={{ fontSize: 14, fontWeight: 600, color: P.text, marginBottom: 2 }}>
              {fix.title}
            </div>
            {fix.description && (
              <div style={{ fontSize: 12, color: P.textMute }}>{fix.description}</div>
            )}
          </div>
          <button aria-label="Close dialog" onClick={onClose} style={{ color: P.textMute, padding: 4, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <X size={14} />
          </button>
        </div>

        {/* Details */}
        <div style={{ padding: '16px 20px' }}>
          {/* Meta */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 14 }}>
            {fix.time_estimate && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Clock size={11} color={P.textMute} />
                <span style={{ fontSize: 11, color: P.textMute }}>{fix.time_estimate}</span>
              </div>
            )}
            {fix.disk_estimate && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <HardDrive size={11} color={P.textMute} />
                <span style={{ fontSize: 11, color: P.textMute }}>{fix.disk_estimate}</span>
              </div>
            )}
          </div>

          {/* Commands */}
          {fix.commands && fix.commands.length > 0 && (
            <div style={{ background: P.bg, border: `1px solid ${P.border}`,
              borderRadius: 7, padding: '10px 14px', marginBottom: 14 }}>
              {fix.commands.map((cmd, i) => (
                <div key={i} style={{ fontFamily: F.mono, fontSize: 12,
                  color: P.text, marginBottom: i < fix.commands!.length - 1 ? 6 : 0 }}>
                  <span style={{ color: P.accent, userSelect: 'none' }}>$ </span>{cmd}
                </div>
              ))}
            </div>
          )}

          {/* Confirm */}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 4 }}>
            <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}
              style={{ accentColor: P.accent }} />
            <span style={{ fontSize: 12, color: P.textDim }}>
              I understand Inspectra will run the commands above in my terminal
            </span>
          </label>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, padding: '14px 20px',
          borderTop: `1px solid ${P.border}`, justifyContent: 'space-between' }}>
          <button onClick={() => onSkip(fix.id)} style={{
            padding: '7px 14px', borderRadius: 7, fontSize: 12,
            background: 'transparent', border: `1px solid ${P.border}`,
            color: P.textMute, cursor: 'pointer',
          }}>
            Skip for now
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => onRunManually(fix.id)} style={{
              padding: '7px 14px', borderRadius: 7, fontSize: 13,
              background: P.cardHi, border: `1px solid ${P.border}`,
              color: P.textDim, cursor: 'pointer',
            }}>
              Run command manually
            </button>
            {fix.action_label && (
              <button disabled={!confirmed} onClick={() => { if (confirmed) onClose(); }} style={{
                padding: '7px 16px', borderRadius: 7, fontSize: 13, fontWeight: 500,
                background: confirmed ? P.accent : P.cardHi, color: confirmed ? '#fff' : P.textMute,
                cursor: confirmed ? 'pointer' : 'not-allowed', transition: 'background 0.15s',
              }}>
                {fix.action_label}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
