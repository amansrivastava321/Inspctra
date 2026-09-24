/**
 * ProjectsPage — delete app and run modal behaviour.
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
    del: vi.fn(),
    post: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get, del } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;

const APPS = [
  { id: 'app-1', name: 'E2E-App', app_type: 'web', project_id: 'p1', tags: [], created_at: '' },
];

// Path-based mock: sidebar calls /projects, page calls /apps — return correct data per path.
function setupMock(appsValue: typeof APPS | []) {
  mockGet.mockImplementation((path: string) => {
    if (path.startsWith('/apps')) return Promise.resolve(appsValue);
    return Promise.resolve([]); // /projects etc.
  });
}

function renderPage() {
  return render(<MemoryRouter><ProjectsPage /></MemoryRouter>);
}

// Wait for app card to render (the "Open" button only exists on app cards, not in sidebar)
async function waitForCard() {
  await waitFor(() => screen.getByRole('button', { name: 'Open' }));
}

describe('ProjectsPage — delete app', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('shows trash (Remove app) button on each app card', async () => {
    setupMock(APPS);
    renderPage();
    await waitForCard();
    const trashBtn = screen.getByTestId('remove-app-app-1');
    expect(trashBtn).toBeInTheDocument();
    expect(trashBtn).not.toBeDisabled();
  });

  it('does NOT delete if confirm returns false', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    setupMock(APPS);
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByTestId('remove-app-app-1'));
    expect(mockDel).not.toHaveBeenCalled();
  });

  it('calls del() and refetches on confirm', async () => {
    // After deletion, return empty list on refetch
    let callCount = 0;
    mockGet.mockImplementation((path: string) => {
      if (path.startsWith('/apps')) {
        callCount++;
        return callCount === 1 ? Promise.resolve(APPS) : Promise.resolve([]);
      }
      return Promise.resolve([]);
    });
    mockDel.mockResolvedValue(undefined);
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByTestId('remove-app-app-1'));
    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith('/apps/app-1');
    });
  });

  it('shows error banner when delete fails', async () => {
    setupMock(APPS);
    mockDel.mockRejectedValue(new Error('Forbidden'));
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByTestId('remove-app-app-1'));
    await waitFor(() => {
      expect(screen.getByText(/Delete failed.*Forbidden/i)).toBeInTheDocument();
    });
  });
});

describe('ProjectsPage — run modal', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('Run button opens run modal', async () => {
    setupMock(APPS);
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByRole('button', { name: /^Run$/i }));
    await waitFor(() => {
      expect(screen.getByTestId('run-modal')).toBeInTheDocument();
      expect(screen.getByText(/run against/i)).toBeInTheDocument();
    });
  });

  it('"View packs" navigates to /packs', async () => {
    setupMock(APPS);
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByRole('button', { name: /^Run$/i }));
    await waitFor(() => screen.getByTestId('run-modal'));
    fireEvent.click(screen.getByRole('button', { name: /view packs/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/packs');
  });

  it('"Create pack" navigates to /packs/new', async () => {
    setupMock(APPS);
    renderPage();
    await waitForCard();
    fireEvent.click(screen.getByRole('button', { name: /^Run$/i }));
    await waitFor(() => screen.getByTestId('run-modal'));
    fireEvent.click(screen.getByRole('button', { name: /create pack/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/packs/new');
  });
});
