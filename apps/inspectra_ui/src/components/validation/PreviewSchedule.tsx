import { P, F } from '../../design/tokens';
import { isPreviewSchedule, SCHEDULE_PREVIEW_TOOLTIP } from '../../config/capabilities';
import { PreviewBadge } from '../PreviewBadge';
import { describeSchedule, isSupportedSchedule } from '../../config/schedule';

export function PreviewSchedule({ schedule, timezone }: { schedule?: string; timezone?: string }) {
  const label = isSupportedSchedule(schedule) ? describeSchedule(schedule, timezone) : schedule || '—';
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

