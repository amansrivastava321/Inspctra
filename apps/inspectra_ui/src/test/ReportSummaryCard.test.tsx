import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportSummaryCard } from '../components/reports/ReportSummaryCard';
import type { ReportRecord } from '../types/api';

const REPORT: ReportRecord = {
  id: 'report-1',
  run_id: 'run-1',
  app_name: 'Shop',
  pack_name: 'Smoke',
  verdict: 'pass',
  pass_count: 1,
  fail_count: 0,
  unclear_count: 0,
  provenance: 'DRY_RUN',
};

describe('ReportSummaryCard', () => {
  it('shows the report provenance on the summary card', () => {
    render(<ReportSummaryCard report={REPORT} />);
    expect(screen.getByLabelText('Provenance: Dry Run')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download HTML' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download JUnit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download SARIF' })).toBeInTheDocument();
  });
});
