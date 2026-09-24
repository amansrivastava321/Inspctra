/**
 * AddAppRecentFolders.test.tsx
 * Tests for the recent source folders feature in AddAppPage Local Folder tab.
 *
 * Uses localStorage via jsdom. Each test clears the store in beforeEach.
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

const RECENT_KEY = 'inspectra.recentSourceFolders';
const PROJECTS   = [{ id: 'proj-1', name: 'My Project' }];

const SCAN_SUCCESS = {
  id: 'disc-1',
  project_id: 'proj-1',
  source_type: 'local_folder',
  local_path: '/Users/me/myapp',
  status: 'complete',
  detected_stack: [],
  created_at: '',
  updated_at: '',
};

const SCAN_FAIL = {
  ...SCAN_SUCCESS,
  id: 'disc-fail',
  status: 'failed',
  error_message: 'Path does not exist.',
};

function renderPage() { return render(<MemoryRouter><AddAppPage /></MemoryRouter>); }

async function goToLocalFolderTab() {
  await waitFor(() => screen.getByTestId('project-item'));
  fireEvent.click(screen.getByTestId('project-item'));
  fireEvent.click(screen.getByRole('button', { name: /next.*source/i }));
  await waitFor(() => screen.getByTestId('source-tab-local'));
  fireEvent.click(screen.getByTestId('source-tab-local'));
}

async function scanWithPath(path: string) {
  fireEvent.change(screen.getByTestId('local-path-input'), { target: { value: path } });
  fireEvent.click(screen.getByTestId('permission-checkbox'));
  fireEvent.click(screen.getByRole('button', { name: /scan.*detect/i }));
}

describe('AddAppPage — Recent Folders', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem(RECENT_KEY);
    mockGet.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-environment/mode') {
        return Promise.resolve({
          mode: 'local_web',
          local_backend: true,
          native_picker_available: false,
          folder_search_available: true,
          allowed_roots: ['/Users/test/Documents'],
        });
      }
      return Promise.resolve(PROJECTS);
    });
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'unavailable', message: 'Not available.' });
      }
      return Promise.resolve({});
    });
  });

  // ── Section always visible ───────────────────────────────────────────────────

  it('shows Recent folders section on local folder tab', async () => {
    renderPage();
    await goToLocalFolderTab();
    expect(screen.getByTestId('recent-folders-section')).toBeInTheDocument();
  });

  it('shows empty state when no recent folders exist', async () => {
    renderPage();
    await goToLocalFolderTab();
    expect(screen.getByTestId('recent-folders-empty')).toBeInTheDocument();
    expect(screen.getByText(/No recent folders yet/i)).toBeInTheDocument();
  });

  // ── Save on successful scan ──────────────────────────────────────────────────

  it('saves path to recent folders after successful scan', async () => {
    mockPost.mockResolvedValue(SCAN_SUCCESS);

    renderPage();
    await goToLocalFolderTab();
    await scanWithPath('/Users/me/myapp');

    // Goes to step 3 (Review & confirm)
    await waitFor(() => screen.getByText('Review & confirm'));

    // Verify localStorage was written
    const stored = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    expect(stored.length).toBe(1);
    expect(stored[0].path).toBe('/Users/me/myapp');
    expect(stored[0].label).toBe('myapp');
    expect(stored[0].last_used_at).toBeTruthy();
  });

  it('does NOT save path when scan fails', async () => {
    mockPost.mockResolvedValue(SCAN_FAIL);

    renderPage();
    await goToLocalFolderTab();
    await scanWithPath('/Users/me/nonexistent');

    // Wait for scan to complete (stays on step 2 or goes to step 3 with fail state)
    await waitFor(() => expect(mockPost).toHaveBeenCalled());

    const stored = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    expect(stored.length).toBe(0);
  });

  // ── Recent folder UI ─────────────────────────────────────────────────────────

  it('shows recent folder chip after scan', async () => {
    mockPost.mockResolvedValue(SCAN_SUCCESS);

    renderPage();
    await goToLocalFolderTab();
    await scanWithPath('/Users/me/myapp');
    await waitFor(() => screen.getByText('Review & confirm'));

    // Go back to step 2 via re-scan
    fireEvent.click(screen.getByTestId('rescan-btn'));
    await waitFor(() => screen.getByTestId('recent-folder-item-0'));
    expect(screen.getByTestId('recent-folder-item-0')).toBeInTheDocument();
  });

  it('clicking recent folder fills path input', async () => {
    // Pre-populate localStorage
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/saved-app', label: 'saved-app', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    renderPage();
    await goToLocalFolderTab();

    // Recent folder should appear
    await waitFor(() => screen.getByTestId('recent-folder-select-0'));
    fireEvent.click(screen.getByTestId('recent-folder-select-0'));

    // Path input should be filled
    expect(screen.getByTestId('local-path-input')).toHaveValue('/Users/me/saved-app');
  });

  it('scan button still disabled after selecting recent folder — permission required', async () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/saved-app', label: 'saved-app', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    renderPage();
    await goToLocalFolderTab();

    await waitFor(() => screen.getByTestId('recent-folder-select-0'));
    // Fill path via recent folder
    fireEvent.click(screen.getByTestId('recent-folder-select-0'));

    // Permission NOT checked yet
    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).toBeDisabled();
  });

  it('scan enabled after selecting recent folder AND checking permission', async () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/saved-app', label: 'saved-app', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    renderPage();
    await goToLocalFolderTab();

    await waitFor(() => screen.getByTestId('recent-folder-select-0'));
    fireEvent.click(screen.getByTestId('recent-folder-select-0'));
    fireEvent.click(screen.getByTestId('permission-checkbox'));

    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).not.toBeDisabled();
  });

  // ── Remove recent folder ─────────────────────────────────────────────────────

  it('remove button removes recent folder', async () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/saved-app', label: 'saved-app', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    renderPage();
    await goToLocalFolderTab();

    await waitFor(() => screen.getByTestId('recent-folder-remove-0'));
    fireEvent.click(screen.getByTestId('recent-folder-remove-0'));

    await waitFor(() => {
      expect(screen.queryByTestId('recent-folder-item-0')).not.toBeInTheDocument();
      expect(screen.getByTestId('recent-folders-empty')).toBeInTheDocument();
    });
  });

  it('remove button clears path input if that path was selected', async () => {
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/saved-app', label: 'saved-app', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    renderPage();
    await goToLocalFolderTab();

    await waitFor(() => screen.getByTestId('recent-folder-select-0'));
    // Select the recent folder
    fireEvent.click(screen.getByTestId('recent-folder-select-0'));
    expect(screen.getByTestId('local-path-input')).toHaveValue('/Users/me/saved-app');

    // Remove it
    fireEvent.click(screen.getByTestId('recent-folder-remove-0'));

    await waitFor(() => {
      expect(screen.getByTestId('local-path-input')).toHaveValue('');
    });
  });

  // ── Deduplication ────────────────────────────────────────────────────────────

  it('duplicate path is not duplicated in recent folders', async () => {
    // Pre-populate with same path
    localStorage.setItem(RECENT_KEY, JSON.stringify([
      { path: '/Users/me/myapp', label: 'myapp', last_used_at: '2026-01-01T00:00:00Z' },
    ]));

    mockPost.mockResolvedValue(SCAN_SUCCESS);

    renderPage();
    await goToLocalFolderTab();
    await scanWithPath('/Users/me/myapp');
    await waitFor(() => screen.getByText('Review & confirm'));

    const stored = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    expect(stored.filter((f: { path: string }) => f.path === '/Users/me/myapp').length).toBe(1);
  });

  // ── Max 10 cap ───────────────────────────────────────────────────────────────

  it('recent folders capped at 10', async () => {
    // Pre-populate with 10 entries
    const existing = Array.from({ length: 10 }, (_, i) => ({
      path: `/Users/me/app${i}`,
      label: `app${i}`,
      last_used_at: '2026-01-01T00:00:00Z',
    }));
    localStorage.setItem(RECENT_KEY, JSON.stringify(existing));

    mockPost.mockResolvedValue({ ...SCAN_SUCCESS, local_path: '/Users/me/new-app' });

    renderPage();
    await goToLocalFolderTab();
    await scanWithPath('/Users/me/new-app');
    await waitFor(() => screen.getByText('Review & confirm'));

    const stored = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    expect(stored.length).toBeLessThanOrEqual(10);
    expect(stored[0].path).toBe('/Users/me/new-app');
  });

  // Note: browse/drop/search/candidate tests moved to LocalFolderBridge.test.tsx
});

