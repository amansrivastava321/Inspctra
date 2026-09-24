import { P, READINESS_BAND, STATUS_MAP } from '../../design/tokens';

interface ReadinessScoreProps {
  score?: number;  // undefined = no data — shows neutral "—"
  subtitle?: string;
  compact?: boolean;
}

export function ReadinessScore({ score, subtitle, compact }: ReadinessScoreProps) {
  // No data — neutral placeholder, no fake score
  if (score === undefined || score === null) {
    return (
      <div style={{ padding: compact ? '10px 12px' : '14px 16px' }}>
        <div style={{ fontSize: 10, color: P.textMute, letterSpacing: '0.08em',
          textTransform: 'uppercase', fontFamily: "'JetBrains Mono', monospace", marginBottom: 6 }}>
          ENV READINESS
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
          <span style={{ fontSize: compact ? 22 : 28, fontWeight: 700, color: P.textMute, lineHeight: 1 }}>—</span>
          <span style={{ fontSize: 12, color: P.textFaint }}>/ 100</span>
        </div>
        <div style={{ height: 3, background: P.cardHi, borderRadius: 99 }} />
        {subtitle && <div style={{ fontSize: 11, color: P.textMute, marginTop: 4 }}>{subtitle}</div>}
      </div>
    );
  }

  const band = READINESS_BAND(score);
  const { c, label } = STATUS_MAP[band];

  return (
    <div style={{ padding: compact ? '10px 12px' : '14px 16px' }}>
      <div style={{ fontSize: 10, color: P.textMute, letterSpacing: '0.08em', textTransform: 'uppercase',
        fontFamily: "'JetBrains Mono', monospace", marginBottom: 6 }}>
        ENV READINESS
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
        <span style={{ fontSize: compact ? 22 : 28, fontWeight: 700, color: P.text, lineHeight: 1,
          fontVariantNumeric: 'tabular-nums' }}>
          {score}
        </span>
        <span style={{ fontSize: 12, color: P.textMute }}>/ 100</span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          background: STATUS_MAP[band].s, border: `1px solid ${c}22`,
          borderRadius: 5, padding: '2px 6px', marginLeft: 4,
          fontSize: 10, fontWeight: 600, color: c,
          fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.04em',
        }}>
          <span style={{ width: 5, height: 5, borderRadius: 99, background: c }} />
          {label}
        </span>
      </div>
      <div style={{ height: 3, background: P.cardHi, borderRadius: 99, overflow: 'hidden', marginBottom: subtitle ? 6 : 0 }}>
        <div style={{
          width: `${score}%`, height: '100%', borderRadius: 99,
          background: `linear-gradient(90deg, ${c}, ${c}aa)`,
          transition: 'width 0.6s ease',
        }} />
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: P.textMute, marginTop: 4 }}>{subtitle}</div>
      )}
    </div>
  );
}
