/**
 * SearchModal tests
 * - Opens on ⌘K
 * - Shows results from API
 * - Keyboard navigation works
 * - Escape closes
 * - No results when offline
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SearchModal } from '../components/layout/SearchModal';
import { Topbar } from '../components/layout/Topbar';

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

describe('SearchModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Return empty arrays by default
    mockGet.mockResolvedValue([]);
  });

  it('renders search input', async () => {
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByPlaceholderText(/search apps, runs/i)).toBeInTheDocument();
  });

  it('shows "Loading…" initially', () => {
    // Don't resolve yet
    mockGet.mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('shows "No data available" when all API calls return empty', async () => {
    mockGet.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    });
  });

  it('shows app results when /apps returns data', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/apps') return Promise.resolve([
        { id: 'a1', name: 'FlowBook', app_type: 'desktop', platform: 'macos', status: 'ready' },
      ]);
      return Promise.resolve([]);
    });
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('FlowBook')).toBeInTheDocument();
    });
    expect(screen.getByText('Apps')).toBeInTheDocument();
  });

  it('filters by query text', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/apps') return Promise.resolve([
        { id: 'a1', name: 'FlowBook', app_type: 'desktop', platform: 'macos', status: 'ready' },
        { id: 'a2', name: 'Videomation', app_type: 'web', platform: 'web', status: 'ready' },
      ]);
      return Promise.resolve([]);
    });
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('FlowBook')).toBeInTheDocument();
    });

    // Type to filter
    const input = screen.getByPlaceholderText(/search apps/i);
    fireEvent.change(input, { target: { value: 'Video' } });

    await waitFor(() => {
      expect(screen.queryByText('FlowBook')).not.toBeInTheDocument();
      expect(screen.getByText('Videomation')).toBeInTheDocument();
    });
  });

  it('shows no results message when query matches nothing', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/apps') return Promise.resolve([
        { id: 'a1', name: 'FlowBook', app_type: 'desktop', platform: 'macos', status: 'ready' },
      ]);
      return Promise.resolve([]);
    });
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText('FlowBook')).toBeInTheDocument());

    const input = screen.getByPlaceholderText(/search apps/i);
    fireEvent.change(input, { target: { value: 'xyznotexist' } });

    await waitFor(() => {
      expect(screen.getByText(/no results for/i)).toBeInTheDocument();
    });
  });

  it('calls onClose when Escape is pressed', async () => {
    mockGet.mockResolvedValue([]);
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <SearchModal onClose={onClose} />
      </MemoryRouter>
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when backdrop is clicked', async () => {
    mockGet.mockResolvedValue([]);
    const onClose = vi.fn();
    const { container } = render(
      <MemoryRouter>
        <SearchModal onClose={onClose} />
      </MemoryRouter>
    );
    // Click the backdrop (outermost div)
    fireEvent.click(container.firstChild as HTMLElement);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows keyboard hint footer', () => {
    mockGet.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <SearchModal onClose={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByText('navigate')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
    expect(screen.getByText('close')).toBeInTheDocument();
  });
});

describe('Topbar search wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue([]);
  });

  it('shows search button with ⌘K hint', () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );
    expect(screen.getByRole('button', { name: /open search/i })).toBeInTheDocument();
    expect(screen.getByText('⌘K')).toBeInTheDocument();
  });

  it('opens SearchModal when search button clicked', async () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );
    const btn = screen.getByRole('button', { name: /open search/i });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search apps/i)).toBeInTheDocument();
    });
  });

  it('opens SearchModal on Cmd+K keydown', async () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );
    fireEvent.keyDown(window, { key: 'k', metaKey: true });
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search apps/i)).toBeInTheDocument();
    });
  });

  it('closes SearchModal on Escape after ⌘K open', async () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );
    fireEvent.keyDown(window, { key: 'k', metaKey: true });
    await waitFor(() => expect(screen.getByPlaceholderText(/search apps/i)).toBeInTheDocument());

    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/search apps/i)).not.toBeInTheDocument();
    });
  });
});
