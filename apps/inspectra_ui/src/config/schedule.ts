// Schedule strings understood by the backend scheduler (qa_ai/product_backend/scheduler.py):
//   none | hourly | daily | nightly | weekdays | every_<N>m (5-720) | every_<N>h (1-168)

export type ScheduleKind = 'none' | 'minutes' | 'hours' | 'hourly' | 'daily' | 'weekdays';

export interface ScheduleChoice {
  kind: ScheduleKind;
  every: number; // the N of every_<N>m / every_<N>h; ignored by the other kinds
}

export const INTERVAL_LIMITS = {
  minutes: { min: 5, max: 720 },
  hours: { min: 1, max: 168 },
} as const;

const INTERVAL_RE = /^every_(\d{1,4})([mh])$/;
const FIXED = new Set(['hourly', 'daily', 'nightly', 'weekdays']);
const NOT_SCHEDULED = new Set(['', 'none', 'manual', 'on_demand', 'ondemand']);

function norm(schedule: unknown): string {
  return typeof schedule === 'string' ? schedule.trim().toLowerCase() : '';
}

export function parseSchedule(schedule: unknown): ScheduleChoice {
  const value = norm(schedule);
  const interval = INTERVAL_RE.exec(value);
  if (interval) {
    return { kind: interval[2] === 'm' ? 'minutes' : 'hours', every: Number(interval[1]) };
  }
  if (value === 'hourly') return { kind: 'hourly', every: 1 };
  if (value === 'daily' || value === 'nightly') return { kind: 'daily', every: 1 };
  if (value === 'weekdays') return { kind: 'weekdays', every: 1 };
  return { kind: 'none', every: 15 };
}

export function buildSchedule(choice: ScheduleChoice): string {
  switch (choice.kind) {
    case 'minutes': return `every_${choice.every}m`;
    case 'hours': return `every_${choice.every}h`;
    case 'hourly': return 'hourly';
    case 'daily': return 'daily';
    case 'weekdays': return 'weekdays';
    default: return 'none';
  }
}

/** A message when the interval is out of range, otherwise null. */
export function validateInterval(choice: ScheduleChoice): string | null {
  if (choice.kind !== 'minutes' && choice.kind !== 'hours') return null;
  const { min, max } = INTERVAL_LIMITS[choice.kind];
  const unit = choice.kind === 'minutes' ? 'minutes' : 'hours';
  if (!Number.isInteger(choice.every) || choice.every < min || choice.every > max) {
    return `Choose a whole number of ${unit} from ${min} to ${max}.`;
  }
  return null;
}

/** True for a schedule the backend can actually run. */
export function isSupportedSchedule(schedule: unknown): boolean {
  const value = norm(schedule);
  if (FIXED.has(value)) return true;
  const interval = INTERVAL_RE.exec(value);
  if (!interval) return false;
  const count = Number(interval[1]);
  const { min, max } = INTERVAL_LIMITS[interval[2] === 'm' ? 'minutes' : 'hours'];
  return count >= min && count <= max;
}

export function isNotScheduled(schedule: unknown): boolean {
  return NOT_SCHEDULED.has(norm(schedule));
}

export function describeSchedule(schedule: unknown, timezone?: string): string {
  const value = norm(schedule);
  if (isNotScheduled(value)) return 'Not scheduled';
  const zone = timezone && timezone !== 'UTC' ? timezone : 'UTC';
  const choice = parseSchedule(value);
  if (!isSupportedSchedule(value)) return typeof schedule === 'string' ? schedule : 'Not scheduled';
  switch (choice.kind) {
    case 'minutes': return `Every ${choice.every} minutes`;
    case 'hours': return choice.every === 1 ? 'Every hour' : `Every ${choice.every} hours`;
    case 'hourly': return 'Every hour';
    case 'daily': return `Every day at 02:00 (${zone})`;
    case 'weekdays': return `Weekdays at 09:00 (${zone})`;
    default: return 'Not scheduled';
  }
}
