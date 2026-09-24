/**
 * LocalFolderBridge.test.tsx
 * Tests for the LocalFolderBridge component.
 *
 * Verifies:
 * - Mode badge shows "local" in local_web mode
 * - Cloud mode shows disabled message
 * - Browse captures folder name and shows search section
 * - Recommended roots are preselected; optional roots are NOT preselected
 * - Downloads is NOT shown in any root list
 * - No hardcoded machine-specific path appears in the UI
 * - "Find matching folder" calls /api/local-folder-search with selected roots only
 * - Candidate list renders on search results
 * - "Use this folder" calls onPathConfirmed with the path
 * - Not-found shows fallback message
 * - too_broad status shows helpful timeout message
 * - Custom root is added and immediately selected
 * - No fake path filled after browse (path input empty until confirmed)
 * - Tauri gap message shows when __TAURI_INTERNALS__ present
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LocalFolderBridge from '../components/local/LocalFolderBridge';

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

// ── Fixtures ──────────────────────────────────────────────────────────────────

/** Local mode with tiered roots — no hardcoded machine paths. */
const LOCAL_MODE = {
  mode: 'local_web',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: true,
  allowed_roots: ['/Users/test/Projects'],         // backward compat
  recommended_roots: ['/Users/test/Projects'],     // preselected
  optional_roots:   ['/Users/test/Documents'],     // collapsed, not preselected
};

/** Local mode using old shape (no recommended_roots) — backward compat test. */
const LOCAL_MODE_LEGACY = {
  mode: 'local_web',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: true,
  allowed_roots: ['/Users/test/Documents', '/Users/test/Projects'],
};

const CLOUD_MODE = {
  mode: 'cloud',
  local_backend: true,
  native_picker_available: false,
  folder_search_available: false,
  allowed_roots: [],
  recommended_roots: [],
  optional_roots: [],
};

const SEARCH_MATCHED = {
  status: 'matched',
  candidates: [
    {
      path: '/Users/test/Projects/myapp',
      label: 'myapp',
      matched_root: '/Users/test/Projects',
      confidence: 0.7,
      matched_fingerprints: [],
      reason: 'Folder name matched: myapp',
    },
  ],
  message: 'Found 1 match.',
};

const SEARCH_NOT_FOUND = {
  status: 'not_found',
  candidates: [],
  message: 'No matching folder found.',
};

