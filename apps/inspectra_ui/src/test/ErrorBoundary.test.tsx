import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

function ThrowingChild(): ReactNode {
  throw new Error('render exploded');
}

describe('ErrorBoundary', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it('shows the default recovery screen when a child throws', async () => {
    const componentPath = '../components/ErrorBoundary';
    const { ErrorBoundary } = await import(/* @vite-ignore */ componentPath);

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
    expect(screen.getByText('render exploded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload App' })).toBeInTheDocument();
  });

  it('renders a supplied fallback when a child throws', async () => {
    const componentPath = '../components/ErrorBoundary';
    const { ErrorBoundary } = await import(/* @vite-ignore */ componentPath);

    render(
      <ErrorBoundary fallback={<p>Custom recovery</p>}>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText('Custom recovery')).toBeInTheDocument();
  });
});
