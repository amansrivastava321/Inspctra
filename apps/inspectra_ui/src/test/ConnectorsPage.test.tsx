/**
 * ConnectorsPage tests
 *
 * 1.  No apps → empty state "No app connected yet"
 * 2.  No apps → does NOT show "4 / 4 ready" or "4/4"
 * 3.  No apps → does NOT render connector map (radial map removed)
 * 4.  Global dependencies section always shown
 * 5.  Appium client ready + server/CLI missing → PARTIAL badge
 * 6.  Appium all ready (client + CLI + server) → READY badge, no warning
 * 7.  App exists → shows app name in App Runtime Connectors section
 * 8.  No apps → does NOT render connector-map node elements
 * 9.  Re-check button calls /connectors endpoint again
 * 10. Connect app CTA navigates to /projects/new
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ConnectorsPage from '../pages/ConnectorsPage';

// ── Mock api/client ───────────────────────────────────────────────────────────

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

// ── Mock react-router-dom navigate ────────────────────────────────────────────

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { get } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;

// ── Test fixtures ─────────────────────────────────────────────────────────────

const CONNECTORS_ALL_READY = {
  checked_at: '2026-05-27T00:00:00Z',
  provenance: 'REAL_EXECUTION',
  connectors: [
    { connector_id: 'playwright', connector_type: 'browser', ready: true, partial: false, check_type: 'client_library', details: 'playwright package importable' },
    {
      connector_id: 'appium', connector_type: 'mobile', ready: true, partial: false, check_type: 'composite',
      details: 'Appium ready — client, CLI, and server all operational',
      sub_checks: [
        { id: 'appium_client', name: 'Client library', ready: true, check_type: 'client_library', details: 'appium-python-client installed' },
        { id: 'appium_cli', name: 'CLI (appium command)', ready: true, check_type: 'command_available', details: '`appium` command found in PATH' },
        { id: 'appium_server', name: 'Server (localhost:4723)', ready: true, check_type: 'server_reachable', details: 'Appium server reachable at localhost:4723' },
      ],
    },
    { connector_id: 'sqlite', connector_type: 'database', ready: true, partial: false, check_type: 'client_library', details: 'sqlite3 (built-in)' },
    { connector_id: 'ollama', connector_type: 'ai_vision', ready: true, partial: false, check_type: 'server_reachable', details: 'Ollama reachable at localhost:11434' },
  ],
  total: 4, ready: 4, partial: 0,
};

const CONNECTORS_APPIUM_PARTIAL = {
  checked_at: '2026-05-27T00:00:00Z',
  provenance: 'REAL_EXECUTION',
  connectors: [
    { connector_id: 'playwright', connector_type: 'browser', ready: true, partial: false, check_type: 'client_library', details: 'playwright package importable' },
    {
      connector_id: 'appium', connector_type: 'mobile', ready: false, partial: true, check_type: 'composite',
      details: 'Appium partial — client installed but missing: CLI (appium command), Server (localhost:4723)',
      sub_checks: [
        { id: 'appium_client', name: 'Client library', ready: true, check_type: 'client_library', details: 'appium-python-client installed' },
        { id: 'appium_cli', name: 'CLI (appium command)', ready: false, check_type: 'command_available', details: '`appium` command not found — run: npm install -g appium' },
        { id: 'appium_server', name: 'Server (localhost:4723)', ready: false, check_type: 'server_reachable', details: 'Appium server not reachable — start with: appium server' },
      ],
    },
    { connector_id: 'sqlite', connector_type: 'database', ready: true, partial: false, check_type: 'client_library', details: 'sqlite3 (built-in)' },
    { connector_id: 'ollama', connector_type: 'ai_vision', ready: false, partial: false, check_type: 'server_reachable', details: 'Ollama not reachable' },
  ],
  total: 4, ready: 2, partial: 1,
};

const NO_APPS: never[] = [];
const ONE_APP = [{ id: 'app1', name: 'MyApp', app_type: 'web', project_id: 'p1', tags: [], created_at: '', updated_at: '', provenance: 'REAL_EXECUTION' }];

// ── Render helper ─────────────────────────────────────────────────────────────

function renderPage() {
  return render(<MemoryRouter><ConnectorsPage /></MemoryRouter>);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ConnectorsPage — no app connected', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_ALL_READY);
      if (path === '/apps') return Promise.resolve(NO_APPS);
      return Promise.resolve([]);
    });
  });

  it('1. shows "No app connected yet" when no apps', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No app connected yet')).toBeInTheDocument();
    });
  });

  it('2. does NOT show "4 / 4 ready" or claim all connectors ready as app state', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No app connected yet')).toBeInTheDocument();
    });
    // The subtitle may say "4 / 4 ready — global runtime checks" but must NOT
    // present "4 / 4 ready" as app-connector status — the no-app state is explicit
    const noAppEl = screen.getByTestId('no-app-state');
    expect(noAppEl).toBeInTheDocument();
    // "4 / 4 ready" must not appear inside the no-app section
    expect(noAppEl.textContent).not.toMatch(/4\s*\/\s*4\s*ready/);
  });

  it('3. does NOT render connector map elements when no app', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No app connected yet')).toBeInTheDocument();
    });
    // Radial map was removed — no connector-map testid and no SVG/canvas
    expect(screen.queryByTestId('connector-map')).not.toBeInTheDocument();
  });

  it('8. connector nodes do not float outside bounds when no app', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No app connected yet')).toBeInTheDocument();
    });
    // No absolutely positioned connector node elements (old radial map nodes)
    expect(screen.queryByTestId('connector-map')).not.toBeInTheDocument();
  });
});

describe('ConnectorsPage — global dependencies always shown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_ALL_READY);
      if (path === '/apps') return Promise.resolve(NO_APPS);
      return Promise.resolve([]);
    });
  });

  it('4. global runtime dependencies section always visible', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('global-deps-list')).toBeInTheDocument();
    });
    // Playwright is a global dep — must appear (may appear in name + detail)
    expect(screen.getAllByText(/playwright/i).length).toBeGreaterThanOrEqual(1);
    // SQLite is a global dep — must appear
    expect(screen.getAllByText(/sqlite/i).length).toBeGreaterThanOrEqual(1);
  });

  it('preserves response provenance on the header and every connector status', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.querySelector('[data-provenance-source="Connectors detail"]')).toHaveTextContent('Real');
    });
    expect(document.querySelectorAll('[data-provenance-source="Connector status"]')).toHaveLength(4);
    expect(document.querySelectorAll('[data-provenance-source="Connector sub-check"]')).toHaveLength(3);
  });
});

describe('ConnectorsPage — Appium status', () => {
  beforeEach(() => vi.clearAllMocks());

  it('5. Appium client ready + CLI/server missing → shows PARTIAL state + warning', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_APPIUM_PARTIAL);
      if (path === '/apps') return Promise.resolve(NO_APPS);
      return Promise.resolve([]);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('global-deps-list')).toBeInTheDocument();
    });
    // Sub-check: client installed (OK)
    expect(screen.getByText(/appium-python-client installed/i)).toBeInTheDocument();
    // Sub-check: CLI missing (MISSING)
    expect(screen.getByText(/`appium` command not found/i)).toBeInTheDocument();
    // Partial warning banner
    expect(screen.getByText(/client installed but mobile testing is not ready/i)).toBeInTheDocument();
  });

  it('6. Appium all parts ready → READY, no warning banner shown', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_ALL_READY);
      if (path === '/apps') return Promise.resolve(NO_APPS);
      return Promise.resolve([]);
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('global-deps-list')).toBeInTheDocument();
    });
    // All sub-checks pass
    expect(screen.getByText(/appium-python-client installed/i)).toBeInTheDocument();
    expect(screen.getByText(/`appium` command found in PATH/i)).toBeInTheDocument();
    expect(screen.getByText(/Appium server reachable/i)).toBeInTheDocument();
    // No partial warning
    expect(screen.queryByText(/client installed but mobile testing is not ready/i)).not.toBeInTheDocument();
  });
});

describe('ConnectorsPage — app exists', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_ALL_READY);
      if (path === '/apps') return Promise.resolve(ONE_APP);
      return Promise.resolve([]);
    });
  });

  it('7. app exists → shows app name in App Runtime Connectors section', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('MyApp')).toBeInTheDocument();
    });
    // Does NOT show empty state
    expect(screen.queryByTestId('no-app-state')).not.toBeInTheDocument();
  });
});

describe('ConnectorsPage — interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path === '/connectors') return Promise.resolve(CONNECTORS_ALL_READY);
      if (path === '/apps') return Promise.resolve(NO_APPS);
      return Promise.resolve([]);
    });
  });

  it('9. Re-check button calls /connectors endpoint', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('global-deps-list')).toBeInTheDocument();
    });
    const callsBefore = mockGet.mock.calls.filter((args: unknown[]) => args[0] === '/connectors').length;
    fireEvent.click(screen.getByRole('button', { name: /re-check/i }));
    await waitFor(() => {
      const callsAfter = mockGet.mock.calls.filter((args: unknown[]) => args[0] === '/connectors').length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  it('10. Connect app CTA navigates to /projects/new', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('No app connected yet')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Connect app' }));
    expect(mockNavigate).toHaveBeenCalledWith('/projects/new');
  });
});
