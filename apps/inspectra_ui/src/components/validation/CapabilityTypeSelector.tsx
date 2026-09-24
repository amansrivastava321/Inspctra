import { P } from '../../design/tokens';
import { PreviewBadge } from '../PreviewBadge';
import {
  CAPABILITY_OPTIONS,
  PREVIEW_TOOLTIP,
  capabilityForAction,
} from '../../config/capabilities';

interface CapabilityTypeSelectorProps {
  actionType?: string;
  onSelectAction: (actionType: string) => void;
}

export function CapabilityTypeSelector({ actionType, onSelectAction }: CapabilityTypeSelectorProps) {
  const selected = capabilityForAction(actionType);
  return (
    <div>
      <div style={{ fontSize: 9, color: P.textMute, marginBottom: 6 }}>TEST TYPE</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 6 }}>
        {CAPABILITY_OPTIONS.map(option => (
          <button
            key={option.id}
            type="button"
            aria-label={`${option.label}${option.preview ? ' Preview' : ''}`}
            aria-pressed={!option.preview && selected === option.id}
            disabled={option.preview}
            title={option.preview ? PREVIEW_TOOLTIP : undefined}
            onClick={() => option.defaultAction && onSelectAction(option.defaultAction)}
            style={{
              minHeight: 34,
              padding: '6px 8px',
              borderRadius: 6,
              border: `1px solid ${!option.preview && selected === option.id ? P.accent : P.border}`,
              background: !option.preview && selected === option.id ? P.accentSoft : P.cardHi,
              color: option.preview ? P.textMute : P.textDim,
              cursor: option.preview ? 'not-allowed' : 'pointer',
              opacity: option.preview ? 0.72 : 1,
              fontSize: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 5,
              textAlign: 'left',
            }}
          >
            <span>{option.label}</span>
            {option.preview && <PreviewBadge />}
          </button>
        ))}
      </div>
    </div>
  );
}

