/**
 * Shared UI components — pixel-match of premium-core.jsx.
 * Dark mode only. All styling via inline styles for portability.
 */
import React, { CSSProperties, ReactNode } from 'react';
import { P, F, STATUS_MAP, StatusKind } from './tokens';
import { NavLink } from 'react-router-dom';

// ── Card ──────────────────────────────────────────────────────────────────────

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
  pad?: number;
  elevated?: boolean;
  glow?: boolean;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
}

export function Card({ children, style = {}, pad = 20, elevated = false, glow = false, onClick }: CardProps) {
  return (
    <div style={{
      background: elevated ? P.cardHi : P.card,
      border: `1px solid ${P.border}`,
      borderRadius: 14,
      padding: pad,
      boxShadow: glow
        ? `0 0 0 1px ${P.border}, 0 0 60px -20px ${P.accentGlow}, 0 16px 40px -20px rgba(0,0,0,0.6)`
        : `0 1px 0 rgba(255,255,255,0.03) inset, 0 12px 32px -22px rgba(0,0,0,0.7)`,
      position: 'relative',
      cursor: onClick ? 'pointer' : undefined,
      ...style,
    }} onClick={onClick}>
      {children}
    </div>
  );
}

// ── Typography ────────────────────────────────────────────────────────────────

interface DisplayProps {
  children: ReactNode;
  size?: number;
  weight?: number;
  color?: string;
  style?: CSSProperties;
}

export function Display({ children, size = 32, weight = 600, color, style = {} }: DisplayProps) {
  return (
    <div style={{
      fontFamily: F.display,
      fontSize: size,
      fontWeight: weight,
      letterSpacing: size > 28 ? -0.5 : -0.2,
      lineHeight: 1.1,
      color: color || P.text,
      ...style,
    }}>
      {children}
    </div>
  );
}

interface TextProps {
  children: ReactNode;
  size?: number;
  weight?: number;
  color?: string;
  mono?: boolean;
  style?: CSSProperties;
}

export function Text({ children, size = 13, weight = 400, color, mono = false, style = {} }: TextProps) {
  return (
    <div style={{
      fontFamily: mono ? F.mono : F.ui,
      fontSize: size,
      fontWeight: weight,
      color: color || P.text,
      lineHeight: 1.45,
      ...style,
    }}>
      {children}
    </div>
  );
}

export function Eyebrow({ children, color, style = {} }: { children: ReactNode; color?: string; style?: CSSProperties }) {
  return (
    <div style={{
      fontFamily: F.mono,
      fontSize: 10.5,
      fontWeight: 500,
      letterSpacing: 0.8,
      textTransform: 'uppercase',
      color: color || P.textMute,
      ...style,
    }}>
      {children}
    </div>
  );
}

// ── Pill / Badge ──────────────────────────────────────────────────────────────

interface PillProps {
  kind?: StatusKind | string;
  children?: ReactNode;
  style?: CSSProperties;
  small?: boolean;
  dot?: boolean;
  glow?: boolean;
}

export function Pill({ kind = 'pass', children, style = {}, small = false, dot = true, glow = false }: PillProps) {
  const m = STATUS_MAP[kind as StatusKind] || STATUS_MAP.pass;
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: small ? '2px 8px' : '3px 10px',
      borderRadius: 999,
      border: `1px solid ${m.c}33`,
      background: m.s,
      color: m.c,
      fontFamily: F.mono,
      fontSize: small ? 9.5 : 10.5,
      fontWeight: 500,
      letterSpacing: 0.5,
      lineHeight: 1.2,
      boxShadow: glow ? `0 0 0 4px ${m.s}` : 'none',
      whiteSpace: 'nowrap',
      ...style,
    }}>
      {dot && <span style={{
        width: small ? 5 : 6,
        height: small ? 5 : 6,
        borderRadius: 99,
        background: m.c,
        flexShrink: 0,
      }} />}
      {children ?? m.label}
    </span>
  );
}

