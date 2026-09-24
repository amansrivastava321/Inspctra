import type { CSSProperties } from 'react';
import { P, STATUS_MAP, type StatusKind } from '../../design/tokens';

interface StatusBadgeProps {
  kind: StatusKind | string;
  small?: boolean;
  style?: CSSProperties;
}

export function StatusBadge({ kind, small, style }: StatusBadgeProps) {
  const entry = STATUS_MAP[kind as StatusKind] ?? { c: P.textMute, s: 'transparent', label: kind.toUpperCase() };
  const size = small ? 5 : 6;
  const fs = small ? 10 : 11;
  const px = small ? 6 : 8;
  const py = small ? 2 : 3;

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: entry.s, border: `1px solid ${entry.c}22`,
      borderRadius: 6, padding: `${py}px ${px}px`,
      fontFamily: "'JetBrains Mono', monospace", fontSize: fs,
      fontWeight: 500, letterSpacing: '0.04em', color: entry.c,
      whiteSpace: 'nowrap', lineHeight: 1, ...style,
    }}>
      <span style={{ width: size, height: size, borderRadius: 99, background: entry.c, flexShrink: 0 }} />
      {entry.label}
    </span>
  );
}

/** Confidence percentage bar */
export function ConfidenceMeter({ value, color, width = 120 }: { value: number; color?: string; width?: number }) {
  const c = color ?? (value >= 80 ? P.pass : value >= 60 ? P.unclear : P.fail);
  return (
    <div style={{ width, height: 4, background: P.cardHi, borderRadius: 99, overflow: 'hidden' }}>
      <div style={{ width: `${value}%`, height: '100%', background: c, borderRadius: 99,
        transition: 'width 0.4s ease' }} />
    </div>
  );
}
