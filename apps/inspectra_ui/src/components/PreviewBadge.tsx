import type { CSSProperties } from 'react';
import { F, P } from '../design/tokens';
import { PREVIEW_TOOLTIP } from '../config/capabilities';

interface PreviewBadgeProps {
  title?: string;
  style?: CSSProperties;
}

export function PreviewBadge({ title = PREVIEW_TOOLTIP, style }: PreviewBadgeProps) {
  return (
    <span
      title={title}
      data-testid="preview-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        flexShrink: 0,
        whiteSpace: 'nowrap',
        padding: '2px 6px',
        borderRadius: 999,
        border: `1px solid ${P.textMute}55`,
        background: `${P.textMute}18`,
        color: P.textMute,
        fontFamily: F.mono,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        ...style,
      }}
    >
      Preview
    </span>
  );
}

