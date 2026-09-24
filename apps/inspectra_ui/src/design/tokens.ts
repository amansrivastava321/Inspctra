/** Design tokens — premium dark SaaS. Matches Inspectra PDF exactly. */

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
  textMute:    '#878b96',
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
  skippedSoft: 'rgba(107,110,120,0.12)',
  // Shadow / glow
  shadow:      '0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 32px -16px rgba(0,0,0,0.7)',
  shadowCard:  '0 0 0 1px rgba(255,255,255,0.06), 0 4px 16px -8px rgba(0,0,0,0.5)',
  glow:        '0 0 0 1px rgba(91,140,255,0.20), 0 0 24px -8px rgba(91,140,255,0.24)',
} as const;

export const F = {
  ui:      "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono:    "'JetBrains Mono', 'Geist Mono', monospace",
  display: "'Inter', -apple-system, sans-serif",
} as const;

export type StatusKind =
  | 'pass' | 'fail' | 'unclear' | 'blocked' | 'skipped' | 'dry_run'
  | 'running' | 'ready' | 'missing' | 'perm' | 'starting'
  | 'strong' | 'medium' | 'weak' | 'partial' | 'usable';

export const STATUS_MAP: Record<StatusKind, { c: string; s: string; label: string }> = {
  pass:    { c: P.pass,    s: P.passSoft,    label: 'PASS' },
  fail:    { c: P.fail,    s: P.failSoft,    label: 'FAIL' },
  unclear: { c: P.unclear, s: P.unclearSoft, label: 'UNCLEAR' },
  blocked: { c: P.blocked, s: P.blockedSoft, label: 'BLOCKED' },
  skipped: { c: P.skipped, s: P.skippedSoft, label: 'SKIPPED' },
  dry_run: { c: P.skipped, s: P.skippedSoft, label: 'DRY RUN' },
  running: { c: P.accent,  s: P.accentSoft,  label: 'LIVE' },
  ready:   { c: P.pass,    s: P.passSoft,    label: 'READY' },
  missing: { c: P.unclear, s: P.unclearSoft, label: 'MISSING' },
  perm:    { c: P.accent,  s: P.accentSoft,  label: 'PERMISSION' },
  starting:{ c: P.accent,  s: P.accentSoft,  label: 'STARTING' },
  strong:  { c: P.pass,    s: P.passSoft,    label: 'STRONG' },
  medium:  { c: P.unclear, s: P.unclearSoft, label: 'MEDIUM' },
  weak:    { c: P.fail,    s: P.failSoft,    label: 'WEAK' },
  partial: { c: P.unclear, s: P.unclearSoft, label: 'PARTIAL' },
  usable:  { c: P.pass,    s: P.passSoft,    label: 'USABLE' },
};

export const READINESS_BAND = (score: number): StatusKind => {
  if (score >= 86) return 'ready';
  if (score >= 61) return 'usable';
  if (score >= 26) return 'partial';
  return 'blocked';
};
