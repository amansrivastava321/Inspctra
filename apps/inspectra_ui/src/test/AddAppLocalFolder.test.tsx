/**
 * AddAppLocalFolder.test.tsx
 * Tests for Local Folder UX in AddAppPage Step 2.
 *
 * Verifies:
 * - Browse folder button visible (now bridge-browse-btn)
 * - Drop zone visible (now bridge-drop-zone)
 * - Manual path input visible
 * - Permission checkbox required
 * - Scan disabled without path
 * - Scan disabled without permission
 * - Scan enabled with path + permission
 * - Scan posts correct local_folder payload with permission_to_scan
 * - Review page shows Re-scan button
 *
 * Note: browse/drop/search/candidate tests are now in LocalFolderBridge.test.tsx
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

const PROJECTS = [{ id: 'proj-1', name: 'My Project' }];
const renderPage = () => render(<MemoryRouter><AddAppPage /></MemoryRouter>);

const LOCAL_MODE = {
  mode: 'local_web',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: true,
  allowed_roots: ['/Users/test/Documents'],
};

/** Navigate to Step 2 with local_folder tab selected */
async function goToLocalFolderTab() {
  await waitFor(() => screen.getByTestId('project-item'));
  fireEvent.click(screen.getByTestId('project-item'));
  fireEvent.click(screen.getByRole('button', { name: /next.*source/i }));
  await waitFor(() => screen.getByTestId('source-tab-local'));
  fireEvent.click(screen.getByTestId('source-tab-local'));
}

describe('AddAppPage — Local Folder tab UX', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-environment/mode') {
        return Promise.resolve(LOCAL_MODE);
      }
      return Promise.resolve(PROJECTS);
    });
    // Default: local picker unavailable
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'unavailable', message: 'Not available.' });
      }
      return Promise.resolve({});
    });
  });

  // ── UI elements present ──────────────────────────────────────────────────────

  it('shows Browse folder button', async () => {
    renderPage();
    await goToLocalFolderTab();
    await waitFor(() => expect(screen.getByTestId('bridge-browse-btn')).toBeInTheDocument());
  });

  it('shows drag/drop zone', async () => {
    renderPage();
    await goToLocalFolderTab();
    await waitFor(() => expect(screen.getByTestId('bridge-drop-zone')).toBeInTheDocument());
  });

  it('shows manual path input', async () => {
    renderPage();
    await goToLocalFolderTab();
    expect(screen.getByTestId('local-path-input')).toBeInTheDocument();
  });

  it('shows permission checkbox', async () => {
    renderPage();
    await goToLocalFolderTab();
    expect(screen.getByTestId('permission-checkbox')).toBeInTheDocument();
  });

  it('shows permission label text', async () => {
    renderPage();
    await goToLocalFolderTab();
    expect(screen.getByText(/I allow Inspectra to scan safe project fingerprints/i)).toBeInTheDocument();
  });

  // ── Scan button gate ─────────────────────────────────────────────────────────

  it('Scan button disabled with no path and no permission', async () => {
    renderPage();
    await goToLocalFolderTab();
    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).toBeDisabled();
  });

  it('Scan button disabled with path but no permission', async () => {
    renderPage();
    await goToLocalFolderTab();
    fireEvent.change(screen.getByTestId('local-path-input'), {
      target: { value: '/Users/me/myapp' },
    });
    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).toBeDisabled();
  });

  it('Scan button disabled with permission but no path', async () => {
    renderPage();
    await goToLocalFolderTab();
    fireEvent.click(screen.getByTestId('permission-checkbox'));
    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).toBeDisabled();
  });

  it('Scan button enabled with path AND permission checked', async () => {
    renderPage();
    await goToLocalFolderTab();
    fireEvent.change(screen.getByTestId('local-path-input'), {
      target: { value: '/Users/me/myapp' },
    });
    fireEvent.click(screen.getByTestId('permission-checkbox'));
    const scanBtn = screen.getByRole('button', { name: /scan.*detect/i });
    expect(scanBtn).not.toBeDisabled();
  });

  // ── Scan payload ─────────────────────────────────────────────────────────────

  it('scan posts local_folder payload with permission_to_scan=true', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/discovery/scan') return Promise.resolve({
        id: 'disc-1',
        project_id: 'proj-1',
        source_type: 'local_folder',
        local_path: '/Users/me/myapp',
        status: 'complete',
        detected_stack: [],
        created_at: '',
        updated_at: '',
      });
      return Promise.resolve({});
    });

    renderPage();
    await goToLocalFolderTab();
    fireEvent.change(screen.getByTestId('local-path-input'), {
      target: { value: '/Users/me/myapp' },
    });
    fireEvent.click(screen.getByTestId('permission-checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /scan.*detect/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/discovery/scan',
        expect.objectContaining({
          source_type: 'local_folder',
          local_path: '/Users/me/myapp',
          permission_to_scan: true,
        }),
      );
    });
  });

  // ── Re-scan button ───────────────────────────────────────────────────────────

  it('shows Re-scan button on Review step after scan', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/discovery/scan') return Promise.resolve({
        id: 'disc-2',
        project_id: 'proj-1',
        source_type: 'local_folder',
        local_path: '/Users/me/myapp',
        status: 'complete',
        detected_stack: [],
        created_at: '',
        updated_at: '',
      });
      return Promise.resolve({});
    });

    renderPage();
    await goToLocalFolderTab();
    fireEvent.change(screen.getByTestId('local-path-input'), {
      target: { value: '/Users/me/myapp' },
    });
    fireEvent.click(screen.getByTestId('permission-checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /scan.*detect/i }));

    await waitFor(() => screen.getByText('Review & confirm'));
    expect(screen.getByTestId('rescan-btn')).toBeInTheDocument();
  });

  it('Re-scan returns to Step 2', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/discovery/scan') return Promise.resolve({
        id: 'disc-3',
        project_id: 'proj-1',
        source_type: 'local_folder',
        local_path: '/Users/me/myapp',
        status: 'complete',
        detected_stack: [],
        created_at: '',
        updated_at: '',
      });
      return Promise.resolve({});
    });

    renderPage();
    await goToLocalFolderTab();
    fireEvent.change(screen.getByTestId('local-path-input'), {
      target: { value: '/Users/me/myapp' },
    });
    fireEvent.click(screen.getByTestId('permission-checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /scan.*detect/i }));

    await waitFor(() => screen.getByTestId('rescan-btn'));
    fireEvent.click(screen.getByTestId('rescan-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('source-tab-local')).toBeInTheDocument();
    });
  });
});
