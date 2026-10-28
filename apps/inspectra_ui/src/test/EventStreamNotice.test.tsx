import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventStreamDrawer } from '../components/live-run/EventStreamDrawer';
import type { DurableRunEvent, RunEvent } from '../types/api';

const MESSAGE = 'No display is available on the machine running Inspectra, so this run uses a hidden browser instead.';
const TS = '2026-10-28T12:00:00.000000+00:00';

const durable: DurableRunEvent = {
  id: 1,
  run_id: 'run-1',
  event_type: 'notice',
  message: MESSAGE,
  payload: { run_id: 'run-1' },
  created_at: TS,
};

const live: RunEvent = { type: 'notice', message: MESSAGE, ts: TS };

describe('run event notices', () => {
  it('shows a stored notice after the run has finished', () => {
    render(<EventStreamDrawer durableEvents={[durable]} liveEvents={[]} connected={false} defaultOpen />);

    expect(screen.getByText('NOTICE')).toBeInTheDocument();
    expect(screen.getByText(MESSAGE)).toBeInTheDocument();
  });

  it('shows a notice once while the run is live, not once per source', () => {
    render(<EventStreamDrawer durableEvents={[durable]} liveEvents={[live]} connected active defaultOpen />);

    expect(screen.getAllByText(MESSAGE)).toHaveLength(1);
  });

  it('opens from the collapsed state like any other event list', () => {
    render(<EventStreamDrawer durableEvents={[durable]} liveEvents={[]} connected={false} />);

    fireEvent.click(screen.getByRole('button'));

    expect(screen.getByText(MESSAGE)).toBeInTheDocument();
  });
});
