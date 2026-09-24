import React, { useState, useEffect, useRef } from 'react';
import type { ReactNode, CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { P, F } from '../../design/tokens';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { getBackendStatus, onBackendStatus } from '../../api/client';
import type { BackendStatus } from '../../types/api';
import { DEMO_READ_ONLY_TOOLTIP, useWorkspaceMode } from '../../state/WorkspaceModeContext';
import { ProvenanceBadge } from '../ProvenanceBadge';
import type { Provenance } from '../../types/api';
import { useMediaQuery } from '../../hooks/useMediaQuery';

// ── Global backend status banner ──────────────────────────────────────────────

function BackendStatusBanner() {
  const [status, setStatus] = useState<BackendStatus>(getBackendStatus());

  useEffect(() => {
    const unsub = onBackendStatus(setStatus);
    return unsub;
  }, []);

  if (status === 'online') return null;

  const cfg: Record<Exclude<BackendStatus, 'online'>, { bg: string; border: string; dot: string; text: string; msg: string }> = {
    offline: {
      bg: P.failSoft, border: `${P.fail}33`, dot: P.fail,
      text: P.fail,
      msg: 'Backend offline — run: uvicorn qa_ai.server:app --reload --host 127.0.0.1 --port 8765',
    },
    degraded: {
      bg: P.unclearSoft, border: `${P.unclear}33`, dot: P.unclear,
      text: P.unclear,
      msg: 'Backend degraded — some API calls failed. Run Runtime Doctor to diagnose.',
    },
  };

  const c = cfg[status];

  return (
    <div role="status" aria-live="polite" style={{
      padding: '5px 16px', background: c.bg, borderBottom: `1px solid ${c.border}`,
      display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 99, background: c.dot, flexShrink: 0 }} />
      <span style={{ fontSize: 11, color: c.text, fontFamily: F.mono }}>{c.msg}</span>
    </div>
  );
}

function DemoWorkspaceBanner() {
  const nav = useNavigate();
  const { realWorkspacePath } = useWorkspaceMode();
  return (
    <div role="status" aria-live="polite" style={{
      padding: '7px 16px', background: '#312e81', borderBottom: '1px solid #6366f1',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      flexShrink: 0, color: '#eef2ff',
    }}>
      <span style={{ fontSize: 12, fontWeight: 600 }}>
        Demo Workspace — Sample data for exploration. No real tests are running.
      </span>
      <button
        data-demo-allowed
        onClick={() => nav(realWorkspacePath)}
        style={{
          padding: '4px 10px', borderRadius: 6, border: '1px solid #a5b4fc',
          background: '#eef2ff', color: '#312e81', cursor: 'pointer', fontWeight: 600,
        }}
      >Leave Demo</button>
    </div>
  );
}

// ── AppShell ──────────────────────────────────────────────────────────────────

interface AppShellProps {
  children: ReactNode;
  section?: string;
  title?: string;
  actions?: ReactNode;
  readinessScore?: number;
  readinessSubtitle?: string;
  contentStyle?: CSSProperties;
  provenance?: Provenance | null;
  provenanceSource?: string;
}

export function AppShell({
  children, section, title, actions,
  readinessScore, readinessSubtitle, contentStyle,
  provenance, provenanceSource,
}: AppShellProps) {
  const { isDemo } = useWorkspaceMode();
  const shellRef = useRef<HTMLDivElement>(null);
  const isMobile = useMediaQuery('(max-width: 767px)');

  // On desktop: sidebar starts open. On mobile: sidebar starts closed.
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 768 : true,
  );

  // When resizing from mobile → desktop, auto-open sidebar.
  useEffect(() => {
    if (!isMobile) setSidebarOpen(true);
  }, [isMobile]);

  // Escape key closes mobile sidebar.
  useEffect(() => {
    if (!isMobile) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isMobile]);

  // Demo mode: lock write fields/buttons.
  useEffect(() => {
    if (!isDemo || !shellRef.current) return;
    const lockFields = () => {
      shellRef.current?.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('input, textarea, select')
        .forEach(field => {
          field.disabled = true;
          field.title = DEMO_READ_ONLY_TOOLTIP;
        });
      const writeAction = /\b(add|approve|apply|clear|connect|create|delete|discover|edit|evaluate|export|generate|install|remove|reset|retest|run|save|scan|skip|start|submit|update|upload)\b/i;
      shellRef.current?.querySelectorAll<HTMLButtonElement>('button').forEach(button => {
        if (button.hasAttribute('data-demo-allowed')) return;
        const intent = `${button.textContent ?? ''} ${button.title} ${button.getAttribute('aria-label') ?? ''}`;
        if (writeAction.test(intent)) {
          button.disabled = true;
          button.title = DEMO_READ_ONLY_TOOLTIP;
        }
      });
    };
    lockFields();
    const observer = new MutationObserver(lockFields);
    observer.observe(shellRef.current, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [children, isDemo]);

  const mainPadding = isMobile ? 12 : 20;

  return (
    <div
      ref={shellRef}
      style={{ display: 'flex', height: '100vh', background: P.bg, overflow: 'hidden' }}
    >
      {/* Desktop sidebar — rendered in flex flow */}
      {!isMobile && sidebarOpen && (
        <Sidebar readinessScore={readinessScore} readinessSubtitle={readinessSubtitle} />
      )}

      {/* Main content area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {isDemo ? <DemoWorkspaceBanner /> : <BackendStatusBanner />}
        <Topbar
          section={section} title={title} actions={actions}
          provenance={provenance} provenanceSource={provenanceSource}
          sidebarVisible={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(o => !o)}
          isMobile={isMobile}
        />
        <main style={{ flex: 1, overflowY: 'auto', padding: mainPadding, ...contentStyle }}>
          <div>{children}</div>
        </main>
      </div>

      {/* Screen-reader live region for announcements */}
      <div id="a11y-announcer" aria-live="polite" aria-atomic="true" className="sr-only" />

      {/* Mobile sidebar — fixed overlay */}
      {isMobile && sidebarOpen && (
        <>
          {/* Scrim */}
          <div
            aria-hidden="true"
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 8999,
              background: 'rgba(0,0,0,0.55)',
            }}
          />
          {/* Drawer */}
          <div
            className="mobile-sidebar-overlay"
            style={{
              position: 'fixed', top: 0, left: 0, bottom: 0,
              zIndex: 9000, width: 232,
            }}
          >
            <Sidebar
              readinessScore={readinessScore}
              readinessSubtitle={readinessSubtitle}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </>
      )}
    </div>
  );
}

