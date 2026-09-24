/**
 * PackTestPlan.test.tsx — Test Plan feature tests for PackDetailPage
 *
 * 1.  Pack detail shows "No test plan generated yet" empty state.
 * 2.  Generate test plan button calls backend generate endpoint.
 * 3.  Test cases render in All tab after plan loaded.
 * 4.  Edge case filter (tab) shows only edge_case type cases.
 * 5.  Expand test case shows steps, expected evidence, pass criteria.
 * 6.  Safety badge renders for caution/destructive cases.
 * 7.  Run pack opens review modal when no test cases exist.
 * 8.  Run blocked shows no-test-cases warning if plan is empty.
 * 9.  Create validation pack shows "generate now?" prompt after creation.
 * 10. No fake test cases in real mode (plan returns null → empty state shown).
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PackDetailPage from '../pages/PackDetailPage';
import CreateValidationPackPage from '../pages/CreateValidationPackPage';

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
  }
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

// Mock the validationPacks API module
vi.mock('../api/validationPacks', () => ({
  getTestPlan:      vi.fn(),
  generateTestPlan: vi.fn(),
  listTestCases:    vi.fn(),
  createTestCase:   vi.fn(),
  updateTestCase:   vi.fn(),
  deleteTestCase:   vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual as object, useNavigate: () => vi.fn() };
});

import { get, post } from '../api/client';
import { getTestPlan, generateTestPlan, listTestCases } from '../api/validationPacks';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockGetTestPlan = getTestPlan as ReturnType<typeof vi.fn>;
const mockGenerateTestPlan = generateTestPlan as ReturnType<typeof vi.fn>;
const mockListTestCases = listTestCases as ReturnType<typeof vi.fn>;

// ── Fixture data ───────────────────────────────────────────────────────────────

const MOCK_PACK = {
  id: 'pack-1', name: 'Smoke Pack', description: 'Smoke tests',
  project_id: 'proj-1', steps: [],
  created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
};

const MOCK_EDGE_CASE: import('../types/api').TestCase = {
  test_case_id: 'tc-edge-1', plan_id: 'plan-1', pack_id: 'pack-1',
  flow_name: 'edge_cases', title: 'Double-submit prevention',
  description: 'Prevent duplicate submission', test_type: 'edge_case',
  priority: 'P1', risk_level: 'high',
  preconditions: ['Fill valid form'],
  steps: ['Fill valid form', 'Click submit twice quickly'],
  expected_result: 'Only one submission processed',
  expected_evidence: ['screenshot', 'log'],
  pass_criteria: 'Submit button disabled after first click',
  fail_criteria: 'Duplicate records created',
  automation_status: 'needs_selector', safety_level: 'caution',
  requires_permission: false, tags: ['edge_case'], enabled: true,
};

const MOCK_DESTRUCTIVE_CASE: import('../types/api').TestCase = {
  test_case_id: 'tc-dest-1', plan_id: 'plan-1', pack_id: 'pack-1',
  flow_name: 'destructive', title: 'Delete requires confirmation',
  description: 'Test delete flow', test_type: 'negative',
  priority: 'P1', risk_level: 'high',
  preconditions: [], steps: ['Trigger delete', 'Dismiss confirmation'],
  expected_result: 'Delete cancelled',
  expected_evidence: ['screenshot'],
  pass_criteria: 'Item not deleted', fail_criteria: 'Item deleted without confirmation',
  automation_status: 'needs_selector', safety_level: 'destructive',
  requires_permission: true, tags: ['destructive'], enabled: false,
};

const MOCK_POSITIVE_CASE: import('../types/api').TestCase = {
  test_case_id: 'tc-pos-1', plan_id: 'plan-1', pack_id: 'pack-1',
  flow_name: 'smoke', title: 'App loads without error',
  test_type: 'positive', priority: 'P0', risk_level: 'high',
  preconditions: [], steps: ['Open app URL'],
  expected_result: 'Page loads',
  expected_evidence: ['screenshot'],
  pass_criteria: 'HTTP 200', fail_criteria: 'Blank page',
  automation_status: 'ready', safety_level: 'safe',
  requires_permission: false, tags: ['smoke'], enabled: true,
};

const MOCK_LEGACY_MOBILE_CASE: import('../types/api').TestCase = {
  ...MOCK_POSITIVE_CASE,
  test_case_id: 'tc-mobile-legacy',
  title: 'Legacy mobile flow',
  tags: ['mobile'],
  test_steps: [{
    step_id: 'mobile-step-1', case_id: 'tc-mobile-legacy', step_order: 0,
    action_type: 'navigate', target: '/legacy-mobile', timeout_ms: 30000, optional: false,
  }],
};

const MOCK_PLAN: import('../types/api').TestPlan = {
  plan_id: 'plan-1', pack_id: 'pack-1',
  generated_from: 'generic_app_type_template',
  coverage_summary: { positive: 1, edge_case: 1, negative: 1 },
  risk_summary: { high: 2, medium: 1 },
  test_cases: [MOCK_POSITIVE_CASE, MOCK_EDGE_CASE, MOCK_DESTRUCTIVE_CASE],
  created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
};

// ── Helper ─────────────────────────────────────────────────────────────────────

function renderPackDetail(packId = 'pack-1') {
  return render(
    <MemoryRouter initialEntries={[`/packs/${packId}`]}>
      <Routes>
        <Route path="/packs/:packId" element={<PackDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('PackDetailPage — Test Plan', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: pack loads, no runs
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/validation-packs/pack-1') && !path.includes('/test')) {
        return Promise.resolve(MOCK_PACK);
      }
      if (path.includes('/runs')) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });

  // Test 1: empty state shown when no test plan
  it('shows empty state when no test plan exists', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);

    renderPackDetail();
    await waitFor(() => {
      expect(screen.getByTestId('no-test-plan-empty-state')).toBeInTheDocument();
    });
    expect(screen.getByTestId('no-test-plan-empty-state').textContent).toMatch(
      /No test plan generated yet/i
    );
  });

  // Test 2: generate button calls generateTestPlan
  it('generate test plan button calls backend', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateTestPlan.mockResolvedValue(MOCK_PLAN);

    renderPackDetail();
    await waitFor(() => screen.getByTestId('no-test-plan-empty-state'));

    // Use role+name since Btn component doesn't spread data-testid
    const btns = screen.getAllByRole('button', { name: /Generate test plan/i });
    fireEvent.click(btns[0]);

    await waitFor(() => {
      // pack has no app_id → third arg is undefined (GAP 9: pack.app_id forwarded)
      expect(mockGenerateTestPlan).toHaveBeenCalledWith('pack-1', false, undefined);
    });
  });

  // Test 3: test cases render in All tab after plan loaded
  it('renders test cases when plan exists', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_POSITIVE_CASE, MOCK_EDGE_CASE, MOCK_DESTRUCTIVE_CASE]);

    renderPackDetail();
    await waitFor(() => {
      expect(screen.getByTestId(`test-case-row-${MOCK_POSITIVE_CASE.test_case_id}`)).toBeInTheDocument();
    });
    expect(screen.getByTestId(`test-case-row-${MOCK_EDGE_CASE.test_case_id}`)).toBeInTheDocument();
  });

  // Test 4: edge case tab filters correctly
  it('edge case tab shows only edge_case type cases', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_POSITIVE_CASE, MOCK_EDGE_CASE]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId('tab-edge_case'));

    fireEvent.click(screen.getByTestId('tab-edge_case'));

    await waitFor(() => {
      // Edge case row visible
      expect(screen.getByTestId(`test-case-row-${MOCK_EDGE_CASE.test_case_id}`)).toBeInTheDocument();
    });
    // Positive case row not visible (different type, filtered out)
    expect(screen.queryByTestId(`test-case-row-${MOCK_POSITIVE_CASE.test_case_id}`)).not.toBeInTheDocument();
  });

  // Test 5: expand test case shows steps, evidence, pass criteria
  it('expanding test case shows steps and pass criteria', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_EDGE_CASE]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId(`test-case-row-${MOCK_EDGE_CASE.test_case_id}`));

    // Expand
    fireEvent.click(screen.getByTestId(`test-case-row-${MOCK_EDGE_CASE.test_case_id}`));

    await waitFor(() => {
      expect(screen.getByTestId(`test-case-detail-${MOCK_EDGE_CASE.test_case_id}`)).toBeInTheDocument();
    });
    // Steps visible
    expect(screen.getByText('Click submit twice quickly')).toBeInTheDocument();
    // Pass criteria
    expect(screen.getByText('Submit button disabled after first click')).toBeInTheDocument();
    // Evidence
    expect(screen.getAllByText('screenshot').length).toBeGreaterThanOrEqual(1);
  });

  // Test 6: safety badge renders for caution/destructive
  it('renders safety badge for caution and destructive cases', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_EDGE_CASE, MOCK_DESTRUCTIVE_CASE]);

    renderPackDetail();
    await waitFor(() => {
      expect(screen.getByTestId('safety-badge-caution')).toBeInTheDocument();
      expect(screen.getByTestId('safety-badge-destructive')).toBeInTheDocument();
    });
  });

  it('api action dropdown includes API actions and renders API fields', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_POSITIVE_CASE]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId(`test-case-row-${MOCK_POSITIVE_CASE.test_case_id}`));

    fireEvent.click(screen.getByTestId(`test-case-row-${MOCK_POSITIVE_CASE.test_case_id}`));
    fireEvent.click(screen.getByText(/Add Step/i));

    const actionType = screen.getByDisplayValue('navigate');
    fireEvent.change(actionType, { target: { value: 'api_request' } });

    expect(screen.getByText('api_request')).toBeInTheDocument();
    expect(screen.getByText('assert_status')).toBeInTheDocument();
    expect(screen.getByText('assert_json_path')).toBeInTheDocument();
    expect(screen.getByText(/HTTP METHOD/i)).toBeInTheDocument();
    expect(screen.getByText(/REQUEST URL/i)).toBeInTheDocument();
    expect(screen.getByText(/HEADERS JSON/i)).toBeInTheDocument();
    expect(screen.getByText(/BODY JSON/i)).toBeInTheDocument();
  });

  it('shows legacy preview steps read-only and prevents running the pack', async () => {
    mockGetTestPlan.mockResolvedValue(MOCK_PLAN);
    mockListTestCases.mockResolvedValue([MOCK_LEGACY_MOBILE_CASE]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId('preview-pack-warning'));

    const runButton = screen.getByRole('button', { name: 'Run pack' });
    expect(runButton).toBeDisabled();
    expect(runButton).toHaveAttribute(
      'title',
      'Contains preview steps. Preview capabilities cannot be run yet.',
    );

    fireEvent.click(screen.getByTestId('test-case-row-tc-mobile-legacy'));
    expect((await screen.findAllByText('navigate')).length).toBeGreaterThan(0);
    expect(
      screen.getAllByTitle('This feature is planned for a future release. Runs will be unavailable.')
        .some(element => element instanceof HTMLButtonElement && element.disabled),
    ).toBe(true);
    expect(screen.getByRole('button', { name: /Add Step/i })).toBeDisabled();
  });

  // Test 7: run pack shows review modal when no test cases
  it('run pack opens review modal when no test cases exist', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId('no-test-plan-empty-state'));

    // Click Run pack
    fireEvent.click(screen.getByText('Run pack'));

    await waitFor(() => {
      expect(screen.getByTestId('run-review-modal')).toBeInTheDocument();
    });
  });

  // Test 8: review modal shows no-test-cases warning
  it('review modal shows no test cases warning when plan is empty', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);

    renderPackDetail();
    await waitFor(() => screen.getByTestId('no-test-plan-empty-state'));

    fireEvent.click(screen.getByText('Run pack'));

    await waitFor(() => {
      expect(screen.getByTestId('no-test-cases-warning')).toBeInTheDocument();
    });
  });

  // Test 10: no fake test cases in real mode — null plan → empty state
  it('shows empty state not fake cases when plan is null (real mode)', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);

    renderPackDetail();
    await waitFor(() => {
      expect(screen.getByTestId('no-test-plan-empty-state')).toBeInTheDocument();
    });
    // No test case rows rendered
    expect(screen.queryByText(/test-case-row/)).not.toBeInTheDocument();
  });
});

// ── Create pack: generate now prompt ──────────────────────────────────────────

describe('CreateValidationPackPage — generate test plan prompt', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Projects load successfully
    mockGet.mockResolvedValue([
      { id: 'proj-1', name: 'My Project', description: '' },
    ]);
    // Pack creation succeeds
    mockPost.mockResolvedValue({ id: 'new-pack-1', name: 'Test Pack', project_id: 'proj-1' });
  });

  // Test 9: shows "generate now?" prompt after pack created
  it('shows generate-now prompt after pack is created', async () => {
    render(
      <MemoryRouter>
        <CreateValidationPackPage />
      </MemoryRouter>
    );

    // Wait for project card to render
    await waitFor(() => expect(screen.getByTestId('project-card-proj-1')).toBeInTheDocument());

    // Select project card
    fireEvent.click(screen.getByTestId('project-card-proj-1'));

    // Fill pack name (find by role textbox, first = name input)
    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: 'Test Pack' } });

    // Wait for button to become enabled, then click
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Create pack/i });
      expect(btn).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /Create pack/i }));

    await waitFor(() => {
      expect(screen.getByTestId('generate-now-prompt')).toBeInTheDocument();
    });
    expect(screen.getByTestId('generate-now-prompt').textContent).toMatch(
      /Pack created/i
    );
  });
});
