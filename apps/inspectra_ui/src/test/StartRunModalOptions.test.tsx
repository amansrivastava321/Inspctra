import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { StartRunModal } from '../components/modals/StartRunModal';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
}));

import { get, post } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

function renderModal(isManual = false) {
  return render(
    <MemoryRouter>
      <StartRunModal packId="pack-1" packName="Pack" onClose={vi.fn()} isManual={isManual} />
    </MemoryRouter>,
  );
}

async function pickWebsiteAndStart() {
  fireEvent.click(await screen.findByRole('button', { name: /Website/i }));
  fireEvent.click(screen.getByRole('button', { name: 'Start run' }));
  await waitFor(() => expect(mockPost).toHaveBeenCalled());
}

describe('start-run dialog options', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue([{ id: 'web-1', name: 'Website', app_type: 'web' }]);
    mockPost.mockResolvedValue({ id: 'run-1' });
  });

  it('sends the same request as before when no option is ticked', async () => {
    renderModal();

    await pickWebsiteAndStart();

    expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-1/run', {
      app_target_id: 'web-1',
      execution_mode: 'automated',
    });
  });

  it('offers both options as labelled checkboxes, unticked', async () => {
    renderModal();

    const watch = await screen.findByRole('checkbox', { name: /Watch it run/i });
    const flow = screen.getByRole('checkbox', { name: /Run each test case as one flow/i });

    expect(watch).not.toBeChecked();
    expect(flow).not.toBeChecked();
  });

  it('sends watch when it is ticked', async () => {
    renderModal();
    fireEvent.click(await screen.findByRole('checkbox', { name: /Watch it run/i }));

    await pickWebsiteAndStart();

    expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-1/run', {
      app_target_id: 'web-1',
      execution_mode: 'automated',
      watch: true,
    });
  });

  it('sends both options when both are ticked', async () => {
    renderModal();
    fireEvent.click(await screen.findByRole('checkbox', { name: /Watch it run/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /Run each test case as one flow/i }));

    await pickWebsiteAndStart();

    expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-1/run', {
      app_target_id: 'web-1',
      execution_mode: 'automated',
      watch: true,
      continuous: true,
    });
  });

  it('does not send an option that was ticked and then unticked', async () => {
    renderModal();
    const watch = await screen.findByRole('checkbox', { name: /Watch it run/i });
    fireEvent.click(watch);
    fireEvent.click(watch);

    await pickWebsiteAndStart();

    expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-1/run', {
      app_target_id: 'web-1',
      execution_mode: 'automated',
    });
  });

  it('shows no automated-run options for a manual run', async () => {
    renderModal(true);

    await screen.findByRole('button', { name: /Website/i });

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Website/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Start run' }));
    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost).toHaveBeenCalledWith('/validation-packs/pack-1/runs', {
      app_target_id: 'web-1',
      execution_mode: 'manual',
    });
  });
});
