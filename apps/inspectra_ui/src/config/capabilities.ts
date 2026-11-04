import { isNotScheduled, isSupportedSchedule } from './schedule';

export const PREVIEW_TOOLTIP = 'This feature is planned for a future release. Runs will be unavailable.';
export const SCHEDULE_PREVIEW_TOOLTIP = 'This schedule is not supported yet. Use hourly, daily, weekdays or an interval.';
export const PREVIEW_RUN_TOOLTIP = 'Contains preview steps. Preview capabilities cannot be run yet.';

export type CapabilityId =
  | 'web'
  | 'api'
  | 'manual'
  | 'accessibility'
  | 'security'
  | 'performance'
  | 'visual'
  | 'mobile'
  | 'desktop'
  | 'distributed'
  | 'chaos'
  | 'cicd'
  | 'enterprise';

export interface CapabilityOption {
  id: CapabilityId;
  label: string;
  preview: boolean;
  defaultAction?: string;
}

export const CAPABILITY_OPTIONS: readonly CapabilityOption[] = [
  { id: 'web', label: 'Web Test', preview: false, defaultAction: 'navigate' },
  { id: 'api', label: 'API Test', preview: false, defaultAction: 'api_request' },
  // Manual runs collect a human verdict for the same concrete step definition.
  { id: 'manual', label: 'Manual Test', preview: false, defaultAction: 'navigate' },
  { id: 'accessibility', label: 'Accessibility', preview: false, defaultAction: 'check_accessibility' },
  { id: 'security', label: 'Security Check', preview: false, defaultAction: 'passive_security_check' },
  { id: 'performance', label: 'Performance Check', preview: false, defaultAction: 'measure_page_load' },
  { id: 'visual', label: 'Visual Regression', preview: false, defaultAction: 'assert_visual_match' },
  { id: 'mobile', label: 'Mobile App Test', preview: false, defaultAction: 'app_launch' },
  { id: 'desktop', label: 'Desktop App Test', preview: false, defaultAction: 'app_launch' },
  { id: 'distributed', label: 'Distributed Execution', preview: true },
  { id: 'chaos', label: 'Chaos Engineering', preview: true },
  { id: 'cicd', label: 'CI/CD Integration', preview: true },
  { id: 'enterprise', label: 'Enterprise Governance', preview: true },
] as const;

const PREVIEW_MARKERS = [
  'mobile', 'android', 'ios', 'appium',
  'desktop', 'native', 'macos', 'windows',
  'distributed', 'fan_out', 'chaos',
  'ci_', 'cicd', 'pipeline',
  'enterprise', 'governance',
] as const;

const normalize = (value: unknown) => String(value ?? '').trim().toLowerCase().replace(/[\s/-]+/g, '_');

export function isPreviewAction(actionType: unknown): boolean {
  const action = normalize(actionType);
  return action.length > 0 && PREVIEW_MARKERS.some(marker => action.includes(marker));
}

export function isPreviewAppType(appType: unknown): boolean {
  const value = normalize(appType);
  // Mac, Windows, Android and iOS apps are tested through qa_ai/native_execution; generic "mobile"/"desktop"
  // labels and Linux desktop apps are not runnable yet.
  return ['mobile', 'desktop', 'native_linux'].includes(value);
}

// The scheduler runs hourly, daily, nightly, weekdays and every_<N>m / every_<N>h packs. Only free-text
// schedules it cannot honour (for example "on PR") are still shown as Preview.
export function isPreviewSchedule(schedule: unknown): boolean {
  return !isNotScheduled(schedule) && !isSupportedSchedule(schedule);
}

function objectContainsPreview(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const record = value as Record<string, unknown>;
  if (isPreviewAction(record.action_type)) return true;
  for (const key of ['capability', 'test_type', 'flow_name', 'platform', 'app_type']) {
    if (isPreviewAction(record[key])) return true;
  }
  if (Array.isArray(record.tags) && record.tags.some(isPreviewAction)) return true;
  return false;
}

export function isPreviewStep(step: unknown): boolean {
  return objectContainsPreview(step);
}

export function testCaseContainsPreview(testCase: unknown): boolean {
  if (!testCase || typeof testCase !== 'object') return false;
  if (objectContainsPreview(testCase)) return true;
  const record = testCase as Record<string, unknown>;
  return Array.isArray(record.test_steps) && record.test_steps.some(isPreviewStep);
}

export function hasPreviewSteps(packSteps: readonly unknown[] = [], testCases: readonly unknown[] = []): boolean {
  return packSteps.some(isPreviewStep) || testCases.some(testCaseContainsPreview);
}

export function capabilityForAction(actionType: unknown): CapabilityId {
  const action = normalize(actionType);
  if (action.startsWith('api_') || ['assert_status', 'assert_json_path', 'assert_header_contains', 'assert_body_contains', 'assert_response_time_under'].includes(action)) return 'api';
  if (action.includes('accessibility') || action.includes('a11y')) return 'accessibility';
  if (action.includes('security') || action.includes('cookie_flags')) return 'security';
  if (action.includes('performance') || action.includes('response_time') || action.includes('page_load')) return 'performance';
  if (action.includes('visual')) return 'visual';
  return 'web';
}
