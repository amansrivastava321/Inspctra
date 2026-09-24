export const DEMO_READ_ONLY_TOOLTIP = 'Available in your real workspace. Leave demo to get started.';

export function isDemoPath(pathname: string): boolean {
  return /^\/demo(?:\/|$)/.test(pathname);
}