const SEARCH_TOO_BROAD = {
  status: 'too_broad',
  candidates: [],
  message: 'Search took too long. Select a narrower project root (e.g. ~/Projects or ~/Documents/Projects) or paste the full path manually.',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderBridge(props: { currentPath?: string } = {}) {
  const onPathConfirmed = vi.fn();
  const utils = render(
    <LocalFolderBridge
      onPathConfirmed={onPathConfirmed}
      currentPath={props.currentPath ?? ''}
    />
  );
  return { ...utils, onPathConfirmed };
}

function triggerHasName(folderName = 'myapp') {
  fireEvent.drop(screen.getByTestId('bridge-drop-zone'), {
    dataTransfer: { files: [new File([''], folderName)], items: [] },
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('LocalFolderBridge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(LOCAL_MODE);
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'unavailable', message: 'Not available.' });
      }
      return Promise.resolve(SEARCH_MATCHED);
    });
  });

  // ── Mode badge ──────────────────────────────────────────────────────────────

  it('shows local badge when mode is local_web', async () => {
    renderBridge();
    await waitFor(() => expect(screen.getByTestId('bridge-mode-badge')).toBeInTheDocument());
    expect(screen.getByTestId('bridge-mode-badge')).toHaveTextContent(/local/i);
  });

  it('shows cloud-disabled message when mode is cloud', async () => {
    mockGet.mockResolvedValue(CLOUD_MODE);
    renderBridge();
    await waitFor(() => expect(screen.getByTestId('bridge-cloud-message')).toBeInTheDocument());
    expect(screen.getByTestId('bridge-cloud-message')).toHaveTextContent(/desktop app or local agent/i);
  });

  // ── Approved roots checklist ─────────────────────────────────────────────────

  it('renders approved-roots-section after browse captures folder name', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => expect(screen.getByTestId('approved-roots-section')).toBeInTheDocument());
  });

  it('renders recommended root checkboxes from mode response', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-roots-section'));
    // LOCAL_MODE has 1 recommended root → checkbox-0 exists
    expect(screen.getByTestId('approved-root-checkbox-0')).toBeInTheDocument();
  });

  it('recommended roots are preselected by default', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-root-checkbox-0'));
    expect(screen.getByTestId('approved-root-checkbox-0')).toBeChecked();
  });

  it('optional roots are NOT preselected by default', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-roots-section'));
    // Expand optional section
    const showOptBtn = screen.getByTestId('bridge-show-optional-btn');
    fireEvent.click(showOptBtn);
    await waitFor(() => screen.getByTestId('optional-root-checkbox-0'));
    // Optional checkbox must NOT be pre-checked
    expect(screen.getByTestId('optional-root-checkbox-0')).not.toBeChecked();
  });

  it('Downloads is not present in any root — not shown in recommended or optional', async () => {
    mockGet.mockResolvedValue({
      ...LOCAL_MODE,
      recommended_roots: ['/Users/test/Projects'],
      optional_roots: ['/Users/test/Documents', '/Users/test/Desktop'],
      // Downloads intentionally absent
    });
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-roots-section'));
    // Expand optional section
    fireEvent.click(screen.getByTestId('bridge-show-optional-btn'));
    await waitFor(() => screen.getByTestId('optional-root-checkbox-0'));
    // "Downloads" must not appear as a checkbox label
    expect(screen.queryByText(/Downloads/i)).not.toBeInTheDocument();
  });

  it('no hardcoded Aman-specific path appears in the UI', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-roots-section'));
    // UI renders labels (last path component) not full paths — check full body text
    const body = document.body.textContent ?? '';
    expect(body).not.toContain('/Users/aman');
    expect(body).not.toContain('Verifai');
    expect(body).not.toContain('Inspectra-qa-platform');
  });

  it('privacy note is shown', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-privacy-note'));
    expect(screen.getByTestId('bridge-privacy-note')).toHaveTextContent(/never scans your whole computer/i);
  });

  // ── Custom root ──────────────────────────────────────────────────────────────

  it('Add custom root adds it and selects it immediately', async () => {
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-root-add-input'));

    fireEvent.change(screen.getByTestId('approved-root-add-input'), {
      target: { value: '~/CustomProject' },
    });
    fireEvent.click(screen.getByTestId('approved-root-add-btn'));

    // Custom root appears as a checkbox AND is selected
    await waitFor(() => {
      // It's appended after recommended roots
      const idx = LOCAL_MODE.recommended_roots.length;
      const cb = screen.getByTestId(`approved-root-checkbox-${idx}`);
      expect(cb).toBeInTheDocument();
      expect(cb).toBeChecked();
    });
  });

  // ── Search ──────────────────────────────────────────────────────────────────

  it('Find matching folder calls /local-folder-search with selected roots', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        '/local-folder-search',
        expect.objectContaining({
          folder_name: 'myapp',
          confirm_search: true,
          approved_roots: LOCAL_MODE.recommended_roots, // only selected roots
        }),
      )
    );
  });

  it('candidate list renders when search returns results', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-candidates-list'));
    expect(screen.getByTestId('bridge-candidate-0')).toBeInTheDocument();
    expect(screen.getByTestId('bridge-use-candidate-0')).toBeInTheDocument();
  });

  it('Use this folder calls onPathConfirmed with the candidate path', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));
    await waitFor(() => screen.getByTestId('bridge-use-candidate-0'));
    fireEvent.click(screen.getByTestId('bridge-use-candidate-0'));

    expect(onPathConfirmed).toHaveBeenCalledWith('/Users/test/Projects/myapp');
  });

  it('shows confirmed message after Use this folder', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_MATCHED);
      return Promise.resolve({});
    });

    renderBridge({ currentPath: '/Users/test/Projects/myapp' });
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));
    await waitFor(() => screen.getByTestId('bridge-use-candidate-0'));
    fireEvent.click(screen.getByTestId('bridge-use-candidate-0'));

    await waitFor(() => screen.getByTestId('bridge-confirmed-msg'));
  });

  it('shows not-found message when search returns not_found', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_NOT_FOUND);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-not-found-msg'));
    expect(screen.getByTestId('bridge-not-found-msg')).toHaveTextContent(/No matching folder/i);
  });

  // ── too_broad ────────────────────────────────────────────────────────────────

  it('too_broad response shows helpful search-error message', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.resolve(SEARCH_TOO_BROAD);
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-search-error'));
    const errEl = screen.getByTestId('bridge-search-error');
    expect(errEl).toHaveTextContent(/took too long/i);
    expect(errEl).toHaveTextContent(/narrower/i);
  });

  it('timeout network error shows helpful message instead of generic error', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') return Promise.resolve({ status: 'unavailable' });
      if (endpoint === '/local-folder-search') return Promise.reject(new Error('Request timed out'));
      return Promise.resolve({});
    });

    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('bridge-search-btn'));
    fireEvent.click(screen.getByTestId('bridge-search-btn'));

    await waitFor(() => screen.getByTestId('bridge-search-error'));
    const errEl = screen.getByTestId('bridge-search-error');
    expect(errEl).toHaveTextContent(/took too long/i);
  });

  // ── Path safety ─────────────────────────────────────────────────────────────

  it('no fake path after browse — onPathConfirmed not called until candidate confirmed', async () => {
    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    fireEvent.click(screen.getByTestId('bridge-browse-btn'));

    await new Promise(r => setTimeout(r, 100));
    expect(onPathConfirmed).not.toHaveBeenCalled();
  });

  it('native picker selected → calls onPathConfirmed directly', async () => {
    mockPost.mockImplementation((endpoint: string) => {
      if (endpoint === '/local-picker/folder') {
        return Promise.resolve({ status: 'selected', path: '/Users/test/myapp', label: 'myapp' });
      }
      return Promise.resolve({});
    });

    const { onPathConfirmed } = renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    fireEvent.click(screen.getByTestId('bridge-browse-btn'));

    await waitFor(() => expect(onPathConfirmed).toHaveBeenCalledWith('/Users/test/myapp'));
  });

  // ── Backward compat (legacy mode response) ──────────────────────────────────

  it('falls back to allowed_roots when recommended_roots is absent (legacy backend)', async () => {
    mockGet.mockResolvedValue(LOCAL_MODE_LEGACY);
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-browse-btn'));
    triggerHasName();
    await waitFor(() => screen.getByTestId('approved-roots-section'));
    // Both legacy roots appear as recommended checkboxes
    expect(screen.getByTestId('approved-root-checkbox-0')).toBeInTheDocument();
    expect(screen.getByTestId('approved-root-checkbox-1')).toBeInTheDocument();
  });

  // ── Tauri gap message ────────────────────────────────────────────────────────

  it('shows Tauri gap message when __TAURI_INTERNALS__ is in window', async () => {
    (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
    renderBridge();
    await waitFor(() => screen.getByTestId('bridge-tauri-gap-message'));
    expect(screen.getByTestId('bridge-tauri-gap-message')).toHaveTextContent(/Native folder picker not yet wired/i);
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
  });
});