// ── PageHeader ────────────────────────────────────────────────────────────────

export function PageHeader({ title, subtitle, actions, provenance, provenanceSource }: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  provenance?: Provenance | null;
  provenanceSource?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 8 }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: subtitle ? 4 : 0 }}>
          <h1 className="page-header-title" style={{ fontSize: 22, fontWeight: 600, color: P.text, margin: 0 }}>{title}</h1>
          {provenanceSource && <ProvenanceBadge provenance={provenance} source={provenanceSource} />}
        </div>
        {subtitle && <p style={{ fontSize: 13, color: P.textDim }}>{subtitle}</p>}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>{actions}</div>}
    </div>
  );
}

// ── StatCard ──────────────────────────────────────────────────────────────────

export function StatCard({ label, value, sub, valueColor, provenance, provenanceSource }: {
  label: string;
  value: string | number;
  sub?: string;
  valueColor?: string;
  provenance?: Provenance | null;
  provenanceSource?: string;
}) {
  return (
    <div style={{
      background: P.card, border: `1px solid ${P.border}`, borderRadius: 10,
      padding: '16px 20px', flex: 1, minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
        <div style={{ fontSize: 10, color: P.textMute, textTransform: 'uppercase',
          letterSpacing: '0.08em', fontFamily: "'JetBrains Mono', monospace" }}>
          {label}
        </div>
        {provenanceSource && <ProvenanceBadge provenance={provenance} source={provenanceSource} />}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: valueColor ?? P.text,
        fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: P.textMute, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  pad?: number;
}
export function Card({ children, style, pad = 16, ...rest }: CardProps) {
  return (
    <div style={{
      background: P.card, border: `1px solid ${P.border}`, borderRadius: 10,
      padding: pad, boxShadow: P.shadowCard, ...style,
    }} {...rest}>
      {children}
    </div>
  );
}

// ── Btn ───────────────────────────────────────────────────────────────────────

interface BtnProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onClick' | 'type'> {
  onClick?: (e?: React.MouseEvent) => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  type?: 'button' | 'submit';
  demoWrite?: boolean;
}
export function Btn({ children, onClick, variant = 'secondary', size = 'md', disabled, style, type = 'button', title, demoWrite = false, ...rest }: BtnProps) {
  const { isDemo } = useWorkspaceMode();
  const demoDisabled = isDemo && demoWrite;
  const resolvedDisabled = disabled || demoDisabled;
  const base: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderRadius: 7, fontWeight: 500, cursor: resolvedDisabled ? 'not-allowed' : 'pointer',
    opacity: resolvedDisabled ? 0.5 : 1, border: 'none', transition: 'background 0.12s, opacity 0.12s',
    fontFamily: 'inherit',
  };
  const sizeMap = { sm: { fontSize: 12, padding: '5px 10px' }, md: { fontSize: 13, padding: '7px 14px' }, lg: { fontSize: 14, padding: '9px 18px' } };
  const variantMap: Record<string, CSSProperties> = {
    primary:   { background: P.accent, color: '#fff' },
    secondary: { background: P.cardHi, border: `1px solid ${P.border}`, color: P.text },
    ghost:     { background: 'transparent', color: P.textDim },
    danger:    { background: P.failSoft, border: `1px solid ${P.fail}33`, color: P.fail },
  };
  return (
    <button type={type} onClick={onClick} disabled={resolvedDisabled} title={demoDisabled ? DEMO_READ_ONLY_TOOLTIP : title}
      style={{ ...base, ...sizeMap[size], ...variantMap[variant], ...style }} {...rest}>
      {children}
    </button>
  );
}
