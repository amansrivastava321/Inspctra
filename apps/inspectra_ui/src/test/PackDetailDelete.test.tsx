/**
 * PackDetailPage — delete uses del() not messy POST fallback.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PackDetailPage from '../pages/PackDetailPage';

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

const PACK = {
  id: 'pack-001',
  name: 'Smoke Pack',
  project_id: 'proj-1',
  steps: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/packs/pack-001']}>
      <Routes>
        <Route path="/packs/:packId" element={<PackDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PackDetailPage — delete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('delete calls del() and navigates to /packs on success', async () => {
    // get is called for pack, runs, test-plan, test-cases
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/validation-packs/')) {
        if (path.includes('/test-plan')) return Promise.resolve(null);
        if (path.includes('/test-cases')) return Promise.resolve([]);
        return Promise.resolve(PACK);
      }
      if (path.includes('/runs')) return Promise.resolve([]);
      return Promise.resolve(null);
    });
    mockDel.mockResolvedValue(undefined);

    renderPage();
    await waitFor(() => { expect(screen.getAllByText('Smoke Pack').length).toBeGreaterThan(0); });

    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith('/validation-packs/pack-001');
      expect(mockNavigate).toHaveBeenCalledWith('/packs');
    });
  });

  it('delete shows error when del() fails', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/validation-packs/')) {
        if (path.includes('/test-plan')) return Promise.resolve(null);
        if (path.includes('/test-cases')) return Promise.resolve([]);
        return Promise.resolve(PACK);
      }
      if (path.includes('/runs')) return Promise.resolve([]);
      return Promise.resolve(null);
    });
    mockDel.mockRejectedValue(new Error('Forbidden'));

    renderPage();
    await waitFor(() => { expect(screen.getAllByText('Smoke Pack').length).toBeGreaterThan(0); });

    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.getByText(/Forbidden/i)).toBeInTheDocument();
    });
  });
});
