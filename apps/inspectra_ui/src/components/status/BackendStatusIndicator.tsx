import { useState, useEffect } from 'react';
import { P } from '../../design/tokens';
import { getBackendStatus, onBackendStatus, checkHealth } from '../../api/client';
import type { BackendStatus } from '../../types/api';
import { useWorkspaceMode } from '../../state/WorkspaceModeContext';

const STATUS_STYLE: Record<BackendStatus, { c: string; label: string }> = {
  online:   { c: P.pass,    label: 'Online' },
  offline:  { c: P.fail,    label: 'Offline' },
  degraded: { c: P.unclear, label: 'Degraded' },
};

export function BackendStatusIndicator() {
  const { isDemo } = useWorkspaceMode();
  const [status, setStatus] = useState<BackendStatus>(getBackendStatus());

  useEffect(() => {
    if (isDemo) return;
    void checkHealth();
    const off = onBackendStatus(setStatus);
    return off;
  }, [isDemo]);

  if (isDemo) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'default' }} title="Static demo data">
        <span style={{ width: 6, height: 6, borderRadius: 99, background: '#818cf8', flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: '#a5b4fc' }}>Demo</span>
      </div>
    );
  }

  const { c, label } = STATUS_STYLE[status];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'default' }}
      title={`Backend: ${label}`}>
      <span style={{
        width: 6, height: 6, borderRadius: 99, background: c, flexShrink: 0,
        boxShadow: status === 'online' ? `0 0 6px ${c}` : undefined,
        animation: status === 'offline' ? undefined : 'pulse 2s ease-in-out infinite',
      }} />
      <span style={{ fontSize: 11, color: P.textMute }}>{label}</span>
    </div>
  );
}
