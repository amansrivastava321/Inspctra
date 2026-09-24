import { P, F } from '../../design/tokens';
import { isPreviewSchedule, SCHEDULE_PREVIEW_TOOLTIP } from '../../config/capabilities';
import { PreviewBadge } from '../PreviewBadge';

export function PreviewSchedule({ schedule }: { schedule?: string }) {
  const label = schedule || '—';
  const preview = isPreviewSchedule(schedule);
  return (
    <div
      title={preview ? SCHEDULE_PREVIEW_TOOLTIP : undefined}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap' }}
    >
      <span style={{ fontSize: 12, color: P.textMute, fontFamily: F.mono }}>{label}</span>
      {preview && <PreviewBadge title={SCHEDULE_PREVIEW_TOOLTIP} />}
    </div>
  );
}

