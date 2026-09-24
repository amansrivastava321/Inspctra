import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { EvidencePanel } from '../components/evidence/EvidencePanel';
import type { EvidenceFile, LiveRunRecord, StepResult } from '../types/api';

const RUN = {
  id: 'run-1',
  pack_id: 'pack-1',
  status: 'failed',
  execution_mode: 'automated',
  step_results: [],
  provenance: 'REAL_EXECUTION',
} as LiveRunRecord;

const FAILED_STEP = {
  id: 'step-1',
  step_id: 'step-1',
  index: 1,
  name: 'Check homepage title',
  status: 'failed',
  provenance: 'REAL_EXECUTION',
} as StepResult;

describe('EvidencePanel', () => {
  beforeEach(() => {
    vi.mocked(fetch).mockReset();
  });

  it('renders a screenshot hero, console entries, and page HTML as text', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      text: async () => '<html><head><title>Failure</title></head></html>',
    } as Response);
    const evidence = [
      {
        id: 'screenshot-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'screenshot', created_at: '2026-08-14T10:00:00Z',
        provenance: 'REAL_EXECUTION',
      },
      {
        id: 'console-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'console', metadata_json: { entries: [
          { type: 'warning', text: 'Deprecated call', timestamp: '2026-08-14T10:00:01Z' },
          { type: 'error', text: 'Uncaught failure', timestamp: '2026-08-14T10:00:02Z' },
        ] },
        provenance: 'REAL_EXECUTION',
      },
      {
        id: 'html-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'page_html', provenance: 'REAL_EXECUTION',
      },
    ] as unknown as EvidenceFile[];

    render(<EvidencePanel run={RUN} step={FAILED_STEP} evidence={evidence} />);

    const hero = screen.getByRole('img', { name: /full-page evidence for step 1/i });
    expect(hero).toHaveAttribute('src', '/api/evidence/screenshot-1/download');
    expect(screen.getByText('Deprecated call')).toBeInTheDocument();
    expect(screen.getByText('Uncaught failure')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /View page source at failure time/i }));
    expect(await screen.findByText(/<title>Failure<\/title>/i)).toBeInTheDocument();
    expect(document.querySelector('title')?.textContent).not.toBe('Failure');

    fireEvent.click(hero);
    expect(screen.getByRole('dialog', { name: /Screenshot evidence/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Close screenshot/i }));
    expect(screen.queryByRole('dialog', { name: /Screenshot evidence/i })).not.toBeInTheDocument();
  });

  it('renders request and response tabs with pretty JSON and redacted headers', () => {
    const evidence = [
      {
        id: 'request-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'api_request', metadata_json: {
          method: 'GET', url: 'https://httpbin.org/get',
          headers: { Authorization: 'Bearer ***REDACTED***' },
        },
      },
      {
        id: 'response-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'api_response', metadata_json: {
          status_code: 200, body_json: { source: 'fixture', ok: true },
        },
      },
      {
        id: 'assertion-1', run_id: RUN.id, step_id: FAILED_STEP.id,
        evidence_type: 'api_assertion', metadata_json: {
          passed: false, expected: 500, actual: 200, details: 'expected 500, got 200',
        },
      },
    ] as unknown as EvidenceFile[];

    render(<EvidencePanel run={RUN} step={FAILED_STEP} evidence={evidence} />);

    expect(screen.getByText(/Bearer \*\*\*REDACTED\*\*\*/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /Response/i }));
    expect(screen.getByText(/"source": "fixture"/i)).toBeInTheDocument();
    expect(screen.getByText(/expected 500, got 200/i)).toBeInTheDocument();
  });

  it('shows pending manual confirmation actions and completed metadata', () => {
    const onManualVerdict = vi.fn();
    const pendingRun = { ...RUN, status: 'pending', execution_mode: 'manual' } as LiveRunRecord;
    const pendingStep = { ...FAILED_STEP, status: 'pending' } as StepResult;
    const { rerender } = render(
      <EvidencePanel
        run={pendingRun}
        step={pendingStep}
        evidence={[]}
        onManualVerdict={onManualVerdict}
      />,
    );

    expect(screen.getByText(/Awaiting confirmation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Confirm step/i }));
    fireEvent.click(screen.getByRole('button', { name: /Decline step/i }));
    expect(onManualVerdict).toHaveBeenNthCalledWith(1, 'passed');
    expect(onManualVerdict).toHaveBeenNthCalledWith(2, 'failed');

    const manualEvidence = [{
      id: 'manual-1', run_id: RUN.id, step_id: FAILED_STEP.id,
      evidence_type: 'manual_confirmation', metadata_json: {
        status: 'passed', tester_name: 'Aman', completed_at: '2026-08-14T12:00:00Z',
        notes: 'Looks correct', actual_result: 'Homepage is visible',
      },
    }] as unknown as EvidenceFile[];
    rerender(
      <EvidencePanel
        run={{ ...pendingRun, status: 'completed' }}
        step={{ ...pendingStep, status: 'passed' }}
        evidence={manualEvidence}
      />,
    );

    expect(screen.getByText(/Confirmed by Aman/i)).toBeInTheDocument();
    expect(screen.getByText('Looks correct')).toBeInTheDocument();
    expect(screen.getByText('Homepage is visible')).toBeInTheDocument();
  });

  it('renders distinct run and step evidence empty states', () => {
    const { rerender } = render(<EvidencePanel run={RUN} step={FAILED_STEP} evidence={[]} />);
    expect(screen.getByText('No evidence for this step.')).toBeInTheDocument();

    rerender(<EvidencePanel run={RUN} step={null} evidence={[]} />);
    expect(screen.getByText(/No evidence captured.*before evidence collection was enabled/i)).toBeInTheDocument();
  });

  it('shows an unavailable message when a screenshot file cannot load', () => {
    const screenshot = [{
      id: 'missing-shot', run_id: RUN.id, step_id: FAILED_STEP.id,
      evidence_type: 'screenshot', provenance: 'REAL_EXECUTION',
    }] as unknown as EvidenceFile[];
    render(<EvidencePanel run={RUN} step={FAILED_STEP} evidence={screenshot} />);

    fireEvent.error(screen.getByRole('img', { name: /full-page evidence for step 1/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Screenshot artifact is unavailable. Other evidence is still shown.',
    );
    expect(screen.queryByRole('img', { name: /full-page evidence for step 1/i })).not.toBeInTheDocument();
  });
});
