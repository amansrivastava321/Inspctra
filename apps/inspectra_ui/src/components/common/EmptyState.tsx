import type { ReactNode } from 'react';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { P, F } from '../../design/tokens';

export function EmptyState({ icon, title, description, action, secondaryAction }: {
  icon?: ReactNode; title: string; description?: string;
  action?: ReactNode; secondaryAction?: ReactNode;
}) {
  return (
    <div data-testid="empty-state" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '48px 24px', textAlign: 'center',
    }}>
      {icon && <div style={{ color: P.textFaint, marginBottom: 16, opacity: 0.5 }}>{icon}</div>}
      <div style={{ fontSize: 15, fontWeight: 500, color: P.textDim, marginBottom: 6 }}>{title}</div>
      {description && (
        <div style={{ fontSize: 13, color: P.textMute, maxWidth: 360, lineHeight: 1.6 }}>
          {description}
        </div>
      )}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
      {secondaryAction && <div style={{ marginTop: 8 }}>{secondaryAction}</div>}
    </div>
  );
}

export function BlockedState({ icon, title, description, action }: {
  icon?: ReactNode; title: string; description?: string; action?: ReactNode;
}) {
  return (
    <div data-testid="blocked-state" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '40px 24px', textAlign: 'center',
      borderRadius: 10, background: P.unclearSoft, border: `1px solid ${P.unclear}44`,
    }}>
      <div style={{ color: P.unclear, marginBottom: 12, opacity: 0.9 }}>
        {icon ?? <AlertTriangle size={36} />}
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: P.unclear, marginBottom: 8 }}>
        {title}
      </div>
      {description && (
        <div style={{ fontSize: 13, color: P.textDim, maxWidth: 380, lineHeight: 1.6 }}>
          {description}
        </div>
      )}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

function timeAgo(date: Date): string {
  const secs = Math.floor((Date.now() - date.getTime()) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

export function StaleDataState({ fetchedAt, onRefresh, staleMs = 5 * 60 * 1000 }: {
  fetchedAt: Date | null; onRefresh: () => void; staleMs?: number;
}) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick(n => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  if (!fetchedAt) return null;
  if (Date.now() - fetchedAt.getTime() <= staleMs) return null;

  return (
    <div data-testid="stale-data-state" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 10px', borderRadius: 6, marginBottom: 12,
      background: `${P.unclear}10`, border: `1px solid ${P.unclear}22`,
      fontSize: 12, color: P.textMute,
    }}>
      <RefreshCw size={11} style={{ color: P.unclear }} />
      <span>Last updated {timeAgo(fetchedAt)}</span>
      <button
        data-testid="stale-refresh-btn"
        onClick={onRefresh}
        style={{
          marginLeft: 4, padding: '1px 8px', borderRadius: 4, fontSize: 11,
          background: `${P.unclear}18`, border: `1px solid ${P.unclear}33`,
          color: P.unclear, cursor: 'pointer',
        }}>
        Refresh
      </button>
    </div>
  );
}

export function PartialConfigBanner({ message, action }: {
  message: string; action?: ReactNode;
}) {
  return (
    <div data-testid="partial-config-banner" style={{
      padding: '12px 16px', borderRadius: 8,
      background: P.accentSoft, border: `1px solid ${P.accent}33`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
    }}>
      <div style={{ fontSize: 12, color: P.textDim, lineHeight: 1.5 }}>{message}</div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  );
}

export function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{
          height: 36, borderRadius: 6, background: P.cardHi,
          animation: 'pulse 1.5s ease-in-out infinite',
          animationDelay: `${i * 0.08}s`,
          opacity: 1 - i * 0.12,
        }} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={{ padding: '20px 24px', background: P.failSoft,
      border: `1px solid ${P.fail}33`, borderRadius: 8,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: P.fail, marginBottom: 2 }}>Error</div>
        <div style={{ fontSize: 12, color: P.textDim }}>{message}</div>
      </div>
      {onRetry && (
        <button onClick={onRetry} style={{
          padding: '5px 12px', borderRadius: 6, fontSize: 12,
          background: P.cardHi, border: `1px solid ${P.border}`,
          color: P.textDim, cursor: 'pointer',
        }}>Retry</button>
      )}
    </div>
  );
}

/** Shown when backend is not reachable. Includes start command. */
export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  const nav = useNavigate();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '48px 24px', textAlign: 'center', gap: 12 }}>
      <div style={{ width: 10, height: 10, borderRadius: 99, background: P.fail,
        boxShadow: `0 0 8px ${P.fail}` }} />
      <div style={{ fontSize: 15, fontWeight: 500, color: P.textDim }}>Backend offline</div>
      <div style={{ fontSize: 12, color: P.textMute, maxWidth: 440 }}>
        Start the Inspectra backend to see live data.
      </div>
      <div style={{
        background: P.bg, border: `1px solid ${P.border}`, borderRadius: 7,
        padding: '9px 16px', display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontFamily: F.mono, fontSize: 12, color: P.accent }}>$</span>
        <span style={{ fontFamily: F.mono, fontSize: 12, color: P.text, userSelect: 'all' }}>
          uvicorn qa_ai.server:app --reload --host 127.0.0.1 --port 8765
        </span>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        {onRetry && (
          <button onClick={onRetry} style={{
            padding: '5px 14px', borderRadius: 6, fontSize: 12,
            background: P.accentSoft, border: `1px solid ${P.accent}33`,
            color: P.accent, cursor: 'pointer',
          }}>Retry connection</button>
        )}
        <button onClick={() => nav('/demo')} style={{
          padding: '5px 14px', borderRadius: 6, fontSize: 12,
          background: '#312e8133', border: '1px solid #6366f166',
          color: '#a5b4fc', cursor: 'pointer',
        }}>Try Demo</button>
      </div>
    </div>
  );
}
