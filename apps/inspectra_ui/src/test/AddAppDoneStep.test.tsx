/**
 * AddAppDoneStep.test.tsx
 * Tests for Step 4 (Done) — next-action panel, app map generation, navigation buttons.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AddAppPage from '../pages/AddAppPage';

// ── Mocks ──────────────────────────────────────────────────────────────────────

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

const mockNav = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNav };
});

import { get, post } from '../api/client';
const mockGet  = get  as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

// ── Shared test data ───────────────────────────────────────────────────────────

const SAVED_APP = {
  id: 'app-done-001',
  name: 'Done App',
  app_type: 'web',
  project_id: 'proj-1',
  status: 'ready',
};

const APP_MAP = {
  app_map_id: 'map-001',
  app_id: 'app-done-001',
  app_name: 'Done App',
  app_type: 'web',
  map_type: 'fingerprint_based_draft',
  confidence: 'medium',
  detected_stack: ['Node.js', 'React'],
  entry_points: [],
  launch_commands: [],
  runtime_connectors: [{ connector_type: 'web_browser', tool: 'playwright', confidence: 'high', note: '' }],
  testable_surfaces: [
    { name: 'Frontend UI', surface_type: 'frontend_ui', confidence: 'medium', note: '' },
    { name: 'API endpoints', surface_type: 'api_endpoints', confidence: 'low', note: '' },
  ],
  risk_areas: [
    { label: 'XSS', risk_level: 'high', description: '', detection_basis: '' },
  ],
  capability_gaps: [
    { id: 'gap-1', title: 'Routes unknown', description: '', resolution: '', severity: 'medium' },
  ],
  source_type: 'local_folder',
  source_path: '/code/done-app',
  source_url: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const renderPage = () => render(<MemoryRouter><AddAppPage /></MemoryRouter>);

/**
 * Navigates through all 3 steps (project → manual source → review → save)
 * so the test lands on Step 4.
 * mockPost must already be configured by the caller for the /apps call.
 */
async function advanceToStep4() {
  // Projects list loaded
  await waitFor(() => screen.getByTestId('project-item'));
  fireEvent.click(screen.getByTestId('project-item'));
  // Step 1 → Step 2
  fireEvent.click(screen.getByRole('button', { name: /next.*source/i }));
  // Step 2 (manual default) → Step 3
  await waitFor(() => screen.getByRole('button', { name: /next.*app details/i }));
  fireEvent.click(screen.getByRole('button', { name: /next.*app details/i }));
  // Step 3: fill form and save
  await waitFor(() => screen.getByText('App type'));
  fireEvent.click(screen.getByText('Web'));
  fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Done App' } });
  fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));
  // Wait for Step 4
  await waitFor(() => screen.getByText(/Done App connected/i));
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('AddAppPage — Step 4 (Done / next actions)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNav.mockClear();
  });

  it('shows "Generate app map" button after save', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    expect(screen.getByTestId('generate-app-map-btn')).toBeInTheDocument();
    expect(screen.getByTestId('generate-app-map-btn')).toBeEnabled();
  });

  it('shows "Create validation pack" button', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    expect(screen.getByTestId('create-pack-btn')).toBeInTheDocument();
  });

  it('shows "Run Runtime Doctor" button', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    expect(screen.getByTestId('run-doctor-btn')).toBeInTheDocument();
  });

  it('shows "Open App Detail" button', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    expect(screen.getByTestId('open-app-detail-btn')).toBeInTheDocument();
  });

  it('clicking "Generate app map" calls POST /apps/{id}/app-map/generate', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    // First call: save app; second call: generate app map
    mockPost
      .mockResolvedValueOnce(SAVED_APP)
      .mockResolvedValueOnce(APP_MAP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(`/apps/${SAVED_APP.id}/app-map/generate`, {});
    });
  });

  it('shows app map summary after successful generation', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost
      .mockResolvedValueOnce(SAVED_APP)
      .mockResolvedValueOnce(APP_MAP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      // map_type label
      expect(screen.getByText('fingerprint_based_draft')).toBeInTheDocument();
      // surface count
      expect(screen.getByText('2')).toBeInTheDocument();
      // "App map ready" confirmation
      expect(screen.getByText(/app map ready/i)).toBeInTheDocument();
    });
  });

  it('hides generate button and shows "App map ready" after success', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost
      .mockResolvedValueOnce(SAVED_APP)
      .mockResolvedValueOnce(APP_MAP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(screen.queryByTestId('generate-app-map-btn')).not.toBeInTheDocument();
      expect(screen.getByText(/app map ready/i)).toBeInTheDocument();
    });
  });

  it('shows capability gap notice when app map generation fails', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost
      .mockResolvedValueOnce(SAVED_APP)
      .mockRejectedValueOnce(new Error('Map generation failed'));

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(screen.getByText(/capability gap recorded/i)).toBeInTheDocument();
    });
  });

  it('"Open App Detail" navigates to /apps/{id}', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('open-app-detail-btn'));

    expect(mockNav).toHaveBeenCalledWith(`/apps/${SAVED_APP.id}`);
  });

  it('"Create validation pack" navigates to /packs/new', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('create-pack-btn'));

    expect(mockNav).toHaveBeenCalledWith('/packs/new');
  });

  it('"Run Runtime Doctor" navigates to /doctor', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    fireEvent.click(screen.getByTestId('run-doctor-btn'));

    expect(mockNav).toHaveBeenCalledWith('/doctor');
  });

  it('shows app type in summary row', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    await waitFor(() => {
      expect(screen.getByText('web')).toBeInTheDocument();
    });
  });

  it('shows real app ID in Step 4 header (no fake ID)', async () => {
    mockGet.mockResolvedValue([{ id: 'proj-1', name: 'My Project' }]);
    mockPost.mockResolvedValue(SAVED_APP);

    renderPage();
    await advanceToStep4();

    expect(screen.getByText('app-done-001')).toBeInTheDocument();
  });
});
