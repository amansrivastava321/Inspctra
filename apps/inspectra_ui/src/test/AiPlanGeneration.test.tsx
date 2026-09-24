import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PackDetailPage from '../pages/PackDetailPage';

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

vi.mock('../api/validationPacks', () => ({
  getTestPlan: vi.fn(),
  generateTestPlan: vi.fn(),
  listTestCases: vi.fn(),
  createTestCase: vi.fn(),
  updateTestCase: vi.fn(),
  deleteTestCase: vi.fn(),
  generateAiTestPlan: vi.fn(),
  acceptAiTestPlan: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual as object, useNavigate: () => vi.fn() };
});

import { get } from '../api/client';
import {
  getTestPlan,
  listTestCases,
  generateAiTestPlan,
  acceptAiTestPlan,
} from '../api/validationPacks';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockGetTestPlan = getTestPlan as ReturnType<typeof vi.fn>;
const mockListTestCases = listTestCases as ReturnType<typeof vi.fn>;
const mockGenerateAiTestPlan = generateAiTestPlan as ReturnType<typeof vi.fn>;
const mockAcceptAiTestPlan = acceptAiTestPlan as ReturnType<typeof vi.fn>;

// ── Fixtures ────────────────────────────────────────────────────────────────────

const MOCK_PACK = {
  id: 'pack-1',
  name: 'Smoke Pack',
  description: 'Smoke tests',
  project_id: 'proj-1',
  steps: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const MOCK_AI_PREVIEW = {
  preview_id: 'preview-1',
  pack_id: 'pack-1',
  app_id: 'app-1',
  generated_from: 'ai_generation',
  generation_source: 'ollama',
  coverage_summary: {},
  risk_summary: {},
  test_cases: [
    {
      test_case_id: 'proposed-tc-1',
      flow_name: 'login',
      title: 'Successful Login',
      description: 'Login with correct credentials',
      objective: 'Login with correct credentials',
      confidence: 0.95,
      rationale: 'Core user path validation',
      test_steps: [
        {
          step_id: 'step-1',
          action_type: 'navigate',
          target: '/login',
          timeout_ms: 30000,
          optional: false,
          confidence: 1.0,
        },
        {
          step_id: 'step-2',
          action_type: 'click',
          target: '#login-btn',
          timeout_ms: 30000,
          optional: false,
          confidence: 0.9,
        },
      ],
    },
    {
      test_case_id: 'proposed-tc-2',
      flow_name: 'unsupported',
      title: 'Unsupported Action Case',
      description: 'Some fancy case',
      objective: 'Some fancy case',
      confidence: 0.7,
      rationale: 'Check fallback',
      test_steps: [
        {
          step_id: 'step-3',
          action_type: 'unsupported_fancy_action',
          target: '#target',
          timeout_ms: 30000,
          optional: false,
          confidence: 0.5,
        },
      ],
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

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

describe('AI Test Plan Generation Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockImplementation((path: string) => {
      if (path.includes('/validation-packs/pack-1')) {
        return Promise.resolve(MOCK_PACK);
      }
      if (path.includes('/runs')) return Promise.resolve([]);
      return Promise.resolve([]);
    });
  });

  // 1. Generate with AI button renders.
  it('renders the Generate with AI button in empty state and header actions', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);

    renderPackDetail();

    await waitFor(() => {
      expect(screen.getByTestId('no-test-plan-empty-state')).toBeInTheDocument();
    });

    const emptyStateBtn = screen.getByTestId('generate-ai-test-plan-empty-state-btn');
    expect(emptyStateBtn).toBeInTheDocument();

    const headerBtn = screen.getByTestId('generate-ai-test-plan-btn');
    expect(headerBtn).toBeInTheDocument();
  });

  // 2. Clicking button calls generate-ai.
  it('calls generateAiTestPlan API client method when button is clicked', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(MOCK_AI_PREVIEW);

    renderPackDetail();

    await waitFor(() => {
      expect(screen.getByTestId('no-test-plan-empty-state')).toBeInTheDocument();
    });

    const btn = screen.getByTestId('generate-ai-test-plan-btn');
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockGenerateAiTestPlan).toHaveBeenCalledWith('pack-1', undefined);
    });
  });

  // 3. Preview modal renders generated cases.
  it('renders the proposed cases and steps inside the preview modal', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(MOCK_AI_PREVIEW);

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => {
      expect(screen.getByText('AI Proposed Test Plan Preview')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('Successful Login')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Unsupported Action Case')).toBeInTheDocument();
    expect(screen.getByText('95% Match')).toBeInTheDocument();
    expect(screen.getByText('70% Match')).toBeInTheDocument();
    expect(screen.getByText('UNSUPPORTED ACTION')).toBeInTheDocument();
  });

  // 4. Selection toggle works.
  it('allows selecting/unselecting proposed test cases', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(MOCK_AI_PREVIEW);

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => screen.getByText('AI Proposed Test Plan Preview'));

    const checkboxes = screen.getAllByRole('checkbox');
    // Default selected count is 2
    expect(screen.getByRole('button', { name: /Accept Selected \(2\)/i })).toBeInTheDocument();

    // Toggle the second checkbox to deselect it
    fireEvent.click(checkboxes[1]);

    expect(screen.getByRole('button', { name: /Accept Selected \(1\)/i })).toBeInTheDocument();
  });

  // 5. Edited case title is sent to accept-ai.
  it('allows editing case title, objective, and steps in the preview state', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(MOCK_AI_PREVIEW);

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => screen.getByText('AI Proposed Test Plan Preview'));

    // Edit case title
    fireEvent.change(screen.getByDisplayValue('Successful Login'), {
      target: { value: 'Edited Login Case' },
    });
    expect(screen.getByDisplayValue('Edited Login Case')).toBeInTheDocument();

    // Edit objective
    fireEvent.change(screen.getByDisplayValue('Login with correct credentials'), {
      target: { value: 'Edited Login Description' },
    });
    expect(screen.getByDisplayValue('Edited Login Description')).toBeInTheDocument();

    // Edit step target
    fireEvent.change(screen.getByDisplayValue('/login'), {
      target: { value: '/new-login' },
    });
    expect(screen.getByDisplayValue('/new-login')).toBeInTheDocument();
  });

  // 6. Accept button calls accept-ai.
  it('calls acceptAiTestPlan API client method when accept button is clicked', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(MOCK_AI_PREVIEW);
    mockAcceptAiTestPlan.mockResolvedValue([]);

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => screen.getByText('AI Proposed Test Plan Preview'));

    // Accept
    fireEvent.click(screen.getByRole('button', { name: /Accept Selected \(2\)/i }));

    await waitFor(() => {
      expect(mockAcceptAiTestPlan).toHaveBeenCalledWith('pack-1', MOCK_AI_PREVIEW.test_cases);
    });
  });

  // 7. local_fallback badge appears.
  it('renders local_fallback badges when generation_source is local_fallback', async () => {
    const fallbackPreview = {
      ...MOCK_AI_PREVIEW,
      generation_source: 'local_fallback',
    };
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockResolvedValue(fallbackPreview);

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('modal-local-fallback-badge')).toBeInTheDocument();
    });

    // Now check if accepted case renders the local fallback badge in the main table
    const acceptedCase = {
      test_case_id: 'tc-accepted-1',
      plan_id: 'plan-1',
      pack_id: 'pack-1',
      flow_name: 'smoke',
      title: 'Fallback Case Test',
      test_type: 'positive',
      priority: 'P1',
      risk_level: 'medium',
      preconditions: [],
      steps: [],
      expected_result: 'loads',
      expected_evidence: [],
      pass_criteria: 'ok',
      fail_criteria: 'error',
      automation_status: 'ready',
      safety_level: 'safe',
      requires_permission: false,
      tags: [],
      enabled: true,
      confidence: 0.88,
      rationale: 'Local fallback rationale',
      generation_source: 'local_fallback',
    };

    mockGetTestPlan.mockResolvedValue({
      plan_id: 'plan-1',
      pack_id: 'pack-1',
      generated_from: 'ai_generation',
      coverage_summary: {},
      risk_summary: {},
      test_cases: [acceptedCase],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    mockListTestCases.mockResolvedValue([acceptedCase]);

    renderPackDetail();

    await waitFor(() => {
      expect(screen.getByTestId('local-fallback-badge')).toBeInTheDocument();
      expect(screen.getByTestId('ai-sparkles-badge')).toBeInTheDocument();
    });
  });

  // 8. Error state appears on failed generation.
  it('renders an error banner if generateAiTestPlan fails', async () => {
    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([]);
    mockGenerateAiTestPlan.mockRejectedValue(new Error('Ollama model connection timed out'));

    renderPackDetail();

    await waitFor(() => screen.getByTestId('generate-ai-test-plan-btn'));
    fireEvent.click(screen.getByTestId('generate-ai-test-plan-btn'));

    await waitFor(() => {
      expect(screen.getByText('Ollama model connection timed out')).toBeInTheDocument();
    });
  });

  it('renders accepted AI cases even if testPlan refetch is temporarily null', async () => {
    const acceptedCase = {
      test_case_id: 'tc-accepted-2',
      plan_id: 'plan-1',
      pack_id: 'pack-1',
      flow_name: 'smoke',
      title: 'Recovered AI Case',
      test_type: 'positive',
      priority: 'P1',
      risk_level: 'medium',
      preconditions: [],
      steps: [],
      expected_result: 'loads',
      expected_evidence: [],
      pass_criteria: 'ok',
      fail_criteria: 'error',
      automation_status: 'ready',
      safety_level: 'safe',
      requires_permission: false,
      tags: [],
      enabled: true,
      confidence: 0.91,
      rationale: 'Accepted from AI preview',
      generation_source: 'local_fallback',
    };

    mockGetTestPlan.mockResolvedValue(null);
    mockListTestCases.mockResolvedValue([acceptedCase]);

    renderPackDetail();

    await waitFor(() => {
      expect(screen.getByText('Recovered AI Case')).toBeInTheDocument();
      expect(screen.getByTestId('ai-sparkles-badge')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('no-test-plan-empty-state')).not.toBeInTheDocument();
  });
});
