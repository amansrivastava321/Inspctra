import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EvidenceCard } from '../components/evidence/EvidenceCard';
import type { EvidenceFile } from '../types/api';

const MOCK_PERF_SUMMARY_EV: EvidenceFile = {
  id: 'ev-perf-01',
  run_id: 'run-perf-01',
  evidence_type: 'performance_summary',
  strength: 'strong',
  title: 'Performance Summary Step 1',
  description: 'Performance assertion for total_load_ms: actual 420ms (budget 1500ms).',
  metadata_json: {
    verdict: 'pass',
    metric_name: 'total_load_ms',
    measured_ms: 420,
    budget_ms: 1500,
    warn_ms: 1000,
    notes: 'Performance assertion for total_load_ms: actual 420ms (budget 1500ms).'
  }
};

const MOCK_WEB_TIMING_EV: EvidenceFile = {
  id: 'ev-perf-02',
  run_id: 'run-perf-01',
  evidence_type: 'web_timing',
  strength: 'strong',
  title: 'Web Timing Step 1',
  description: 'Web timing metrics',
  metadata_json: {
    metrics: {
      total_load_ms: 420,
      first_byte_ms: 50,
      dom_content_loaded_ms: 120,
      load_event_ms: 400,
      resource_count: 12,
      total_transfer_size: 40960
    }
  }
};

describe('Performance Evidence Rendering', () => {
  it('renders performance summary evidence type label', () => {
    render(<EvidenceCard ev={MOCK_PERF_SUMMARY_EV} />);
    expect(screen.getByText('PERFORMANCE SUMMARY')).toBeInTheDocument();
  });

  it('renders web timing evidence type label', () => {
    render(<EvidenceCard ev={MOCK_WEB_TIMING_EV} />);
    expect(screen.getByText('WEB TIMING')).toBeInTheDocument();
  });
});
