import { useEffect, useCallback } from 'react';
import { Shield, X, AlertTriangle, Check } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { PermissionRecord } from '../../types/api';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface PermissionModalProps {
  permission: PermissionRecord;
  onApprove: (id: string, reason?: string) => void;
  onDeny: (id: string, reason?: string) => void;
  onClose: () => void;
}

const RISK_COLOR = { high: P.fail, medium: P.unclear, low: P.pass };

export function PermissionModal({ permission, onApprove, onDeny, onClose }: PermissionModalProps) {
  const riskColor = RISK_COLOR[permission.risk_level ?? 'low'];
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
        aria-labelledby="permission-modal-title"
        ref={trapRef}
        tabIndex={-1}
        style={{
          width: 460, background: P.card, border: `1px solid ${P.borderHi}`,
          borderRadius: 12, boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
          animation: 'fadeIn 0.15s ease-out', outline: 'none',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '18px 20px', borderBottom: `1px solid ${P.border}`,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 9,
            background: `${riskColor}18`, border: `1px solid ${riskColor}33`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <Shield size={16} color={riskColor} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="permission-modal-title" style={{ fontSize: 14, fontWeight: 600, color: P.text, marginBottom: 2 }}>
              Permission Request
            </div>
            <div style={{ fontSize: 12, color: P.textMute }}>{permission.action_type}</div>
          </div>
          <button aria-label="Close dialog" onClick={onClose} style={{ color: P.textMute, padding: 4, borderRadius: 5, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '18px 20px' }}>
          <p style={{ fontSize: 13, color: P.text, lineHeight: 1.6, marginBottom: 14 }}>
            {permission.description}
          </p>

          {permission.what_will_happen && permission.what_will_happen.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: P.textMute, marginBottom: 6,
                textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: F.mono }}>
                WILL HAPPEN
              </div>
              {permission.what_will_happen.map((item, i) => (
                <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 4, alignItems: 'flex-start' }}>
                  <Check size={11} color={P.pass} style={{ marginTop: 2, flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: P.textDim }}>{item}</span>
                </div>
              ))}
            </div>
          )}

          {permission.what_will_not && (
            <div style={{
              padding: '8px 12px', borderRadius: 7,
              background: P.passSoft, border: `1px solid ${P.pass}22`,
              fontSize: 12, color: P.textDim, marginBottom: 12,
            }}>
              ✓ {permission.what_will_not}
            </div>
          )}

          {permission.risk_level && permission.risk_level !== 'low' && (
            <div style={{
              display: 'flex', gap: 6, padding: '8px 12px', borderRadius: 7,
              background: `${riskColor}12`, border: `1px solid ${riskColor}33`,
              alignItems: 'center', marginBottom: 4,
            }}>
              <AlertTriangle size={12} color={riskColor} />
              <span style={{ fontSize: 12, color: riskColor, fontWeight: 500 }}>
                {permission.risk_level.toUpperCase()} RISK
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{
          display: 'flex', gap: 8, padding: '14px 20px',
          borderTop: `1px solid ${P.border}`, justifyContent: 'flex-end',
        }}>
          <button onClick={() => onDeny(permission.id)} style={{
            padding: '7px 16px', borderRadius: 7, fontSize: 13, fontWeight: 500,
            background: P.failSoft, border: `1px solid ${P.fail}33`,
            color: P.fail, cursor: 'pointer',
          }}>
            Deny
          </button>
          <button onClick={() => onApprove(permission.id)} style={{
            padding: '7px 20px', borderRadius: 7, fontSize: 13, fontWeight: 500,
            background: P.accent, color: '#fff', cursor: 'pointer',
          }}>
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
