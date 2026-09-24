import { describe, expect, it } from 'vitest';

import { getStepValidationErrors, normalizeStepPayload } from '../pages/PackDetailPage';


describe('validation-pack step timeout contract', () => {
  it('defaults an omitted timeout to 30000 ms', () => {
    expect(normalizeStepPayload({ action_type: 'navigate' }).timeout_ms).toBe(30000);
  });

  it('preserves a configured timeout in the saved payload', () => {
    const reloadedForm = { action_type: 'api_request', method: 'GET', url: '/health', timeout_ms: 1250 };
    expect(normalizeStepPayload(reloadedForm).timeout_ms).toBe(1250);
    expect(getStepValidationErrors(reloadedForm)).toEqual([]);
  });

  it('rejects values outside the backend 1–300000 ms bounds', () => {
    expect(getStepValidationErrors({ action_type: 'navigate', timeout_ms: 0 })).toContain(
      'Timeout must be greater than 0.',
    );
    expect(getStepValidationErrors({ action_type: 'navigate', timeout_ms: 300001 })).toContain(
      'Timeout cannot exceed 300000 ms (5 minutes).',
    );
    expect(getStepValidationErrors({ action_type: 'navigate', timeout_ms: 300000 })).toEqual([]);
  });
});
