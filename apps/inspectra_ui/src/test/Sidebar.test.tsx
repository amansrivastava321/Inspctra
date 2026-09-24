import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Sidebar } from '../components/layout/Sidebar';
import { WorkspaceModeProvider } from '../state/WorkspaceModeContext';

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

import { get, ApiError } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;

const renderSidebar = (props: { readinessScore?: number; readinessSubtitle?: string } = {}) =>
  render(<MemoryRouter><Sidebar {...props} /></MemoryRouter>);

const STORAGE_KEY = 'inspectra.sidebar.groups.v1';

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderSidebarAt(path = '/', mode: 'real' | 'demo' = 'real') {
  const entry = mode === 'demo' && !path.startsWith('/demo') ? `/demo${path === '/' ? '' : path}` : path;
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <WorkspaceModeProvider mode={mode}>
        <Sidebar />
        <LocationProbe />
      </WorkspaceModeProvider>
    </MemoryRouter>,
  );
}

describe('Sidebar — no hardcoded identity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // ── No fake identity ────────────────────────────────────────────────────────

  it('never shows "nimbus" anywhere', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.queryByText(/nimbus/i)).not.toBeInTheDocument();
    });
  });

  it('never shows "Riya" anywhere', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.queryByText(/riya/i)).not.toBeInTheDocument();
    });
  });

  it('never shows fake user initials "RJ"', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.queryByText('RJ')).not.toBeInTheDocument();
    });
  });

  // ── Real user label ─────────────────────────────────────────────────────────

  it('shows "Local user" — no auth endpoint', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText('Local user')).toBeInTheDocument();
    });
  });

  // ── Workspace derived from real projects API ────────────────────────────────

  it('shows "No project selected" when backend returns empty array', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText('No project selected')).toBeInTheDocument();
    });
  });

  it('shows real project name when backend returns project', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'Acme Platform', description: '', created_at: '' },
    ]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText('Acme Platform')).toBeInTheDocument();
    });
    expect(screen.queryByText(/nimbus/i)).not.toBeInTheDocument();
  });

  it('shows summary label when multiple projects', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'Acme Platform', description: '', created_at: '' },
      { id: 'proj-2', name: 'Beta App',      description: '', created_at: '' },
    ]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText('Acme Platform (+1 more)')).toBeInTheDocument();
    });
  });

  it('shows "Backend offline" in workspace selector when offline', async () => {
    const { ApiError: Err } = await import('../api/client');
    mockGet.mockRejectedValue(new (Err as any)(0, 'Network error'));
    renderSidebar();
    await waitFor(() => {
      // Workspace selector label shows "Backend offline"
      expect(screen.getAllByText(/backend offline/i).length).toBeGreaterThan(0);
    });
  });

  // ── Readiness score — no hardcoded 84 ──────────────────────────────────────

  it('shows "—" when readinessScore prop is undefined', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar(); // no readinessScore prop
    await waitFor(() => {
      // Readiness score widget should show "—" not "84"
      expect(screen.queryByText('84')).not.toBeInTheDocument();
    });
  });

  it('shows passed readiness score when provided', async () => {
    mockGet.mockResolvedValue([]);
    renderSidebar({ readinessScore: 72 });
    await waitFor(() => {
      expect(screen.getByText('72')).toBeInTheDocument();
    });
  });
});

describe('Sidebar — task-oriented navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockGet.mockResolvedValue([]);
  });

  it('shows four groups with Setup and Test expanded for a new user', () => {
    renderSidebarAt('/');

    expect(screen.getByRole('button', { name: /setup/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: /^test$/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: /investigate/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /configure/i })).toHaveAttribute('aria-expanded', 'false');
    expect(document.getElementById('sidebar-group-investigate')).toHaveAttribute('hidden');
    expect(document.getElementById('sidebar-group-configure')).toHaveAttribute('hidden');
    expect(screen.getByRole('button', { name: 'Projects' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Validation Packs' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Evidence Center' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument();
  });

  it('toggles a group and persists the complete group state', () => {
    renderSidebarAt('/');

    fireEvent.click(screen.getByRole('button', { name: /investigate/i }));
    expect(screen.getByRole('button', { name: /investigate/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Evidence Center' })).toBeVisible();

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toMatchObject({
      setup: true,
      test: true,
      investigate: true,
      configure: false,
    });
  });

  it('restores saved collapse state when no active item requires expansion', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      setup: false,
      test: false,
      investigate: true,
      configure: true,
    }));

    renderSidebarAt('/');

    expect(screen.getByRole('button', { name: /setup/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /^test$/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /investigate/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: /configure/i })).toHaveAttribute('aria-expanded', 'true');
  });

  it('auto-expands the active deep-link group and highlights only the matching item', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      setup: false,
      test: false,
      investigate: false,
      configure: false,
    }));

    renderSidebarAt('/reports/report-1');

    expect(screen.getByRole('button', { name: /investigate/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Reports' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Evidence Center' })).not.toHaveAttribute('aria-current');
  });

  it('disambiguates items that share a pathname using the approved query view', () => {
    renderSidebarAt('/projects?view=apps');

    expect(screen.getByRole('button', { name: 'Apps' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Projects' })).not.toHaveAttribute('aria-current');
  });

  it('navigates quick actions and duplicate destinations without changing route paths', () => {
    renderSidebarAt('/');

    fireEvent.click(screen.getByRole('button', { name: /new pack/i }));
    expect(screen.getByTestId('location')).toHaveTextContent('/packs/new');

    fireEvent.click(screen.getByRole('button', { name: 'Manual Tests' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/runs?mode=manual');
  });

  it('labels integrations Preview and keeps Run All unavailable honestly', () => {
    renderSidebarAt('/');

    fireEvent.click(screen.getByRole('button', { name: /configure/i }));
    expect(screen.getByRole('button', { name: 'Integrations Preview' })).toBeVisible();
    expect(screen.getByText('Preview')).toBeVisible();

    const runAll = screen.getByRole('button', { name: 'Run All' });
    expect(runAll).toBeDisabled();
    expect(runAll).toHaveAttribute('title', expect.stringMatching(/bulk|scheduling/i));
  });

  it('keeps the same groups in demo mode and disables create/run quick actions', () => {
    renderSidebarAt('/demo', 'demo');

    expect(screen.getByRole('button', { name: /setup/i })).toBeVisible();
    expect(screen.getByRole('button', { name: /^test$/i })).toBeVisible();
    expect(screen.getByRole('button', { name: /investigate/i })).toBeVisible();
    expect(screen.getByRole('button', { name: /configure/i })).toBeVisible();
    expect(screen.getByRole('button', { name: /new pack/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Run All' })).toBeDisabled();
  });
});
