/**
 * validationPacks.ts - Test plan + test case API calls.
 *
 * All calls go through the typed client. No hardcoded app names.
 * No credentials stored. No unsafe HTML.
 */
import { assertRealWorkspace, get, post, patch, del } from './client';
import type {
  TestCase,
  TestCaseCreate,
  TestCaseUpdate,
  TestPlan,
  TestCaseStep,
  TestCaseStepCreate,
  TestCaseStepUpdate,
  LiveRunRecord,
  EvidenceFile,
  AITestPlanPreview,
  AIProposedTestCase,
} from '../types/api';

/** Return existing test plan for pack, or null if none. */
export function getTestPlan(packId: string): Promise<TestPlan | null> {
  return get<TestPlan | null>(`/validation-packs/${packId}/test-plan`);
}

/** Generate (or return cached) test plan. force=true overwrites. app_id enables app-map enrichment. */
export function generateTestPlan(packId: string, force = false, appId?: string): Promise<TestPlan> {
  return post<TestPlan>(`/validation-packs/${packId}/test-plan/generate`, {
    force,
    ...(appId ? { app_id: appId } : {}),
  });
}

/** List all test cases for a pack, optionally filtered by test_type. */
export function listTestCases(packId: string, testType?: string): Promise<TestCase[]> {
  const qs = testType ? `?test_type=${encodeURIComponent(testType)}` : '';
  return get<TestCase[]>(`/validation-packs/${packId}/test-cases${qs}`);
}

/** Manually create a test case in a pack. */
export function createTestCase(packId: string, payload: TestCaseCreate): Promise<TestCase> {
  return post<TestCase>(`/validation-packs/${packId}/test-cases`, payload);
}

/** Update fields on an existing test case. */
export function updateTestCase(
  packId: string,
  testCaseId: string,
  payload: TestCaseUpdate,
): Promise<TestCase> {
  return patch<TestCase>(`/validation-packs/${packId}/test-cases/${testCaseId}`, payload);
}

/** Delete a test case. Returns void on 204. */
export function deleteTestCase(packId: string, testCaseId: string): Promise<void> {
  return del(`/validation-packs/${packId}/test-cases/${testCaseId}`);
}

/** Duplicate a test case with all its steps. */
export function duplicateTestCase(caseId: string): Promise<TestCase> {
  return post<TestCase>(`/test-cases/${caseId}/duplicate`);
}

/** Add a new test step to a test case. */
export function addTestCaseStep(caseId: string, step: TestCaseStepCreate): Promise<TestCaseStep> {
  return post<TestCaseStep>(`/test-cases/${caseId}/steps`, step);
}

/** Update an existing test step. */
export function updateTestCaseStep(stepId: string, payload: TestCaseStepUpdate): Promise<TestCaseStep> {
  return patch<TestCaseStep>(`/test-steps/${stepId}`, payload);
}

/** Delete a test step. */
export function deleteTestCaseStep(stepId: string): Promise<void> {
  return del(`/test-steps/${stepId}`);
}

/** Reorder test steps for a test case. */
export function reorderTestCaseSteps(caseId: string, stepIds: string[]): Promise<void> {
  return post(`/test-cases/${caseId}/steps/reorder`, { step_ids: stepIds });
}

/** Start a manual validation pack run. */
export function startManualRun(packId: string, appId: string): Promise<LiveRunRecord> {
  return post<LiveRunRecord>(`/validation-packs/${encodeURIComponent(packId)}/runs`, {
    app_target_id: appId,
    execution_mode: 'manual',
  });
}

/** Save manual step verdict result. */
export function saveManualStepVerdict(
  runId: string,
  stepId: string,
  payload: {
    status: string;
    actual_result?: string;
    notes?: string;
    failure_reason?: string;
    tester_name?: string;
  },
): Promise<LiveRunRecord> {
  return post<LiveRunRecord>(
    `/live-runs/${encodeURIComponent(runId)}/manual-steps/${encodeURIComponent(stepId)}/result`,
    payload,
  );
}

/** Upload evidence for manual step. */
export function uploadManualEvidence(
  runId: string,
  stepId: string,
  file: File,
  name?: string,
  evidenceType?: string,
): Promise<EvidenceFile> {
  assertRealWorkspace();
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (evidenceType) formData.append('evidence_type', evidenceType);

  return fetch(`/api/live-runs/${encodeURIComponent(runId)}/manual-steps/${encodeURIComponent(stepId)}/evidence`, {
    method: 'POST',
    body: formData,
  }).then(resp => {
    if (!resp.ok) {
      throw new Error(`Upload failed: ${resp.statusText}`);
    }
    return resp.json() as Promise<EvidenceFile>;
  });
}

/** Finalize manual run. */
export function finalizeManualRun(runId: string): Promise<LiveRunRecord> {
  return post<LiveRunRecord>(`/live-runs/${encodeURIComponent(runId)}/finalize`);
}

/** Generate AI proposed test plan (returns preview only). */
export function generateAiTestPlan(packId: string, appId?: string): Promise<AITestPlanPreview> {
  return post<AITestPlanPreview>(`/validation-packs/${packId}/test-plan/generate-ai`, {
    ...(appId ? { app_id: appId } : {}),
  });
}

/** Accept and persist selected AI proposed test cases. */
export function acceptAiTestPlan(
  packId: string,
  testCases: AIProposedTestCase[],
  force = false,
): Promise<TestCase[]> {
  return post<TestCase[]>(`/validation-packs/${packId}/test-plan/accept-ai`, {
    test_cases: testCases,
    force,
  });
}
