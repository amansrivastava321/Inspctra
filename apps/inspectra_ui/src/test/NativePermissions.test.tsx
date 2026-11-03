import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { StartRunModal } from '../components/modals/StartRunModal';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

import { del, get, post, put } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockPut = put as ReturnType<typeof vi.fn>;
const mockDel = del as ReturnType<typeof vi.fn>;

const SCOPES = [
  { id: 'launch_apps', label: 'Open and quit the app under test' },
  { id: 'control_input', label: 'Move the pointer, click and type in that app' },
  { id: 'screenshots', label: 'Take screenshots of the screen as evidence' },
];

function readiness(overrides: Record<string, unknown> = {}) {
  return {
    platform: 'native_macos',
    label: 'Mac app',
    requirements: [
      { id: 'accessibility', label: 'Accessibility', status: 'missing', how_to_fix: 'Turn on Terminal under Accessibility.', can_request: true, optional: false },
      { id: 'screen_recording', label: 'Screen Recording', status: 'missing', how_to_fix: 'Turn it on.', can_request: true, optional: true },
    ],
    tools_ready: false,
    consent: null,
    consent_scopes: SCOPES,
    ready: false,
    ...overrides,
  };
}

const APPS = [
  { id: 'web-1', name: 'Website', app_type: 'web' },
  { id: 'mac-1', name: 'TextEdit', app_type: 'native_macos' },
];

function routeGets(state: { ready: ReturnType<typeof readiness> }) {
  mockGet.mockImplementation((path: string) => {
    if (path === '/apps') return Promise.resolve(APPS);
    if (path.startsWith('/native/')) return Promise.resolve(state.ready);
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}

function renderModal() {
  render(
    <MemoryRouter>
      <StartRunModal packId="pack-1" packName="Pack" onClose={vi.fn()} />
    </MemoryRouter>,
  );
}

describe('permissions for desktop and mobile apps', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPost.mockResolvedValue({ id: 'run-1' });
    mockPut.mockResolvedValue({});
    mockDel.mockResolvedValue(undefined);
  });

  it('asks nothing for a website', async () => {
    routeGets({ ready: readiness() });
    renderModal();

    fireEvent.click(await screen.findByRole('button', { name: /Website/ }));

    expect(screen.queryByRole('group', { name: 'Permissions' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start run' })).not.toBeDisabled();
  });

  it('lists what the Mac needs and keeps Start disabled until everything is allowed', async () => {
    routeGets({ ready: readiness() });
    renderModal();

    fireEvent.click(await screen.findByRole('button', { name: /TextEdit/ }));

    const panel = await screen.findByRole('group', { name: 'Permissions' });
    expect(within(panel).getByTestId('requirement-accessibility')).toHaveTextContent('Missing');
    expect(within(panel).getByText('Turn on Terminal under Accessibility.')).toBeInTheDocument();
    expect(within(panel).getByTestId('requirement-screen_recording')).toHaveTextContent('(optional)');
    expect(within(panel).getByRole('note')).toHaveTextContent(/real screen/);
    expect(screen.getByRole('button', { name: 'Start run' })).toBeDisabled();
  });

  it('asks the operating system for a permission when the user clicks it', async () => {
    routeGets({ ready: readiness() });
    renderModal();
    fireEvent.click(await screen.findByRole('button', { name: /TextEdit/ }));
    const panel = await screen.findByRole('group', { name: 'Permissions' });

    fireEvent.click(within(within(panel).getByTestId('requirement-accessibility')).getByRole('button', { name: 'Ask the system' }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith('/native/native_macos/permissions/accessibility/request'));
  });

  it('only sends consent once every item is ticked, and then Start is enabled', async () => {
    const state = { ready: readiness({ requirements: [], tools_ready: true }) };
    routeGets(state);
    renderModal();
    fireEvent.click(await screen.findByRole('button', { name: /TextEdit/ }));
    const panel = await screen.findByRole('group', { name: 'Permissions' });

    const allow = within(panel).getByRole('button', { name: 'Allow' });
    expect(allow).toBeDisabled();
    for (const scope of SCOPES) fireEvent.click(within(panel).getByRole('checkbox', { name: scope.label }));
    fireEvent.click(within(panel).getByRole('checkbox', { name: /scheduled runs/ }));
    state.ready = readiness({
      requirements: [], tools_ready: true, ready: true,
      consent: { scopes: SCOPES.map(s => s.id), unattended: true, granted_at: 'now' },
    });
    fireEvent.click(allow);

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith('/native/native_macos/consent', {
      scopes: ['launch_apps', 'control_input', 'screenshots'],
      unattended: true,
    }));
    expect(await within(panel).findByText(/You allowed Inspectra/)).toHaveTextContent('including scheduled runs');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start run' })).not.toBeDisabled());
  });

  it('lets the user take the permission back', async () => {
    const state = {
      ready: readiness({
        requirements: [], tools_ready: true, ready: true,
        consent: { scopes: SCOPES.map(s => s.id), unattended: false, granted_at: 'now' },
      }),
    };
    routeGets(state);
    renderModal();
    fireEvent.click(await screen.findByRole('button', { name: /TextEdit/ }));
    const panel = await screen.findByRole('group', { name: 'Permissions' });

    state.ready = readiness({ requirements: [], tools_ready: true });
    fireEvent.click(await within(panel).findByRole('button', { name: 'Take back' }));

    await waitFor(() => expect(mockDel).toHaveBeenCalledWith('/native/native_macos/consent'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start run' })).toBeDisabled());
  });

  it('describes Watch for an emulator instead of a browser', async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === '/apps') return Promise.resolve([{ id: 'and-1', name: 'Shop', app_type: 'android' }]);
      return Promise.resolve(readiness({ platform: 'android', label: 'Android (emulator or device)' }));
    });
    renderModal();

    fireEvent.click(await screen.findByRole('button', { name: /Shop/ }));

    expect(await screen.findByText(/emulator or simulator window/)).toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument(); // no "real screen" warning for an emulator
  });
});
