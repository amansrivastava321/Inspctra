// Desktop (Mac, Windows) and mobile (Android, iOS) app testing. Mirrors qa_ai/native_execution.

export type NativePlatform = 'native_macos' | 'native_windows' | 'android' | 'ios';

export const NATIVE_PLATFORMS: readonly NativePlatform[] = ['native_macos', 'native_windows', 'android', 'ios'];

export function isNativeAppType(appType: unknown): appType is NativePlatform {
  return typeof appType === 'string' && (NATIVE_PLATFORMS as readonly string[]).includes(appType);
}

export interface NativeFieldHints {
  identifierLabel: string;
  identifierPlaceholder: string;
  pathLabel: string;
  pathPlaceholder: string;
  deviceLabel?: string;
  devicePlaceholder?: string;
}

export const NATIVE_FIELDS: Record<NativePlatform, NativeFieldHints> = {
  native_macos: {
    identifierLabel: 'App name or bundle id',
    identifierPlaceholder: 'TextEdit or com.apple.TextEdit',
    pathLabel: 'App file (optional)',
    pathPlaceholder: '/Applications/MyApp.app',
  },
  native_windows: {
    identifierLabel: 'Program to start',
    identifierPlaceholder: 'notepad.exe',
    pathLabel: 'Full path to the .exe (optional)',
    pathPlaceholder: 'C:\\Program Files\\MyApp\\MyApp.exe',
    deviceLabel: 'Window title (optional)',
    devicePlaceholder: 'Only if it differs from the program name',
  },
  android: {
    identifierLabel: 'Package name',
    identifierPlaceholder: 'com.example.app',
    pathLabel: 'APK to install (optional)',
    pathPlaceholder: '/builds/app-debug.apk',
    deviceLabel: 'Emulator (AVD) or device serial (optional)',
    devicePlaceholder: 'Pixel_8_API_35',
  },
  ios: {
    identifierLabel: 'Bundle id',
    identifierPlaceholder: 'com.example.app',
    pathLabel: 'Simulator build (.app) to install (optional)',
    pathPlaceholder: '/builds/MyApp.app',
    deviceLabel: 'Simulator name (optional)',
    devicePlaceholder: 'iPhone 15',
  },
};

export const APP_ACTIONS = [
  'app_launch', 'app_tap', 'app_type', 'app_press', 'app_assert_text', 'app_wait_for_text', 'app_screenshot', 'app_close',
] as const;

export function isAppAction(action: unknown): boolean {
  return typeof action === 'string' && (APP_ACTIONS as readonly string[]).includes(action);
}

const APP_TARGET: Record<string, [string, string]> = {
  app_launch: ['APP (OPTIONAL, DEFAULTS TO THE TARGET\'S)', 'e.g. com.example.app'],
  app_tap: ['ON-SCREEN LABEL', 'e.g. Sign in'],
  app_type: ['FIELD LABEL (OPTIONAL)', 'e.g. Email'],
};

const APP_VALUE: Record<string, [string, string]> = {
  app_type: ['TEXT TO TYPE', 'e.g. me@example.com'],
  app_press: ['KEY', 'enter, tab, escape, back, home'],
  app_assert_text: ['TEXT THAT MUST BE ON SCREEN', 'e.g. Welcome back'],
  app_wait_for_text: ['TEXT TO WAIT FOR', 'e.g. Loaded'],
};

export const appNeedsTarget = (action: string) => action in APP_TARGET;
export const appNeedsValue = (action: string) => action in APP_VALUE;
export const appTargetLabel = (action: string) => APP_TARGET[action]?.[0];
export const appTargetPlaceholder = (action: string) => APP_TARGET[action]?.[1];
export const appValueLabel = (action: string) => APP_VALUE[action]?.[0];
export const appValuePlaceholder = (action: string) => APP_VALUE[action]?.[1];
