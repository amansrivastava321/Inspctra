/**
 * AddAppPage — duplicate app warning before POST.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AddAppPage from '../pages/AddAppPage';

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

import { get, post } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

const PROJECT = { id: 'proj-1', name: 'My Project', description: '', created_at: '' };
const EXISTING_APP = { id: 'app-old', name: 'Demo App', app_type: 'web', project_id: 'proj-1', tags: [] };

// Path-based mock: /projects → project list, /apps → app list.
// Avoids ordering issues when Sidebar also calls get('/projects').
function setupMock(existingApps: typeof EXISTING_APP[]) {
  mockGet.mockImplementation((path: string) => {
    if (path.startsWith('/apps')) return Promise.resolve(existingApps);
    if (path.startsWith('/projects')) return Promise.resolve([PROJECT]);
    return Promise.resolve([]);
  });
}

function renderPage() {
  return render(<MemoryRouter><AddAppPage /></MemoryRouter>);
}

async function goToStep2() {
  await waitFor(() => screen.getByTestId('project-item'));
  fireEvent.click(screen.getByTestId('project-item'));
  // Step 1 → Step 2: "Next: Choose source →"
  fireEvent.click(screen.getByRole('button', { name: /next.*source/i }));
  // Step 2: Manual tab is default → "Next: App details →"
  await waitFor(() => screen.getByRole('button', { name: /next.*app details/i }));
  fireEvent.click(screen.getByRole('button', { name: /next.*app details/i }));
  await waitFor(() => screen.getByText('App type'));
}

describe('AddAppPage — duplicate warning', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows dup-warning when same name+type app exists in project', async () => {
    setupMock([EXISTING_APP]);
    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => {
      expect(screen.getByTestId('dup-warning')).toBeInTheDocument();
      expect(screen.getByText(/already exists/i)).toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('"Create anyway" proceeds to POST despite duplicate', async () => {
    setupMock([EXISTING_APP]);
    mockPost.mockResolvedValue({
      id: 'app-new', name: 'Demo App', app_type: 'web', project_id: 'proj-1', tags: [],
    });

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => screen.getByTestId('dup-warning'));
    fireEvent.click(screen.getByRole('button', { name: /create anyway/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/apps', expect.objectContaining({ name: 'Demo App' }));
    });
  });

  it('Cancel clears the duplicate warning without posting', async () => {
    setupMock([EXISTING_APP]);

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => screen.getByTestId('dup-warning'));
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));

    await waitFor(() => {
      expect(screen.queryByTestId('dup-warning')).not.toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('no warning when app name is different', async () => {
    setupMock([EXISTING_APP]);
    mockPost.mockResolvedValue({
      id: 'app-new2', name: 'Other App', app_type: 'web', project_id: 'proj-1', tags: [],
    });

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Other App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalled();
      expect(screen.queryByTestId('dup-warning')).not.toBeInTheDocument();
    });
  });
});