export function StatusDot({ kind = 'pass', size = 18, glow = false }: { kind?: StatusKind; size?: number; glow?: boolean }) {
  const glyphMap: Record<string, string> = {
    pass: '✓', fail: '✕', unclear: '?', blocked: '⏸', skipped: '–', running: '●',
  };
  const m = STATUS_MAP[kind] || STATUS_MAP.pass;
  return (
    <div style={{
      width: size, height: size,
      borderRadius: 99,
      border: `1.2px solid ${m.c}`,
      background: kind === 'running' ? m.c : `${m.c}22`,
      color: kind === 'running' ? P.bg : m.c,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: F.mono, fontSize: size * 0.55, fontWeight: 600,
      boxShadow: glow ? `0 0 0 4px ${m.c}22, 0 0 12px ${m.c}66` : 'none',
      flexShrink: 0,
    }}>
      {glyphMap[kind] ?? '•'}
    </div>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────

interface ButtonProps {
  children?: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: string;
  style?: CSSProperties;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

export function Button({
  children, variant = 'ghost', size = 'md', icon, style = {}, onClick, disabled = false, type = 'button',
}: ButtonProps) {
  const sizes = {
    sm: { pad: '5px 10px', fs: 12, h: 26 },
    md: { pad: '7px 14px', fs: 13, h: 32 },
    lg: { pad: '10px 18px', fs: 14, h: 40 },
  }[size];

  const variants: Record<string, CSSProperties> = {
    primary: {
      background: P.accent,
      color: '#0a0c14',
      border: `1px solid ${P.accent}`,
      boxShadow: `0 0 0 1px ${P.accent}, 0 8px 24px -8px ${P.accentGlow}, inset 0 1px 0 rgba(255,255,255,0.18)`,
    },
    secondary: {
      background: P.cardHi,
      color: P.text,
      border: `1px solid ${P.borderHi}`,
    },
    ghost: {
      background: 'transparent',
      color: P.textDim,
      border: `1px solid ${P.border}`,
    },
    danger: {
      background: 'transparent',
      color: P.fail,
      border: `1px solid ${P.fail}44`,
    },
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: sizes.pad, height: sizes.h,
        fontSize: sizes.fs, fontWeight: 500,
        fontFamily: F.ui,
        borderRadius: 8,
        cursor: disabled ? 'not-allowed' : 'pointer',
        letterSpacing: -0.1,
        opacity: disabled ? 0.5 : 1,
        ...variants[variant],
        ...style,
      }}
    >
      {icon && <span style={{ fontSize: sizes.fs + 1, opacity: 0.9 }}>{icon}</span>}
      {children}
    </button>
  );
}

// ── Layout helpers ────────────────────────────────────────────────────────────

export function Row({ children, gap = 12, style = {}, onClick }: { children: ReactNode; gap?: number; style?: CSSProperties; onClick?: React.MouseEventHandler<HTMLDivElement> }) {
  return <div style={{ display: 'flex', gap, ...style }} onClick={onClick}>{children}</div>;
}

export function Col({ children, gap = 12, style = {} }: { children: ReactNode; gap?: number; style?: CSSProperties }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap, ...style }}>{children}</div>;
}

export function Divider({ vertical = false, style = {} }: { vertical?: boolean; style?: CSSProperties }) {
  return (
    <div style={{
      [vertical ? 'width' : 'height']: 1,
      background: P.border,
      [vertical ? 'alignSelf' : 'width']: '100%',
      flexShrink: 0,
      ...style,
    }} />
  );
}

// ── Meter ─────────────────────────────────────────────────────────────────────

interface MeterProps {
  value: number;
  color?: string;
  label?: string;
  height?: number;
  animated?: boolean;
  style?: CSSProperties;
}

