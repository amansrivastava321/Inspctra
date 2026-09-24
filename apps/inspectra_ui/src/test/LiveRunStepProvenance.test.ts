import { describe, expect, it } from 'vitest';
import { toDisplaySteps } from '../pages/LiveRunDetailPage';
import type { LiveRunRecord } from '../types/api';

describe('live run step provenance mapping', () => {
  it('keeps result-level provenance when combining declared steps with results', () => {
    const run = {
      steps: [{ step_id: 'step-1', action_type: 'http_request', description: 'Check API' }],
      step_results: [{
        step_id: 'step-1',
        step: 1,
        status: 'passed',
        provenance: 'REAL_EXECUTION',
      }],
    } as unknown as LiveRunRecord;

    expect(toDisplaySteps(run)[0].provenance).toBe('REAL_EXECUTION');
  });
});
