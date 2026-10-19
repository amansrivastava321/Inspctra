import { describe, expect, it } from 'vitest';

import { normalizeStepPayload, stepToFormValues } from '../pages/PackDetailPage';
import type { TestCaseStep } from '../types/api';

describe('step editor payload keeps stored values as they were', () => {
  // The backend compares assert_json_path values with `==`, so 200 must not become "200".
  it.each([200, true, { ok: 1 }, ['a']])('does not stringify expected_value %j', value => {
    expect(normalizeStepPayload({ action_type: 'assert_json_path', expected_value: value }).expected_value).toEqual(value);
  });

  it('sends the HTTP method as entered instead of dropping unusual ones', () => {
    expect(normalizeStepPayload({ action_type: 'api_request', method: 'HEAD' }).method).toBe('HEAD');
    expect(normalizeStepPayload({ action_type: 'api_request', method: 'POST' }).method).toBe('POST');
    expect(normalizeStepPayload({ action_type: 'navigate', method: '' }).method).toBeUndefined();
  });
});

describe('opening and saving a step without changes round-trips it', () => {
  it.each([200, true, { ok: 1 }])('keeps expected_value %j unchanged', value => {
    const stored = { step_id: 's1', action_type: 'assert_json_path', expected_json_path: '$.status', expected_value: value } as TestCaseStep;
    expect(normalizeStepPayload(stepToFormValues(stored)).expected_value).toEqual(value);
  });
});
