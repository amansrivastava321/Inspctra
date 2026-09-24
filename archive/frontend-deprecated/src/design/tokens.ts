/** Design tokens — match premium-core.jsx exactly. Dark mode first. */

export const P = {
  // Surfaces
  bg:          '#08090b',
  surface:     '#0e0f12',
  card:        '#121317',
  cardHi:      '#16181d',
  cardHover:   '#1a1c22',
  glass:       'rgba(22,24,29,0.72)',
  // Borders
  border:      'rgba(255,255,255,0.06)',
  borderHi:    'rgba(255,255,255,0.10)',
  borderFocus: 'rgba(91,140,255,0.45)',
  // Text
  text:        '#ececf1',
  textDim:     '#a0a3ad',
  textMute:    '#6b6e78',
  textFaint:   '#494c55',
  // Accent (signature indigo-blue)
  accent:      '#5b8cff',
  accentSoft:  'rgba(91,140,255,0.14)',
  accentGlow:  'rgba(91,140,255,0.32)',
  // Status
  pass:        '#34d399',
  passSoft:    'rgba(52,211,153,0.12)',
  fail:        '#f87171',
  failSoft:    'rgba(248,113,113,0.12)',
  unclear:     '#fbbf24',
  unclearSoft: 'rgba(251,191,36,0.12)',
  blocked:     '#94a3b8',
  blockedSoft: 'rgba(148,163,184,0.12)',
  skipped:     '#6b6e78',
  // Shadow
  shadow:      '0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 32px -16px rgba(0,0,0,0.7)',
} as const;

export const F = {
  ui:      "'Geist', 'Inter', -apple-system, sans-serif",
  mono:    "'Geist Mono', 'JetBrains Mono', monospace",
  display: "'Geist', 'Inter', sans-serif",
} as const;

export type StatusKind =
  | 'pass' | 'fail' | 'unclear' | 'blocked' | 'skipped'
  | 'running' | 'ready' | 'missing' | 'perm' | 'starting'
  | 'strong' | 'medium' | 'weak';

export const STATUS_MAP: Record<StatusKind, { c: string; s: string; label: string }> = {
  pass:     { c: P.pass,    s: P.passSoft,    label: 'PASS' },
  fail:     { c: P.fail,    s: P.failSoft,    label: 'FAIL' },
  unclear:  { c: P.unclear, s: P.unclearSoft, label: 'UNCLEAR' },
  blocked:  { c: P.blocked, s: P.blockedSoft, label: 'BLOCKED' },
  skipped:  { c: P.skipped, s: 'transparent', label: 'SKIPPED' },
  running:  { c: P.accent,  s: P.accentSoft,  label: 'RUNNING' },
  ready:    { c: P.pass,    s: P.passSoft,    label: 'READY' },
  missing:  { c: P.unclear, s: P.unclearSoft, label: 'MISSING' },
  perm:     { c: P.accent,  s: P.accentSoft,  label: 'PERMISSION' },
  starting: { c: P.accent,  s: P.accentSoft,  label: 'STARTING' },
  strong:   { c: P.pass,    s: P.passSoft,    label: 'STRONG' },
  medium:   { c: P.unclear, s: P.unclearSoft, label: 'MEDIUM' },
  weak:     { c: P.fail,    s: P.failSoft,    label: 'WEAK' },
};
