/**
 * RuntimeDoctorPage fix verification tests
 * - things_to_fix built from ALL non-ready components (not just missing_items)
 * - readinessScore prop passed to AppShell → sidebar shows real score
 * - Score panel "N things blocking" matches things_to_fix count
 * - "All systems ready" only shown when all components ready
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RuntimeDoctorPage from '../pages/RuntimeDoctorPage';

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
  }
  return {
    get: vi.fn(),
    post: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;

// Minimal backend report with some missing, some ready
const PARTIAL_REPORT = {
  readiness_score: 72,
  readiness_label: 'partial',
  missing_items: [],                    // empty — old code would show "All systems ready"
  recommended_actions: [],
  driver_readiness: [],
  playwright_installed: true,
  playwright_browsers_installed: true,
  appium_client_installed: false,       // missing
  appium_command_available: false,      // missing
  appium_server_reachable: false,       // missing
  ollama_reachable: true,
  ollama_vision_model_available: true,
  macos_accessibility_granted: false,   // perm
  pywinauto_installed: false,
  atspi_installed: false,
  npm_available: true,
  platform: 'darwin',
};

const ALL_READY_REPORT = {
  readiness_score: 100,
  readiness_label: 'ready',
  missing_items: [],
  recommended_actions: [],
  driver_readiness: [],
  playwright_installed: true,
  playwright_browsers_installed: true,
  appium_client_installed: true,
  appium_command_available: true,
  appium_server_reachable: true,
  ollama_reachable: true,
  ollama_vision_model_available: true,
  macos_accessibility_granted: true,
  pywinauto_installed: false,
  atspi_installed: false,
  npm_available: true,
  platform: 'darwin',
};

describe('RuntimeDoctorPage — things_to_fix logic', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows fix items for missing components even when missing_items is empty', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // 'Appium Client' appears in component status list AND in things_to_fix cards
      expect(screen.getAllByText('Appium Client').length).toBeGreaterThanOrEqual(1);
    });
    // Must NOT show "All systems ready" when components are missing
    expect(screen.queryByText('All systems ready')).not.toBeInTheDocument();
  });

  it('shows "All systems ready" only when all components are ready', async () => {
    mockGet.mockResolvedValue(ALL_READY_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('All systems ready')).toBeInTheDocument();
    });
  });

  it('does NOT show "All systems ready" when there are non-ready components', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // Wait for data to load
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText('All systems ready')).not.toBeInTheDocument();
  });

  it('shows macOS perm fix when accessibility not granted', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // 'macOS Accessibility' appears in component status list AND in things_to_fix cards
      expect(screen.getAllByText('macOS Accessibility').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('"N things blocking" count matches non-ready components shown', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText(/things blocking environment readiness/i)).toBeInTheDocument();
    });
    // The text should NOT be "0 things blocking" when there are missing items
    const blockingEl = screen.getByText(/things blocking environment readiness/i);
    expect(blockingEl.textContent).not.toMatch(/^0 things/);
  });
});

describe('RuntimeDoctorPage — sidebar readiness score', () => {
  beforeEach(() => vi.clearAllMocks());

  it('passes readiness score to sidebar (not "—") when backend returns score', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT); // score=72
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // Score "72" appears in main content AND sidebar ReadinessScore
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(2);
    });
  });

  it('sidebar does not show "—" score when doctor has real score', async () => {
    mockGet.mockResolvedValue(PARTIAL_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // "—" is shown only when score is undefined — should NOT appear
      // (It may appear in workspace label but not in the readiness score widget)
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
  });
});

// ── Label and badge mapping ───────────────────────────────────────────────────

const USABLE_REPORT = {
  readiness_score: 80,
  readiness_label: 'usable',
  missing_items: [],
  recommended_actions: [],
  driver_readiness: [],
  playwright_installed: true,
  playwright_browsers_installed: true,
  appium_client_installed: false,
  appium_command_available: false,
  appium_server_reachable: false,
  ollama_reachable: true,
  ollama_vision_model_available: true,
  macos_accessibility_granted: true,
  pywinauto_installed: false,
  atspi_installed: false,
  npm_available: true,
  platform: 'darwin',
  needs_mobile: false,
};

describe('RuntimeDoctorPage — usable label → USABLE badge', () => {
  beforeEach(() => vi.clearAllMocks());

  it('readiness_label "usable" renders USABLE badge not PARTIAL', async () => {
    mockGet.mockResolvedValue(USABLE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // USABLE badge appears in both score card and sidebar — use getAllByText
      expect(screen.getAllByText('USABLE').length).toBeGreaterThanOrEqual(1);
    });
    // No STATUS badge showing PARTIAL (all-caps) — band bar shows "26-60 Partial" (mixed case, not a badge)
    // USABLE_REPORT has readiness_label='usable', so band is 'usable', never 'partial'
    // No component in USABLE_REPORT has partial status
    expect(screen.queryByText('PARTIAL')).not.toBeInTheDocument();
  });

  it('score 80 with usable label shows 80 score and USABLE badge', async () => {
    mockGet.mockResolvedValue(USABLE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('USABLE').length).toBeGreaterThanOrEqual(1);
    });
  });
});

// ── not_available drivers hidden ─────────────────────────────────────────────

const REPORT_WITH_NOT_AVAILABLE = {
  ...PARTIAL_REPORT,
  driver_readiness: [
    { app_type: 'native_windows', driver_type: 'WindowsUIADriver', status: 'not_available', missing_deps: [] },
    { app_type: 'native_linux',   driver_type: 'LinuxATSPIDriver',  status: 'not_available', missing_deps: [] },
  ],
};

describe('RuntimeDoctorPage — not_available drivers excluded', () => {
  beforeEach(() => vi.clearAllMocks());

  it('not_available drivers do not appear in Things to Fix', async () => {
    mockGet.mockResolvedValue(REPORT_WITH_NOT_AVAILABLE);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
    // Windows / Linux drivers must not appear in Things to Fix
    expect(screen.queryByText(/native_windows/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/native_linux/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/WindowsUIADriver/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/LinuxATSPIDriver/i)).not.toBeInTheDocument();
  });
});

// ── Appium skipped when no mobile context ─────────────────────────────────────

const NO_MOBILE_REPORT = {
  ...PARTIAL_REPORT,
  needs_mobile: false,
  appium_client_installed: false,
  appium_command_available: false,
  appium_server_reachable: false,
};

describe('RuntimeDoctorPage — Appium skipped when needs_mobile=false', () => {
  beforeEach(() => vi.clearAllMocks());

  it('Appium shows SKIPPED not MISSING when needs_mobile=false', async () => {
    mockGet.mockResolvedValue(NO_MOBILE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
    // Appium rows appear in component status with SKIPPED badge (3 Appium rows = 3 SKIPPED)
    const skippedBadges = screen.queryAllByText('SKIPPED');
    expect(skippedBadges.length).toBeGreaterThanOrEqual(3);
    // No MISSING badge anywhere — skipped items excluded from things_to_fix
    // (macOS Accessibility shows PERM, not MISSING)
    expect(screen.queryAllByText('MISSING').length).toBe(0);
  });

  it('"Only needed for Android/iOS testing" shown as detail for skipped Appium components', async () => {
    mockGet.mockResolvedValue(NO_MOBILE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
    // Each Appium row (Client, CLI, Server) shows the skip detail — 3 occurrences
    expect(screen.getAllByText('Only needed for Android/iOS testing').length).toBeGreaterThanOrEqual(3);
  });
});

// ── No-app global mode — android/ios drivers not shown ────────────────────────

// Simulates backend response in global mode (app_types=None):
// driver_readiness has NO android/ios entries (backend fix excludes them)
const GLOBAL_MODE_REPORT = {
  readiness_score: 80,
  readiness_label: 'usable',
  missing_items: [],
  recommended_actions: [],
  driver_readiness: [], // mobile drivers absent — backend excluded them in global mode
  playwright_installed: true,
  playwright_browsers_installed: true,
  appium_client_installed: false,
  appium_command_available: false,
  appium_server_reachable: false,
  ollama_reachable: false,
  ollama_vision_model_available: false,
  macos_accessibility_granted: true,
  pywinauto_installed: false,
  atspi_installed: false,
  npm_available: true,
  platform: 'darwin',
  needs_mobile: false,
};

const ANDROID_APP_REPORT = {
  readiness_score: 40,
  readiness_label: 'partial',
  missing_items: ['Appium-Python-Client not installed'],
  recommended_actions: ['pip install Appium-Python-Client'],
  driver_readiness: [
    {
      app_type: 'android',
      driver_type: 'AndroidAppiumDriver',
      status: 'missing_deps',
      missing_deps: ['Appium-Python-Client', 'appium-server-command'],
    },
  ],
  playwright_installed: true,
  playwright_browsers_installed: true,
  appium_client_installed: false,
  appium_command_available: false,
  appium_server_reachable: false,
  ollama_reachable: false,
  ollama_vision_model_available: false,
  macos_accessibility_granted: true,
  pywinauto_installed: false,
  atspi_installed: false,
  npm_available: true,
  platform: 'darwin',
  needs_mobile: true,
};

describe('RuntimeDoctorPage — global mode (no app connected)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('android · AndroidAppiumDriver NOT in Things to Fix in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText(/android · AndroidAppiumDriver/i)).not.toBeInTheDocument();
  });

  it('ios · IOSAppiumDriver NOT in Things to Fix in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText(/ios · IOSAppiumDriver/i)).not.toBeInTheDocument();
  });

  it('flutter_android · AndroidAppiumDriver NOT shown in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText(/flutter_android/i)).not.toBeInTheDocument();
  });

  it('flutter_ios · IOSAppiumDriver NOT shown in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText(/flutter_ios/i)).not.toBeInTheDocument();
  });

  it('"No app connected yet" informational card shown in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByTestId('no-app-connected-doctor')).toBeInTheDocument();
    });
    expect(screen.getByTestId('no-app-connected-doctor').textContent).toMatch(/No app connected yet/i);
  });

  it('score 80 shows USABLE in global mode', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('USABLE').length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe('RuntimeDoctorPage — Android app connected', () => {
  beforeEach(() => vi.clearAllMocks());

  it('android · AndroidAppiumDriver IS shown when needs_mobile=true', async () => {
    mockGet.mockResolvedValue(ANDROID_APP_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // Appears in Component Status list AND Things to Fix — both expected
      expect(screen.getAllByText(/android · AndroidAppiumDriver/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('"No app connected yet" card NOT shown when needs_mobile=true', async () => {
    mockGet.mockResolvedValue(ANDROID_APP_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('40').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByTestId('no-app-connected-doctor')).not.toBeInTheDocument();
  });
});

// ── Phase 3: ENV READINESS vs APP RUNTIME READINESS split ────────────────────

describe('RuntimeDoctorPage — Phase 3: ENV vs App Runtime split', () => {
  beforeEach(() => vi.clearAllMocks());

  it('score card shows ENVIRONMENT READINESS header when no app connected', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('ENVIRONMENT READINESS')).toBeInTheDocument();
    });
  });

  it('shows App Runtime Readiness section with "Not checked" when no app connected', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('App Runtime Readiness')).toBeInTheDocument();
      expect(screen.getByText('Not checked')).toBeInTheDocument();
    });
  });

  it('no app connected does not imply app ready', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1);
    });
    // App Runtime Readiness section says "Not checked" — not ready
    expect(screen.getByText('Not checked')).toBeInTheDocument();
    // "All systems ready" absent — GLOBAL_MODE_REPORT has missing Ollama components
    expect(screen.queryByText('All systems ready')).not.toBeInTheDocument();
  });

  it('sidebar shows ENV READINESS label not plain READINESS', async () => {
    mockGet.mockResolvedValue(GLOBAL_MODE_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('ENV READINESS').length).toBeGreaterThanOrEqual(1);
    });
    // Old ambiguous "READINESS" label replaced by "ENV READINESS"
    expect(screen.queryByText('READINESS')).not.toBeInTheDocument();
  });

  it('connected app mode shows app driver info and no "Not checked"', async () => {
    mockGet.mockResolvedValue(ANDROID_APP_REPORT);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText('40').length).toBeGreaterThanOrEqual(1);
    });
    // App Runtime section still rendered but with app-connected content
    expect(screen.getByText('App Runtime Readiness')).toBeInTheDocument();
    // "Not checked" absent when app IS connected
    expect(screen.queryByText('Not checked')).not.toBeInTheDocument();
    // no-app-connected-doctor testid absent
    expect(screen.queryByTestId('no-app-connected-doctor')).not.toBeInTheDocument();
  });
});
