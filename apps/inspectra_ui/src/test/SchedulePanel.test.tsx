import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SchedulePanel, type SchedulablePack } from '../components/validation/SchedulePanel';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

import { patch } from '../api/client';

const mockPatch = patch as ReturnType<typeof vi.fn>;

function renderPanel(pack: Partial<SchedulablePack> = {}, onSaved = vi.fn()) {
  render(
    <MemoryRouter>
      <SchedulePanel pack={{ id: 'pack-1', ...pack }} onSaved={onSaved} />
    </MemoryRouter>,
  );
  return onSaved;
}

describe('schedule panel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPatch.mockResolvedValue({});
  });

  it('is shown for a pack with no schedule, so one can be created', () => {
    renderPanel();

    expect(screen.getByText('Not scheduled')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('none');
    expect(screen.getByText(/happen in the background/i)).toBeInTheDocument();
  });

  it('saves an interval schedule as every_<N>m and turns it on', async () => {
    const onSaved = renderPanel();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'minutes' } });
    fireEvent.change(screen.getByLabelText('Minutes between runs'), { target: { value: '30' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /Run on this schedule/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalled());
    expect(mockPatch).toHaveBeenCalledWith('/validation-packs/pack-1', {
      schedule: 'every_30m',
      schedule_enabled: true,
      schedule_timezone: 'UTC',
      continuous: false,
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it('does not save an out-of-range interval and says why', async () => {
    renderPanel();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'minutes' } });
    fireEvent.change(screen.getByLabelText('Minutes between runs'), { target: { value: '2' } });

    const save = screen.getByRole('button', { name: 'Save schedule' });
    expect(save).toBeDisabled();
    fireEvent.click(save);

    expect(mockPatch).not.toHaveBeenCalled();
  });

  it('sends the chosen timezone and the one-flow setting for a daily schedule', async () => {
    renderPanel({ schedule: 'daily', schedule_enabled: true });

    fireEvent.change(screen.getByLabelText('Timezone'), { target: { value: 'Asia/Kolkata' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /Run each test case as one flow/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalled());
    expect(mockPatch).toHaveBeenCalledWith('/validation-packs/pack-1', {
      schedule: 'daily',
      schedule_enabled: true,
      schedule_timezone: 'Asia/Kolkata',
      continuous: true,
    });
  });

  it('turns the schedule off without leaving it enabled', async () => {
    renderPanel({ schedule: 'hourly', schedule_enabled: true });

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'none' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalled());
    expect(mockPatch.mock.calls[0][1]).toMatchObject({ schedule: 'none', schedule_enabled: false });
  });

  it('leaves a saved webhook alone unless it is edited, and never shows the full address', async () => {
    renderPanel({ schedule: 'hourly', schedule_enabled: true, notify_webhook_url: 'https://hooks.example.com/***' });

    expect(screen.getByLabelText('Failure webhook URL')).toHaveAttribute('placeholder', 'Saved: https://hooks.example.com/***');
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalled());
    expect(mockPatch.mock.calls[0][1]).not.toHaveProperty('notify_webhook_url');
  });

  it('sends a new webhook URL, and an empty string to remove the saved one', async () => {
    renderPanel({ schedule: 'hourly', schedule_enabled: true, notify_webhook_url: 'https://hooks.example.com/***' });

    fireEvent.change(screen.getByLabelText('Failure webhook URL'), { target: { value: 'https://new.example.com/hook' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));
    await waitFor(() => expect(mockPatch).toHaveBeenCalledTimes(1));
    expect(mockPatch.mock.calls[0][1]).toMatchObject({ notify_webhook_url: 'https://new.example.com/hook' });
  });

  it('removes a saved webhook with the Remove button', async () => {
    renderPanel({ schedule: 'hourly', schedule_enabled: true, notify_webhook_url: 'https://hooks.example.com/***' });

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalled());
    expect(mockPatch.mock.calls[0][1]).toMatchObject({ notify_webhook_url: '' });
  });

  it('shows the server error when saving fails and does not claim it saved', async () => {
    mockPatch.mockRejectedValue(new Error('Unknown timezone.'));
    const onSaved = renderPanel({ schedule: 'daily' });

    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown timezone.');
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.queryByText(/Saved at/)).not.toBeInTheDocument();
  });

  it('shows the next run only while the schedule is on', () => {
    renderPanel({ schedule: 'hourly', schedule_enabled: false, next_run_at: '2030-01-01T00:00:00+00:00' });

    expect(screen.queryByText(/Next run/)).not.toBeInTheDocument();
  });
});
