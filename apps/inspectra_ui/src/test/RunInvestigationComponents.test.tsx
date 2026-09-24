import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { FailureDetails } from '../components/live-run/FailureDetails';
import { EventStreamDrawer } from '../components/live-run/EventStreamDrawer';
import { StepTimeline } from '../components/live-run/StepTimeline';
import type { DurableRunEvent, EvidenceFile, StepResult } from '../types/api';

const FAILED_STEP = {
  id: 'step-1',
  step_id: 'step-1',
  index: 1,
  name: 'Check homepage title',
  status: 'failed',
  started_at: '2026-08-14T10:00:00.000Z',
  completed_at: '2026-08-14T10:00:01.200Z',
  duration_ms: 1200,
  failure_reason: "Expected title to contain 'NonExistent' but was 'Example Domain'",
  expected: 'NonExistent',
  actual: 'Example Domain',
  evidence_count: 2,
  provenance: 'REAL_EXECUTION',
} as StepResult;

describe('run investigation components', () => {
  it('shows actual step identity, timing, result, provenance, and selection', () => {
    const onSelectStep = vi.fn();
    render(<StepTimeline steps={[FAILED_STEP]} onSelectStep={onSelectStep} />);

    expect(screen.getByText('Step 1: Check homepage title')).toBeInTheDocument();
    expect(screen.getByText('1.2s')).toBeInTheDocument();
    expect(screen.getByText(/Expected title to contain/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Provenance: Real')).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 1 status: failed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Step 1: Check homepage title'));
    expect(onSelectStep).toHaveBeenCalledWith(FAILED_STEP);
  });

  it('shows prominent failure details with expected, actual, and exception text', () => {
    const step = { ...FAILED_STEP, error: 'AssertionError: title mismatch' };
    render(<FailureDetails step={step} evidence={[]} />);

    expect(screen.getByText(/Expected title to contain 'NonExistent'/i)).toBeInTheDocument();
    expect(screen.getByText('Expected')).toBeInTheDocument();
    expect(screen.getByText('NonExistent')).toBeInTheDocument();
    expect(screen.getByText('Actual')).toBeInTheDocument();
    expect(screen.getByText('Example Domain')).toBeInTheDocument();
    expect(screen.getByText('AssertionError: title mismatch')).toBeInTheDocument();
  });

  it('derives API expected and actual values from assertion evidence', () => {
    const evidence = [{
      id: 'api-assertion', run_id: 'run-1', step_id: 'step-1',
      evidence_type: 'api_assertion', metadata_json: {
        expected: 500, actual: 200, details: 'expected 500, got 200', passed: false,
      },
    }] as unknown as EvidenceFile[];
    render(<FailureDetails step={{ ...FAILED_STEP, expected: undefined, actual: undefined }} evidence={evidence} />);

    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('200')).toBeInTheDocument();
  });

  it('renders durable event descriptions and the exact legacy empty state', () => {
    const durableEvents = [{
      id: 1,
      run_id: 'run-1',
      step_index: 1,
      step_id: 'step-1',
      event_type: 'step_completed',
      message: 'Step 1 completed: failed',
      payload: { status: 'failed' },
      created_at: '2026-08-14T10:00:01Z',
    }] as DurableRunEvent[];
    const { rerender } = render(
      <EventStreamDrawer durableEvents={durableEvents} liveEvents={[]} connected={false} defaultOpen />,
    );
    expect(screen.getByText('Step 1 completed: failed')).toBeInTheDocument();

    rerender(<EventStreamDrawer durableEvents={[]} liveEvents={[]} connected={false} defaultOpen />);
    expect(screen.getByText(
      'No event stream available for this run. Event capture was enabled on 14 August 2026.',
    )).toBeInTheDocument();
  });

  it('keeps event auto-scroll scoped to the event list', () => {
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    try {
      render(
        <EventStreamDrawer
          durableEvents={[{
            id: 2, run_id: 'run-1', step_index: 1, step_id: 'step-1',
            event_type: 'error', message: 'AssertionError', payload: {},
            created_at: '2026-08-14T10:00:02Z',
          }]}
          liveEvents={[]}
          connected={false}
          defaultOpen
        />,
      );
      expect(scrollIntoView).not.toHaveBeenCalled();
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it('deduplicates live aliases when the durable event arrives', () => {
    const timestamp = '2026-08-14T10:00:01Z';
    render(
      <EventStreamDrawer
        durableEvents={[{
          id: 3, run_id: 'run-1', step_index: 1, step_id: 'step-1',
          event_type: 'step_completed', message: 'Step 1 completed: failed',
          payload: { step: 1, step_id: 'step-1', status: 'failed' }, created_at: timestamp,
        }]}
        liveEvents={[{
          type: 'step_end', step: 1, step_id: 'step-1', step_name: 'Check title',
          status: 'failed', ts: timestamp,
        }]}
        connected={false}
        defaultOpen
      />,
    );

    expect(screen.getAllByText('STEP COMPLETED')).toHaveLength(1);
    expect(screen.getByText('1 events')).toBeInTheDocument();
  });
});
