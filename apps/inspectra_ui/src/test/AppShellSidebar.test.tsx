import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from '../components/layout/AppShell';

vi.mock('../api/client', () => ({
  get: vi.fn().mockResolvedValue([]),
  checkHealth: vi.fn().mockResolvedValue('online'),
  getBackendStatus: vi.fn().mockReturnValue('online'),
  onBackendStatus: vi.fn().mockReturnValue(() => {}),
}));

describe('AppShell sidebar visibility', () => {
  beforeEach(() => localStorage.clear());

  it('hides and restores primary navigation from the hamburger toggle', () => {
    render(
      <MemoryRouter>
        <AppShell title="Test page"><div>Page content</div></AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Hide navigation' }));
    expect(screen.queryByRole('navigation', { name: 'Primary navigation' })).not.toBeInTheDocument();
    expect(screen.getByText('Page content')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Show navigation' }));
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  });
});
