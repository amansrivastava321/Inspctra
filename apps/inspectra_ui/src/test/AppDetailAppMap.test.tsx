/**
 * AppDetailAppMap.test.tsx
 * Tests for the App Map section in AppDetailPage.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AppDetailPage from '../pages/AppDetailPage';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
  }
  return {
    get: vi.fn(),
    post: vi.fn(),
    del: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get, post } from '../api/client';
const mockGet  = get  as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

// ── Shared data ────────────────────────────────────────────────────────────────

const MOCK_APP = {
  id: 'app-map-test-01',
  name: 'Map Test App',
  app_type: 'web',
  project_id: 'proj-1',
  base_url: 'http://localhost:3000',
  description: '',
  tags: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const MOCK_APP_MAP = {
  app_map_id: 'map-test-01',
  app_id: 'app-map-test-01',
  app_name: 'Map Test App',
  app_type: 'web',
  map_type: 'fingerprint_based_draft',
  confidence: 'medium',
  detected_stack: ['Node.js', 'React'],
  entry_points: [],
  launch_commands: [],
  runtime_connectors: [],
  testable_surfaces: [
    { name: 'Frontend UI', surface_type: 'frontend_ui', confidence: 'medium', note: 'Main web interface' },
    { name: 'API endpoints', surface_type: 'api_endpoints', confidence: 'low', note: '' },
  ],
  risk_areas: [
    { label: 'XSS', risk_level: 'high', description: 'Potential XSS via user inputs', detection_basis: '' },
    { label: 'Auth bypass', risk_level: 'critical', description: '', detection_basis: '' },
  ],
  capability_gaps: [
    { id: 'gap-1', title: 'Routes unknown', description: 'No route list detected', resolution: '', severity: 'medium' },
  ],
  source_type: 'local_folder',
  source_path: '/code/app',
  source_url: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderWithId(appId = 'app-map-test-01') {
  return render(
    <MemoryRouter initialEntries={[`/apps/${appId}`]}>
      <Routes>
        <Route path="/apps/:appId" element={<AppDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('AppDetailPage — App Map section', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows empty state with generate button when no app map exists', async () => {
    // Both GET calls return MOCK_APP (no app_map_id → treated as no map)
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId();
    await waitFor(() => {
      expect(screen.getByTestId('app-map-empty')).toBeInTheDocument();
      expect(screen.getByTestId('generate-app-map-btn')).toBeInTheDocument();
    });
  });

  it('shows app map content when map is pre-loaded', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByTestId('app-map-content')).toBeInTheDocument();
    });
  });

  it('shows map_type label in app map', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByText('fingerprint_based_draft')).toBeInTheDocument();
    });
  });

  it('shows testable surfaces with count', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByText(/Testable surfaces \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText('Frontend UI')).toBeInTheDocument();
    });
  });

  it('shows risk areas with count', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByText(/Risk areas \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText('XSS')).toBeInTheDocument();
    });
  });

  it('shows capability gaps section', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByTestId('app-map-gaps')).toBeInTheDocument();
      expect(screen.getByText('Routes unknown')).toBeInTheDocument();
    });
  });

  it('clicking generate button calls POST /apps/{id}/app-map/generate', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    mockPost.mockResolvedValue(MOCK_APP_MAP);
    renderWithId();

    await waitFor(() => screen.getByTestId('generate-app-map-btn'));
    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        `/apps/${MOCK_APP.id}/app-map/generate`,
        {},
      );
    });
  });

  it('shows app map content after generate succeeds', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    mockPost.mockResolvedValue(MOCK_APP_MAP);
    renderWithId();

    await waitFor(() => screen.getByTestId('generate-app-map-btn'));
    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('app-map-content')).toBeInTheDocument();
      expect(screen.queryByTestId('app-map-empty')).not.toBeInTheDocument();
    });
  });

  it('shows error when generate fails', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    mockPost.mockRejectedValue(new Error('Server error'));
    renderWithId();

    await waitFor(() => screen.getByTestId('generate-app-map-btn'));
    fireEvent.click(screen.getByTestId('generate-app-map-btn'));

    await waitFor(() => {
      expect(screen.getByText(/Server error/i)).toBeInTheDocument();
      // Empty state remains visible
      expect(screen.getByTestId('app-map-empty')).toBeInTheDocument();
    });
  });

  it('shows regenerate button when map is loaded', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => {
      expect(screen.getByTestId('regenerate-app-map-btn')).toBeInTheDocument();
    });
  });

  it('no raw source code shown in app map section', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.endsWith('/app-map')) return Promise.resolve(MOCK_APP_MAP);
      return Promise.resolve(MOCK_APP);
    });
    renderWithId();
    await waitFor(() => screen.getByTestId('app-map-content'));
    // No actual source code should appear
    expect(screen.queryByText(/import React/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/function component/i)).not.toBeInTheDocument();
  });
});
