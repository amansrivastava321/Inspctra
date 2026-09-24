/**
 * AddAppPage — project list filtering, search, delete, and Step 1 UX.
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

import { get, post, del } from '../api/client';
const mockGet  = get  as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockDel  = del  as ReturnType<typeof vi.fn>;

const REAL_PROJ = { id: 'p-real', name: 'My Real Project', description: '', created_at: '' };
const E2E_PROJ  = { id: 'p-e2e',  name: 'E2E-Test-Project', description: '', created_at: '' };
const ALPHA     = { id: 'p-a',    name: 'Alpha',             description: '', created_at: '' };
const BETA      = { id: 'p-b',    name: 'Beta',              description: '', created_at: '' };

function setupMock(projects: object[]) {
  mockGet.mockImplementation((path: string) => {
    if (path.startsWith('/projects')) return Promise.resolve(projects);
    if (path.startsWith('/apps'))     return Promise.resolve([]);
    return Promise.resolve([]);
  });
}

function renderPage() {
  return render(<MemoryRouter><AddAppPage /></MemoryRouter>);
}

// ── Step 1 copy and create behaviour ─────────────────────────────────────────

describe('AddAppPage — step 1 UX', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows "Create a new project" heading', async () => {
    setupMock([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Create a new project')).toBeInTheDocument();
    });
  });

  it('Create button is disabled when name input is empty', async () => {
    setupMock([]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /create project/i }));
    expect(screen.getByRole('button', { name: /create project/i })).toBeDisabled();
  });

  it('shows hint "Enter a project name" when input is empty', async () => {
    setupMock([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/enter a project name/i)).toBeInTheDocument();
    });
  });

  it('Create button enables after typing project name', async () => {
    setupMock([]);
    renderPage();
    await waitFor(() => screen.getByTestId('new-project-name-input'));
    fireEvent.change(screen.getByTestId('new-project-name-input'), { target: { value: 'My New' } });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create project/i })).not.toBeDisabled();
    });
  });

  it('Create calls POST /api/projects with correct name', async () => {
    setupMock([]);
    mockPost.mockResolvedValue({ id: 'p-new', name: 'My New', description: '', created_at: '' });
    renderPage();
    await waitFor(() => screen.getByTestId('new-project-name-input'));
    fireEvent.change(screen.getByTestId('new-project-name-input'), { target: { value: 'My New' } });
    fireEvent.click(screen.getByRole('button', { name: /create project/i }));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/projects', { name: 'My New' });
    });
  });

  it('created project is auto-selected and summary shows name', async () => {
    const newProj = { id: 'p-new', name: 'My New', description: '', created_at: '' };
    let projectList: object[] = [];
    mockGet.mockImplementation((path: string) => {
      if (path.startsWith('/projects')) return Promise.resolve(projectList);
      return Promise.resolve([]);
    });
    mockPost.mockImplementation(async () => {
      projectList = [newProj];
      return newProj;
    });
    renderPage();
    await waitFor(() => screen.getByTestId('new-project-name-input'));
    fireEvent.change(screen.getByTestId('new-project-name-input'), { target: { value: 'My New' } });
    fireEvent.click(screen.getByRole('button', { name: /create project/i }));
    await waitFor(() => {
      expect(screen.getByTestId('selected-project-summary')).toHaveTextContent('My New');
    });
  });

  it('selected project summary shows name after clicking a project', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId('project-item'));
    await waitFor(() => {
      expect(screen.getByTestId('selected-project-summary')).toHaveTextContent('My Real Project');
    });
  });

  it('summary shows "No project selected yet." initially', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('selected-project-summary'));
    expect(screen.getByTestId('selected-project-summary')).toHaveTextContent('No project selected yet.');
  });

  it('Next button is disabled before project selected', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    expect(screen.getByRole('button', { name: /next.*source/i })).toBeDisabled();
  });

  it('Next button enables after project selected', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId('project-item'));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /next.*source/i })).not.toBeDisabled();
    });
  });

  it('disabled Next shows "Select or create a project to continue."', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    expect(screen.getByText(/select or create a project to continue/i)).toBeInTheDocument();
  });

  it('helper text disappears after project selected', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId('project-item'));
    await waitFor(() => {
      expect(screen.queryByText(/select or create a project to continue/i)).not.toBeInTheDocument();
    });
  });

  it('empty normal projects state says "No normal projects found."', async () => {
    setupMock([E2E_PROJ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no normal projects found/i)).toBeInTheDocument();
    });
  });

  it('backend create error is visible', async () => {
    setupMock([]);
    mockPost.mockRejectedValue(new Error('Name taken'));
    renderPage();
    await waitFor(() => screen.getByTestId('new-project-name-input'));
    fireEvent.change(screen.getByTestId('new-project-name-input'), { target: { value: 'Taken' } });
    fireEvent.click(screen.getByRole('button', { name: /create project/i }));
    await waitFor(() => {
      expect(screen.getByText(/name taken/i)).toBeInTheDocument();
    });
  });
});

// ── Project list filtering ────────────────────────────────────────────────────

describe('AddAppPage — project list filtering', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('hides E2E- projects by default', async () => {
    setupMock([REAL_PROJ, E2E_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    const items = screen.getAllByTestId('project-item');
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent('My Real Project');
    expect(screen.queryByText('E2E-Test-Project')).not.toBeInTheDocument();
  });

  it('shows toggle when E2E- projects exist', async () => {
    setupMock([REAL_PROJ, E2E_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('show-test-projects-toggle'));
  });

  it('test project toggle is a real button element', async () => {
    setupMock([REAL_PROJ, E2E_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('show-test-projects-toggle'));
    const toggle = screen.getByTestId('show-test-projects-toggle');
    expect(toggle.tagName).toBe('BUTTON');
  });

  it('toggle reveals E2E- projects', async () => {
    setupMock([REAL_PROJ, E2E_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('show-test-projects-toggle'));
    fireEvent.click(screen.getByTestId('show-test-projects-toggle'));
    await waitFor(() => {
      const items = screen.getAllByTestId('project-item');
      expect(items).toHaveLength(2);
    });
  });

  it('does not show toggle when no E2E- projects', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    expect(screen.queryByTestId('show-test-projects-toggle')).not.toBeInTheDocument();
  });

  it('search filters project list', async () => {
    setupMock([ALPHA, BETA]);
    renderPage();
    await waitFor(() => {
      const items = screen.getAllByTestId('project-item');
      expect(items).toHaveLength(2);
    });
    fireEvent.change(screen.getByTestId('project-search'), { target: { value: 'Alpha' } });
    await waitFor(() => {
      expect(screen.getAllByTestId('project-item')).toHaveLength(1);
      expect(screen.getByTestId('project-item')).toHaveTextContent('Alpha');
    });
  });

  it('search no-match shows "No matching projects."', async () => {
    setupMock([ALPHA, BETA]);
    renderPage();
    await waitFor(() => screen.getAllByTestId('project-item'));
    fireEvent.change(screen.getByTestId('project-search'), { target: { value: 'zzzno' } });
    await waitFor(() => {
      expect(screen.getByText(/no matching projects/i)).toBeInTheDocument();
    });
  });
});

// ── Project delete ────────────────────────────────────────────────────────────

describe('AddAppPage — project delete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('each project row has a delete button', async () => {
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    expect(screen.getByTestId(`delete-project-${REAL_PROJ.id}`)).toBeInTheDocument();
  });

  it('delete calls del() with correct path', async () => {
    setupMock([REAL_PROJ]);
    mockDel.mockResolvedValue(undefined);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId(`delete-project-${REAL_PROJ.id}`));
    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith(`/projects/${REAL_PROJ.id}`);
    });
  });

  it('does not delete when confirm is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    setupMock([REAL_PROJ]);
    renderPage();
    await waitFor(() => screen.getByTestId('project-item'));
    fireEvent.click(screen.getByTestId(`delete-project-${REAL_PROJ.id}`));
    expect(mockDel).not.toHaveBeenCalled();
  });
});
