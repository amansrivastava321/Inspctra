import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PreviewBadge } from '../components/PreviewBadge';
import { CapabilityTypeSelector } from '../components/validation/CapabilityTypeSelector';
import { PreviewSchedule } from '../components/validation/PreviewSchedule';
import { StartRunModal } from '../components/modals/StartRunModal';
import {
  hasPreviewSteps,
  isPreviewAction,
  isPreviewAppType,
  isPreviewSchedule,
  SCHEDULE_PREVIEW_TOOLTIP,
} from '../config/capabilities';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
}));

import { get, post } from '../api/client';

const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;

describe('preview capability policy', () => {
  it('classifies only unimplemented execution families as preview', () => {
    expect(isPreviewAction('mobile_tap')).toBe(true);
    expect(isPreviewAction('desktop_launch')).toBe(true);
    expect(isPreviewAction('distributed_fan_out')).toBe(true);
    expect(isPreviewAction('chaos_network_partition')).toBe(true);
    expect(isPreviewAction('ci_pipeline_gate')).toBe(true);
    expect(isPreviewAction('enterprise_governance_check')).toBe(true);

    for (const action of [
      'navigate', 'api_request', 'check_accessibility',
      'passive_security_check', 'measure_page_load', 'assert_visual_match',
    ]) {
      expect(isPreviewAction(action)).toBe(false);
    }
  });

  it('detects preview steps in legacy pack and test-case shapes', () => {
    expect(hasPreviewSteps(
      [{ action_type: 'navigate' }],
      [{ test_steps: [{ action_type: 'mobile_tap' }] }],
    )).toBe(true);
    expect(hasPreviewSteps([{ action_type: 'api_request' }], [])).toBe(false);
  });

  it('marks mobile/desktop targets and non-manual schedules as preview', () => {
    expect(isPreviewAppType('mobile')).toBe(true);
    expect(isPreviewAppType('desktop')).toBe(true);
    expect(isPreviewAppType('web')).toBe(false);
    expect(isPreviewAppType('api')).toBe(false);
    // Schedules the scheduler can run are live; only free-text ones it cannot honour stay Preview.
    expect(isPreviewSchedule('nightly')).toBe(false);
    expect(isPreviewSchedule('hourly')).toBe(false);
    expect(isPreviewSchedule('every_15m')).toBe(false);
    expect(isPreviewSchedule('every_6h')).toBe(false);
    expect(isPreviewSchedule('weekdays 09:00')).toBe(true);
    expect(isPreviewSchedule('on PR')).toBe(true);
    expect(isPreviewSchedule('every_1m')).toBe(true);
    expect(isPreviewSchedule('manual')).toBe(false);
    expect(isPreviewSchedule('none')).toBe(false);
  });
});

describe('preview capability presentation', () => {
  it('renders a neutral Preview badge with planned-feature help', () => {
    render(<PreviewBadge />);
    expect(screen.getByText('Preview')).toHaveAttribute(
      'title',
      'This feature is planned for a future release. Runs will be unavailable.',
    );
  });

  it('keeps MVP test types enabled and preview types visible but disabled', () => {
    const onSelect = vi.fn();
    render(<CapabilityTypeSelector actionType="navigate" onSelectAction={onSelect} />);

    for (const label of [
      'Web Test', 'API Test', 'Manual Test', 'Accessibility',
      'Security Check', 'Performance Check', 'Visual Regression',
    ]) {
      expect(screen.getByRole('button', { name: label })).not.toBeDisabled();
    }
    for (const label of [
      'Mobile Testing', 'Desktop Testing', 'Distributed Execution',
      'Chaos Engineering', 'CI/CD Integration', 'Enterprise Governance',
    ]) {
      const option = screen.getByRole('button', { name: `${label} Preview` });
      expect(option).toBeDisabled();
      expect(option).toHaveAttribute(
        'title',
        'This feature is planned for a future release. Runs will be unavailable.',
      );
      fireEvent.click(option);
    }
    expect(onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'API Test' }));
    expect(onSelect).toHaveBeenCalledWith('api_request');
  });

  it('describes supported schedules, badges unsupported ones as preview and leaves manual runs unbadged', () => {
    const { rerender } = render(<PreviewSchedule schedule="nightly" />);
    expect(screen.getByText('Every day at 02:00 (UTC)')).toBeInTheDocument();
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();

    rerender(<PreviewSchedule schedule="every_15m" />);
    expect(screen.getByText('Every 15 minutes')).toBeInTheDocument();

    rerender(<PreviewSchedule schedule="weekdays" timezone="Asia/Kolkata" />);
    expect(screen.getByText('Weekdays at 09:00 (Asia/Kolkata)')).toBeInTheDocument();

    rerender(<PreviewSchedule schedule="on PR" />);
    expect(screen.getByText('on PR')).toBeInTheDocument();
    expect(screen.getByText('Preview')).toHaveAttribute('title', SCHEDULE_PREVIEW_TOOLTIP);

    rerender(<PreviewSchedule schedule="manual" />);
    expect(screen.getByText('manual')).toBeInTheDocument();
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();
  });
});

describe('preview run target protection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue([
      { id: 'web-1', name: 'Website', app_type: 'web' },
      { id: 'mobile-1', name: 'Phone app', app_type: 'mobile' },
      { id: 'desktop-1', name: 'Desktop app', app_type: 'desktop' },
    ]);
    mockPost.mockResolvedValue({ id: 'run-1' });
  });

  it('disables preview app targets in the start-run dialog', async () => {
    render(
      <MemoryRouter>
        <StartRunModal packId="pack-1" packName="Pack" onClose={vi.fn()} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /Phone app.*Preview/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Desktop app.*Preview/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /Website/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Start run' }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
  });
});

