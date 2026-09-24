/**
 * ProjectsPage — "Open" button now navigates to /apps/:appId
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProjectsPage from '../pages/ProjectsPage';

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
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;

const MOCK_APPS = [
  {
    id: 'app-abc',
    name: 'Test App',
    app_type: 'web',
    project_id: 'proj-1',
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
  },
];

describe('ProjectsPage — Open button', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('Open button navigates to /apps/:appId', async () => {
    mockGet.mockResolvedValue(MOCK_APPS);
    render(<MemoryRouter><ProjectsPage /></MemoryRouter>);

    await waitFor(() => {
      // App name appears in sidebar and card
      expect(screen.getAllByText('Test App').length).toBeGreaterThan(0);
    });

    // "Open" text appears only on the app card button (search button says "Open search (⌘K)")
    const openBtn = screen.getByRole('button', { name: 'Open' });
    expect(openBtn).not.toBeDisabled();
    fireEvent.click(openBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/apps/app-abc');
  });
});
