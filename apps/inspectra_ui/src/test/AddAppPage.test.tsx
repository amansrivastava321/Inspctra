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
const mockGet  = get  as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

const renderPage = () => render(<MemoryRouter><AddAppPage /></MemoryRouter>);

describe('AddAppPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  // ── Step 1 — project selection ──────────────────────────────────────────────

  it('shows step 1 select project on load', async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Select a project/i)).toBeInTheDocument();
    });
  });

  it('Next button disabled until project selected', async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      const next = screen.getByRole('button', { name: /next.*source/i });
      expect(next).toBeDisabled();
    });
  });

  it('shows existing projects from API', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    renderPage();
    await waitFor(() => {
      // getByTestId targets the project list item (not the Sidebar workspace label)
      expect(screen.getByTestId('project-item')).toBeInTheDocument();
    });
  });

  it('shows create project form when no projects exist', async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/No projects yet/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Project name')).toBeInTheDocument();
    });
  });

  // ── Step 2 — app details & save ────────────────────────────────────────────

  // Helper: select existing project and advance to step 3 (Review & confirm) via manual source
  const goToStep2 = async () => {
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId('project-item'));
    // Step 1 → Step 2
    fireEvent.click(screen.getByRole('button', { name: /next.*source/i }));
    // Step 2: Manual tab is default → Next: App details
    await waitFor(() => screen.getByRole('button', { name: /next.*app details/i }));
    fireEvent.click(screen.getByRole('button', { name: /next.*app details/i }));
    await waitFor(() => screen.getByText('App type'));
  };

  it('advances to review step after project selected and source chosen', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    renderPage();
    await goToStep2();
    expect(screen.getByText('Review & confirm')).toBeInTheDocument();
    expect(screen.getByText('App type')).toBeInTheDocument();
  });

  it('Save button disabled until app name and type filled', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    renderPage();
    await goToStep2();
    const save = screen.getByRole('button', { name: /save.*connect/i });
    expect(save).toBeDisabled();
  });

  it('offers Mac, Windows, Android and iOS apps alongside web and API', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    renderPage();
    await goToStep2();

    for (const label of ['Web', 'API / Service', 'Mac app', 'Windows app', 'Android app', 'iOS app']) {
      expect(screen.getByRole('button', { name: label })).not.toBeDisabled();
    }
    expect(screen.queryByRole('button', { name: /Preview/ })).not.toBeInTheDocument();
  });

  it('calls POST /api/apps with correct payload when saved', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    mockPost.mockResolvedValue({
      id: 'app-abc',
      name: 'Demo App',
      app_type: 'web',
      project_id: 'proj-1',
      status: 'ready',
    });

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/apps', expect.objectContaining({
        project_id: 'proj-1',
        name: 'Demo App',
        app_type: 'web',
      }));
    });
  });

  it('saves an Android app with its package, APK and emulator, and needs the package first', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    mockPost.mockResolvedValue({ id: 'app-droid', name: 'Shop', app_type: 'android', project_id: 'proj-1' });

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByRole('button', { name: 'Android app' }));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Shop' } });
    const save = screen.getByRole('button', { name: /save.*connect/i });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('com.example.app'), { target: { value: 'com.shop.app' } });
    fireEvent.change(screen.getByPlaceholderText('/builds/app-debug.apk'), { target: { value: '/b/shop.apk' } });
    fireEvent.change(screen.getByPlaceholderText('Pixel_8_API_35'), { target: { value: 'Pixel_8' } });
    expect(screen.getByText(/Nothing is controlled until you agree/)).toBeInTheDocument();
    fireEvent.click(save);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/apps', expect.objectContaining({
        app_type: 'android',
        app_identifier: 'com.shop.app',
        app_path: '/b/shop.apk',
        device_name: 'Pixel_8',
      }));
    });
  });

  it('asks a Mac app for its name or bundle id and has no device field', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByRole('button', { name: 'Mac app' }));

    expect(screen.getByPlaceholderText('TextEdit or com.apple.TextEdit')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Pixel_8_API_35')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('http://localhost:3000')).not.toBeInTheDocument();
  });

  it('shows real app ID in success screen (no fake done state)', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    mockPost.mockResolvedValue({
      id: 'app-xyz-999',
      name: 'Demo App',
      app_type: 'web',
      project_id: 'proj-1',
      status: 'ready',
    });

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => {
      // Success step shows real app ID from API response
      expect(screen.getByText('app-xyz-999')).toBeInTheDocument();
      expect(screen.getByText(/Demo App connected/i)).toBeInTheDocument();
    });
  });

  it('shows save error when POST fails — no fake Done step', async () => {
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '', created_at: '' },
    ]);
    mockPost.mockRejectedValue(new Error('Internal server error'));

    renderPage();
    await goToStep2();

    fireEvent.click(screen.getByText('Web'));
    fireEvent.change(screen.getByPlaceholderText('My App'), { target: { value: 'Demo App' } });
    fireEvent.click(screen.getByRole('button', { name: /save.*connect/i }));

    await waitFor(() => {
      expect(screen.getByText(/save failed/i)).toBeInTheDocument();
      // Should NOT advance to step 3 without a real saved app
      expect(screen.queryByText(/connected!/i)).not.toBeInTheDocument();
    });
  });

  // ── No pre-filled fake data ─────────────────────────────────────────────────

  it('no hardcoded app name (FlowBook etc.) pre-filled', async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.queryByText(/flowbook/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/nimbus/i)).not.toBeInTheDocument();
    });
  });
});
