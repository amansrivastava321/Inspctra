import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { EmptyState, BlockedState, StaleDataState, PartialConfigBanner } from '../components/common/EmptyState';

function wrap(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('EmptyState', () => {
  it('renders title and description', () => {
    wrap(<EmptyState title="No items" description="Nothing here yet." />);
    expect(screen.getByTestId('empty-state')).toBeDefined();
    expect(screen.getByText('No items')).toBeDefined();
    expect(screen.getByText('Nothing here yet.')).toBeDefined();
  });

  it('renders action when provided', () => {
    wrap(<EmptyState title="Empty" action={<button>Create</button>} />);
    expect(screen.getByRole('button', { name: 'Create' })).toBeDefined();
  });

  it('renders secondaryAction when provided', () => {
    wrap(
      <EmptyState
        title="Empty"
        action={<button>Primary</button>}
        secondaryAction={<button>Secondary</button>}
      />
    );
    expect(screen.getByRole('button', { name: 'Primary' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Secondary' })).toBeDefined();
  });

  it('omits description when not provided', () => {
    wrap(<EmptyState title="No items" />);
    expect(screen.queryByText('Nothing here yet.')).toBeNull();
  });
});

describe('BlockedState', () => {
  it('renders with default AlertTriangle icon', () => {
    wrap(<BlockedState title="Setup required" description="Do this first." />);
    const el = screen.getByTestId('blocked-state');
    expect(el).toBeDefined();
    expect(screen.getByText('Setup required')).toBeDefined();
    expect(screen.getByText('Do this first.')).toBeDefined();
  });

  it('renders CTA action when provided', () => {
    wrap(
      <BlockedState
        title="Blocked"
        action={<button>Connect App</button>}
      />
    );
    expect(screen.getByRole('button', { name: 'Connect App' })).toBeDefined();
  });

  it('accepts custom icon', () => {
    wrap(
      <BlockedState
        title="Blocked"
        icon={<span data-testid="custom-icon">🔒</span>}
      />
    );
    expect(screen.getByTestId('custom-icon')).toBeDefined();
  });
});

describe('StaleDataState', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('renders nothing when fetchedAt is null', () => {
    wrap(<StaleDataState fetchedAt={null} onRefresh={() => {}} />);
    expect(screen.queryByTestId('stale-data-state')).toBeNull();
  });

  it('renders nothing when data is fresh (< 5 min)', () => {
    const freshDate = new Date(Date.now() - 2 * 60 * 1000); // 2 min ago
    wrap(<StaleDataState fetchedAt={freshDate} onRefresh={() => {}} />);
    expect(screen.queryByTestId('stale-data-state')).toBeNull();
  });

  it('renders stale indicator when data is old (> 5 min)', () => {
    const staleDate = new Date(Date.now() - 10 * 60 * 1000); // 10 min ago
    wrap(<StaleDataState fetchedAt={staleDate} onRefresh={() => {}} />);
    expect(screen.getByTestId('stale-data-state')).toBeDefined();
    expect(screen.getByText(/Last updated/)).toBeDefined();
    expect(screen.getByTestId('stale-refresh-btn')).toBeDefined();
  });

  it('calls onRefresh when Refresh button is clicked', async () => {
    const onRefresh = vi.fn();
    const staleDate = new Date(Date.now() - 10 * 60 * 1000);
    wrap(<StaleDataState fetchedAt={staleDate} onRefresh={onRefresh} />);
    screen.getByTestId('stale-refresh-btn').click();
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it('respects custom staleMs threshold', () => {
    const date = new Date(Date.now() - 30 * 1000); // 30 sec ago
    wrap(<StaleDataState fetchedAt={date} onRefresh={() => {}} staleMs={10 * 1000} />);
    expect(screen.getByTestId('stale-data-state')).toBeDefined();
  });
});

describe('PartialConfigBanner', () => {
  it('renders message', () => {
    wrap(<PartialConfigBanner message="This item is incomplete." />);
    expect(screen.getByTestId('partial-config-banner')).toBeDefined();
    expect(screen.getByText('This item is incomplete.')).toBeDefined();
  });

  it('renders action when provided', () => {
    wrap(
      <PartialConfigBanner
        message="Add steps."
        action={<button>Add Steps</button>}
      />
    );
    expect(screen.getByRole('button', { name: 'Add Steps' })).toBeDefined();
  });
});
