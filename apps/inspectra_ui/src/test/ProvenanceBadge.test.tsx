import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import type { Provenance } from '../types/api';

const CASES: Array<[Provenance, string, string, string]> = [
  ['REAL_EXECUTION', 'Real', 'This result came from an actual execution.', '#10b981'],
  ['DRY_RUN', 'Dry Run', 'This result was simulated without side effects.', '#f59e0b'],
  ['MIXED', 'Mixed', 'Some steps ran for real, others were simulated.', '#f97316'],
  ['SIMULATED', 'Simulated', 'This is simulated data.', '#3b82f6'],
  ['DEMO_EXAMPLE', 'Demo', 'Sample data for exploration.', '#a855f7'],
  ['UNAVAILABLE', 'Unavailable', 'This data could not be verified.', '#6b7280'],
];

describe('ProvenanceBadge', () => {
  it.each(CASES)('renders %s as the required badge', (provenance, label, tooltip, color) => {
    render(<ProvenanceBadge provenance={provenance} source="Test surface" />);

    const badge = screen.getByTestId('provenance-badge');
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveAttribute('title', tooltip);
    expect(badge).toHaveAttribute('data-provenance-source', 'Test surface');
    expect(badge).toHaveStyle({ display: 'inline-flex', whiteSpace: 'nowrap' });
    expect(screen.getByTestId('provenance-dot')).toHaveStyle({ backgroundColor: color });
  });

  it('renders Unavailable and warns in development when provenance is missing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    render(<ProvenanceBadge provenance={undefined} source="Run card" />);

    expect(screen.getByTestId('provenance-badge')).toHaveTextContent('Unavailable');
    await waitFor(() => expect(warn).toHaveBeenCalledWith('Missing provenance for Run card'));
    warn.mockRestore();
  });
});
