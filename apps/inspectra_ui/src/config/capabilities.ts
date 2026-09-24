export const PREVIEW_TOOLTIP = 'This feature is planned for a future release. Runs will be unavailable.';
export const SCHEDULE_PREVIEW_TOOLTIP = 'Scheduling will be available in a future release.';
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
  { id: 'mobile', label: 'Mobile Testing', preview: true },
  { id: 'desktop', label: 'Desktop Testing', preview: true },
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
  return ['mobile', 'android', 'ios', 'desktop', 'native_macos', 'native_windows', 'native_linux'].includes(value);
}

// The scheduler is not an MVP execution path yet; only explicitly on-demand
// packs are executable without a Preview label.
const LIVE_SCHEDULES = new Set(['manual', 'none', 'on_demand', 'ondemand']);

export function isPreviewSchedule(schedule: unknown): boolean {
  const value = normalize(schedule);
  return value.length > 0 && !LIVE_SCHEDULES.has(value);
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
