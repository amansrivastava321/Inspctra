import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RuntimeDoctorPage from '../pages/RuntimeDoctorPage';
import { MOCK_DOCTOR } from '../mocks/sampleData';

vi.mock('../api/client', () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) { super(msg); this.status = status; this.name = 'ApiError'; }
  }
  return {
    get: vi.fn(),
    post: vi.fn(),
    checkHealth: vi.fn().mockResolvedValue('online'),
    getBackendStatus: vi.fn().mockReturnValue('online'),
    onBackendStatus: vi.fn().mockReturnValue(() => {}),
    ApiError,
  };
});

import { get } from '../api/client';
const mockGet = get as ReturnType<typeof vi.fn>;

describe('RuntimeDoctorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders readiness score from real data', async () => {
    mockGet.mockResolvedValue(MOCK_DOCTOR); // 72 from mock data
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    // Score appears in both the main score card and the sidebar ReadinessScore — use getAllByText
    await waitFor(() => {
      expect(screen.getAllByText('72').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows things to fix', async () => {
    mockGet.mockResolvedValue(MOCK_DOCTOR);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getAllByText(/Environment Readiness/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows component status section', async () => {
    mockGet.mockResolvedValue(MOCK_DOCTOR);
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('COMPONENT STATUS')).toBeInTheDocument();
    });
  });

  it('preserves provenance from a real backend response across doctor status surfaces', async () => {
    mockGet.mockResolvedValue({
      ...MOCK_DOCTOR,
      readiness_label: 'partial',
      provenance: 'REAL_EXECUTION',
    });
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);

    await waitFor(() => {
      expect(document.querySelector('[data-provenance-source="Runtime Doctor detail"]')).toHaveTextContent('Real');
    });
    expect(document.querySelector('[data-provenance-source="Runtime Doctor score"]')).toHaveTextContent('Real');
    expect(document.querySelectorAll('[data-provenance-source="Runtime Doctor component"]').length).toBeGreaterThan(0);
  });

  it('shows real score when backend returns 0 (no hardcoded 72)', async () => {
    mockGet.mockResolvedValue({
      ...MOCK_DOCTOR,
      readiness_score: 0,
      readiness_band: 'missing',
      components: [],
      things_to_fix: [],
      summary: { ready: 0, missing: 0, perm: 0, skipped: 0 },
    });
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // Multiple "0"s appear (score + summary) — that's correct, none should be "72"
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    });
    expect(screen.queryByText('72')).not.toBeInTheDocument();
  });

  it('shows offline state when backend unreachable', async () => {
    const { ApiError } = await import('../api/client');
    mockGet.mockRejectedValue(new (ApiError as any)(0, 'Network error'));
    render(<MemoryRouter><RuntimeDoctorPage /></MemoryRouter>);
    await waitFor(() => {
      // Multiple "Backend offline" elements appear (Sidebar workspace label + main OfflineState)
      expect(screen.getAllByText(/backend offline/i).length).toBeGreaterThan(0);
    });
    expect(document.querySelectorAll('[data-testid="provenance-badge"]')).toHaveLength(0);
  });
});
