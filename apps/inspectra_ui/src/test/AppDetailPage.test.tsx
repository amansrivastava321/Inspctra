import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AppDetailPage from '../pages/AppDetailPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
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

import { get, del } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;

const MOCK_APP = {
  id: 'app-001',
  name: 'My Web App',
  app_type: 'web',
  project_id: 'proj-001',
  base_url: 'http://localhost:3000',
  description: 'Test app description',
  tags: ['smoke', 'regression'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};

function renderWithId(appId = 'app-001') {
  return render(
    <MemoryRouter initialEntries={[`/apps/${appId}`]}>
      <Routes>
        <Route path="/apps/:appId" element={<AppDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AppDetailPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders app name and type from backend', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId('app-001');
    await waitFor(() => {
      // App name appears multiple times (sidebar + heading) — just confirm it's present
      expect(screen.getAllByText('My Web App').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/🌐 Web/i).length).toBeGreaterThan(0);
  });

  it('shows base_url as link', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId('app-001');
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /localhost:3000/i })).toBeInTheDocument();
    });
  });

  it('shows tags', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId('app-001');
    await waitFor(() => {
      expect(screen.getByText('smoke')).toBeInTheDocument();
      expect(screen.getByText('regression')).toBeInTheDocument();
    });
  });

  it('shows error state when backend returns 404', async () => {
    const err = new Error('Not found') as Error & { status?: number };
    err.status = 404;
    mockGet.mockRejectedValue(err);
    renderWithId('app-999');
    await waitFor(() => {
      // ErrorState renders the detail message
      expect(screen.getAllByText(/Not found/i).length).toBeGreaterThan(0);
    });
  });

  it('shows app id in metadata section', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId('app-001');
    await waitFor(() => {
      expect(screen.getByText('app-001')).toBeInTheDocument();
    });
  });

  it('delete button visible', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    renderWithId('app-001');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete app/i })).toBeInTheDocument();
    });
  });

  it('delete calls del() and navigates to /projects', async () => {
    mockGet.mockResolvedValue(MOCK_APP);
    mockDel.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderWithId('app-001');
    await waitFor(() => screen.getByRole('button', { name: /delete app/i }));
    fireEvent.click(screen.getByRole('button', { name: /delete app/i }));
    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith('/apps/app-001');
      expect(mockNavigate).toHaveBeenCalledWith('/projects');
    });
  });
});