export function Meter({ value, color, label, height = 4, animated = false, style = {} }: MeterProps) {
  return (
    <div style={{ width: '100%', ...style }}>
      {label && (
        <Row style={{ justifyContent: 'space-between', marginBottom: 4 }}>
          <Text size={11} color={P.textMute}>{label}</Text>
          <Text size={11} mono color={color || P.text}>{value}%</Text>
        </Row>
      )}
      <div style={{ height, borderRadius: 99, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
        <div style={{
          width: `${Math.min(100, Math.max(0, value))}%`,
          height: '100%',
          background: color || P.accent,
          borderRadius: 99,
          boxShadow: animated ? `0 0 12px ${color || P.accent}88` : 'none',
          transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { key: 'Dashboard',   label: 'Dashboard',         to: '/' },
  { key: 'Projects',    label: 'Projects',           to: '/projects' },
  { key: 'Doctor',      label: 'Runtime Doctor',     to: '/doctor' },
  { key: 'Packs',       label: 'Validation Packs',   to: '/packs' },
  { key: 'Runs',        label: 'Live Test Runs',      to: '/runs' },
  { key: 'Evidence',    label: 'Evidence Center',     to: '/evidence' },
  { key: 'Reports',     label: 'Reports',             to: '/reports' },
  { key: 'Connectors',  label: 'Connectors',          to: '/connectors' },
  { key: 'Settings',    label: 'Settings',            to: '/settings' },
];

// SVG nav icons matching premium-core.jsx NavIcon paths
const NAV_ICON_PATHS: Record<string, string> = {
  Dashboard:  'M3 13h6v8H3v-8zm0-10h6v7H3V3zm8 0h6v8h-6V3zm0 10h6v8h-6v-8z',
  Projects:   'M3 5h18v4H3V5zm0 6h12v8H3v-8z',
  Doctor:     'M12 3v18M3 12h18M5.5 5.5l13 13M18.5 5.5l-13 13',
  Packs:      'M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 0h7v7h-7v-7z',
  Runs:       'M5 4l14 8L5 20V4z',
  Evidence:   'M12 2l9 5v10l-9 5-9-5V7l9-5zM12 12l9-5M12 12L3 7M12 12v10',
  Reports:    'M5 3h10l4 4v14H5V3zm10 0v4h4',
  Connectors: 'M6 8v8m12-8v8M2 12h4m12 0h4M6 8h4l2-4 2 4h4',
  Settings:   'M12 8a4 4 0 100 8 4 4 0 000-8zm0 0l3-3m-3 3l-3-3m3 3l-3 3m3-3l3 3',
};

function NavIcon({ name }: { name: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={NAV_ICON_PATHS[name] || NAV_ICON_PATHS.Dashboard} />
    </svg>
  );
}

export function Sidebar({ readinessScore = 84 }: { readinessScore?: number }) {
  return (
    <div style={{
      width: 232, background: P.surface,
      borderRight: `1px solid ${P.border}`,
      display: 'flex', flexDirection: 'column',
      padding: 16, flexShrink: 0,
    }}>
      {/* Workspace button */}
      <button style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 10px',
        background: P.cardHi,
        border: `1px solid ${P.border}`,
        borderRadius: 10,
        textAlign: 'left',
        marginBottom: 16,
        cursor: 'default',
      }}>
        <div style={{
          width: 26, height: 26, borderRadius: 7,
          background: `linear-gradient(135deg, ${P.accent}, #8b5cf6)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontFamily: F.display, fontWeight: 700, fontSize: 13,
          boxShadow: `0 4px 12px -4px ${P.accentGlow}`,
          flexShrink: 0,
        }}>i</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text size={12.5} weight={600}>Inspectra</Text>
          <Text size={10.5} color={P.textMute}>local workspace</Text>
        </div>
        <span style={{ color: P.textMute, fontSize: 14 }}>⌄</span>
      </button>

      {/* Nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {NAV_ITEMS.map(({ key, label, to }) => (
          <NavLink key={key} to={to} end={to === '/'}>
            {({ isActive }) => (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '7px 10px',
                borderRadius: 8,
                background: isActive ? P.accentSoft : 'transparent',
                color: isActive ? P.text : P.textDim,
                fontFamily: F.ui, fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                border: isActive ? `1px solid ${P.accent}22` : '1px solid transparent',
                cursor: 'pointer',
              }}>
                <NavIcon name={key} />
                <span style={{ flex: 1 }}>{label}</span>
                {isActive && <span style={{ width: 4, height: 4, borderRadius: 99, background: P.accent }} />}
              </div>
            )}
          </NavLink>
        ))}
      </div>

      {/* Bottom — readiness + user */}
      <div style={{ marginTop: 'auto', borderTop: `1px solid ${P.border}`, paddingTop: 14 }}>
        <Card pad={12} style={{ background: P.cardHi, borderRadius: 10 }}>
          <Eyebrow>Readiness</Eyebrow>
          <Row gap={4} style={{ alignItems: 'baseline', marginTop: 2 }}>
            <Display size={20}>{readinessScore}</Display>
            <Text size={11} color={P.textMute}>/ 100</Text>
          </Row>
          <div style={{ height: 4, borderRadius: 99, background: 'rgba(255,255,255,0.05)', marginTop: 6, overflow: 'hidden' }}>
            <div style={{
              width: `${readinessScore}%`, height: '100%',
              background: `linear-gradient(90deg, ${P.accent}, ${P.pass})`,
              borderRadius: 99,
              transition: 'width 0.5s ease',
            }} />
          </div>
        </Card>
      </div>
    </div>
  );
}

// ── TopBar ────────────────────────────────────────────────────────────────────

interface TopBarProps {
  title: string;
  crumbs?: string[];
  sub?: string;
  right?: ReactNode;
}

export function TopBar({ title, crumbs = [], sub, right }: TopBarProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '18px 28px',
      borderBottom: `1px solid ${P.border}`,
      gap: 16, flexShrink: 0,
    }}>
      <div>
        {crumbs.length > 0 && (
          <Text size={11.5} color={P.textMute} style={{ marginBottom: 4 }}>
            {crumbs.map((c, i) => (
              <span key={i}>
                {c}
                {i < crumbs.length - 1 && <span style={{ margin: '0 8px', opacity: 0.5 }}>/</span>}
              </span>
            ))}
          </Text>
        )}
        <Display size={20} weight={600}>{title}</Display>
        {sub && <Text size={12.5} color={P.textDim} style={{ marginTop: 4 }}>{sub}</Text>}
      </div>
      {right && <Row gap={8} style={{ alignItems: 'center', flexShrink: 0 }}>{right}</Row>}
    </div>
  );
}

// ── Screen frame ──────────────────────────────────────────────────────────────

interface ScreenProps {
  active?: string;
  title: string;
  crumbs?: string[];
  sub?: string;
  right?: ReactNode;
  children: ReactNode;
  readinessScore?: number;
}

export function Screen({ title, crumbs, sub, right, children, readinessScore }: ScreenProps) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: P.bg, color: P.text,
      display: 'flex', fontFamily: F.ui, overflow: 'hidden',
    }}>
      <Sidebar readinessScore={readinessScore} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar title={title} crumbs={crumbs} sub={sub} right={right} />
        <div style={{ flex: 1, padding: 24, overflow: 'auto', background: P.bg }}>
          {children}
        </div>
      </div>
    </div>
  );
}

// ── Empty / Loading / Error states ────────────────────────────────────────────

export function EmptyState({ message = 'No data yet.', action }: { message?: string; action?: ReactNode }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: 14, padding: 48, color: P.textMute,
    }}>
      <div style={{ fontSize: 32, opacity: 0.3 }}>◻</div>
      <Text size={13} color={P.textMute}>{message}</Text>
      {action}
    </div>
  );
}

export function LoadingSpinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 48 }}>
      <div style={{
        width: 22, height: 22,
        border: `2px solid ${P.border}`,
        borderTopColor: P.accent,
        borderRadius: 99,
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 10,
      background: P.failSoft, border: `1px solid ${P.fail}44`,
      color: P.fail, fontFamily: F.ui, fontSize: 13,
    }}>
      ✕ {message}
    </div>
  );
}
